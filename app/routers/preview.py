from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app import models
from db_connection import DatabaseConnection
import re

router = APIRouter(prefix="/preview", tags=["preview"])

def fill_template(template: str, data: dict) -> str:
    """Fill template with data values using regex to handle single or double braces"""
    if not template:
        return ""
        
    def replace(match):
        key = match.group(1)
        value = data.get(key)
        if value is None:
            return ''
        # Format numbers with thousand separator
        if isinstance(value, (int, float)):
            return f"{value:,}"
        return str(value)

    # Support {key} or {{key}}
    pattern = r"{+([\w]+)}+"
    try:
        return re.sub(pattern, replace, template)
    except Exception as e:
        print(f"Error in fill_template: {str(e)}")
        return template  # Return original template if error occurs

def inject_limit_offset(sql: str, limit: int, offset: int) -> str:
    """Remove existing LIMIT and add new LIMIT/OFFSET"""
    cleaned_sql = sql.strip().rstrip(';')

    # Remove existing LIMIT ... OFFSET ... (jika ada)
    cleaned_sql = re.sub(r"\s+LIMIT\s+\d+(\s+OFFSET\s+\d+)?", "", cleaned_sql, flags=re.IGNORECASE)

    return f"{cleaned_sql} LIMIT {limit} OFFSET {offset}"

@router.get("/data/{query_id}")
def preview_data(
    query_id: int,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1),
    db: Session = Depends(get_db)
):
    # Get query details from SQLAlchemy
    query_store = db.query(models.QueryStore).filter(models.QueryStore.id == query_id).first()
    if not query_store:
        raise HTTPException(status_code=404, detail="Query not found")

    # Initialize database connection for executing the query
    db_conn = DatabaseConnection()
    try:
        # Execute the stored query
        results = db_conn.execute_query(query_store.generated_sql)
        
        if not results:
            return {
                "response_type": query_store.response_type,
                "display_type": query_store.display_type,
                "data": []
            }

        if query_store.response_type == "sentence":
            # For sentence type, use the template
            print("Template:", query_store.answer_template)
            print("Data:", results[0])
            result = fill_template(query_store.answer_template, results[0])
            print("Result after template fill:", result)
            return {
                "response_type": "sentence",
                "display_type": query_store.display_type,
                "output_text": result
            }
        
        elif query_store.response_type in ["table", "bar_chart", "line_chart", "pie_chart"]:
            offset = (page - 1) * limit
            paginated_sql = inject_limit_offset(query_store.generated_sql, limit, offset)

            # Eksekusi query paginasi
            results = db_conn.execute_query(paginated_sql)

            # Count total (optional, tergantung database)
            count_sql = f"SELECT COUNT(*) as total_count FROM ({query_store.generated_sql.rstrip(';')}) as count_subquery"
            count_result = db_conn.execute_query(count_sql)
            total_count = count_result[0]["total_count"] if count_result else len(results)

            return {
                "response_type": query_store.response_type,
                "display_type": query_store.display_type,
                "page": page,
                "limit": limit,
                "total": total_count,
                "data": results
            }
        
        else:
            raise HTTPException(status_code=400, detail="Unknown response type")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error executing query: {str(e)}")
    
    finally:
        db_conn.close()