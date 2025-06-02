from app.utils.openai import openai_client
import datetime
from db_connection import DatabaseConnection
import json

def generate_sql_from_natural_language(question: str, user_id: int):
    today = datetime.date.today()
    
    # Get database schema
    db = DatabaseConnection()
    schema_info = db.get_schema()
    
    # Convert schema info to readable format for prompt
    schema_text = "Database Schema:\n"
    for table_name, columns in schema_info.items():
        schema_text += f"\nTable: {table_name}\n"
        for column in columns:
            schema_text += f"  - {column['Field']} ({column['Type']})\n"
    
    prompt = f"""
Kamu adalah asisten AI yang mengubah pertanyaan pengguna menjadi query SQL.

Berikut adalah skema database yang tersedia:
{schema_text}

PENTING: Kamu harus memberikan response dalam format JSON yang valid dengan struktur berikut:
{{
    "generated_sql": "query SQL untuk MySQL",
    "response_type": "pilih salah satu: sentence, table, bar_chart, line_chart, atau pie_chart",
    "answer_template": "template jawaban dengan placeholder menggunakan {{nama_field}}"
}}

Contoh input: "Berapa total transaksi saya bulan ini?"
Contoh output yang valid:
{{
    "generated_sql": "SELECT SUM(total) as total FROM transaksi WHERE user_id = {user_id} AND tanggal >= '{today.replace(day=1)}'",
    "response_type": "sentence",
    "answer_template": "Total transaksi anda di bulan ini adalah Rp {{total}}"
}}

Berikan response untuk pertanyaan berikut dalam format JSON yang valid:
"{question}"
"""

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system", 
                    "content": "Kamu adalah asisten SQL yang selalu memberikan response dalam format JSON yang valid. Pastikan response-mu bisa di-parse oleh json.loads()."
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.2
        )

        response_content = response.choices[0].message.content.strip()
        
        # Coba parse hasil sebagai JSON
        try:
            json_result = json.loads(response_content)
            
            # Validasi struktur JSON
            required_fields = ["generated_sql", "response_type", "answer_template"]
            for field in required_fields:
                if field not in json_result:
                    raise Exception(f"Missing required field: {field}")
            
            # Validasi response_type
            valid_response_types = ["sentence", "table", "bar_chart", "line_chart", "pie_chart"]
            if json_result["response_type"] not in valid_response_types:
                raise Exception(f"Invalid response_type. Must be one of: {', '.join(valid_response_types)}")
            
            return json_result
            
        except json.JSONDecodeError as e:
            raise Exception(f"Invalid JSON format from GPT response: {response_content}")
        except Exception as e:
            raise Exception(f"Validation error: {str(e)}")
            
    except Exception as e:
        raise Exception(f"Error in GPT request: {str(e)}")
