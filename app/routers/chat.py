import asyncio
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app import crud, models, schemas
from app.database import get_db
from app.dependencies_auth import get_current_user
from typing import Generator, List
from agents import Agent, Runner
from app.modules.chat.schema import ChatStreamInput, TestChat
from app.utils.openai import get_openai_client
from app.methods.generate_sql import generate_sql_from_natural_language
from db_connection import DatabaseConnection
from openai.types.responses import ResponseTextDeltaEvent
import queue
from concurrent.futures import ThreadPoolExecutor

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/create", response_model=schemas.ChatResponse)
def create_chat(
    chat: schemas.ChatCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    return crud.create_chat(db=db, chat=chat, user_id=current_user.id)

@router.post("/create-chat-sql")
def create_chat_sql(
    chat: TestChat,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # Generate SQL from natural language
    try:
        sql_result = generate_sql_from_natural_language(chat.query, current_user.id)
        
        # Create new QueryStore entry
        query_store = models.QueryStore(
            user_id=current_user.id,
            question=chat.query,
            generated_sql=sql_result.get("generated_sql", ""),
            response_type=sql_result.get("response_type", ""),
            answer_template=sql_result.get("answer_template", ""),
            display_type=sql_result.get("response_type", "")  # Using response_type as display_type
        )
        
        db.add(query_store)
        db.commit()
        db.refresh(query_store)
        
        return {
            "query_id": query_store.id
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating SQL: {str(e)}"
        )

@router.post("/stream")
def stream_chat(
    chat: ChatStreamInput,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    def event_stream() -> Generator[str, None, None]:
        try:
            # Get database schema
            schema_db = DatabaseConnection()
            schema_info = schema_db.get_schema()
            

            # Build comprehensive schema description with intelligent suggestions
            schema_sections = []

            for table_name, columns in schema_info.items():
                column_details = []
                date_columns = []
                numeric_columns = []
                text_columns = []
                
                for col in columns:
                    col_info = f"{col['Field']} ({col['Type']}"
                    if col.get('Key') == 'PRI':
                        col_info += ", PRIMARY KEY"
                    if col.get('Key') == 'UNI':
                        col_info += ", UNIQUE"
                    if col.get('Null') == 'NO':
                        col_info += ", NOT NULL"
                    if col.get('Default'):
                        col_info += f", DEFAULT: {col['Default']}"
                    col_info += ")"
                    column_details.append(f"    • {col_info}")
                    
                    # Categorize columns for smart suggestions
                    col_type = col['Type'].lower()
                    col_name = col['Field'].lower()
                    
                    if any(date_word in col_type for date_word in ['date', 'time', 'timestamp']):
                        date_columns.append(col['Field'])
                    elif any(num_word in col_type for num_word in ['int', 'decimal', 'float', 'double', 'numeric']):
                        numeric_columns.append(col['Field'])
                    elif any(text_word in col_type for text_word in ['varchar', 'text', 'char']):
                        text_columns.append(col['Field'])
                
                schema_sections.append(f"  {table_name}:\n" + "\n".join(column_details))
            
            schema_text = "DATABASE SCHEMA:\n" + "\n\n".join(schema_sections)
                    
            last_chats = crud.get_last_chats_by_user(db, current_user.id, limit=20)
            is_first_interaction = len(last_chats) == 0
            chat_context = ""
            if last_chats and not is_first_interaction:
                chat_entries = []
                for chat_item in last_chats[-8:]:
                    role = "User" if chat_item.type == "user" else "Assistant"
                    chat_entries.append(f"{role}: {chat_item.content[:150]}")
                chat_context = "RECENT CONVERSATION HISTORY:\n" + "\n".join(chat_entries)

            messages = []
            system_lang = "Indonesian"
            system_prompt = f""""""

            messages.append({"role": "system", "content": system_prompt})

            for c in reversed(last_chats):
                role = "assistant" if c.type == "assistant" else "user"
                messages.append({"role": role, "content": c.content})
            messages.append({"role": "user", "content": chat.query})

            # Simpan pesan user
            crud.create_chat(db=db, chat=schemas.ChatCreate(type="user", content=chat.query), user_id=current_user.id)

            openai_client = get_openai_client()
            response = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                stream=True
            )

            ai_content = ""
            for chunk in response:
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    ai_content += delta.content
                    yield delta.content

            crud.create_chat(db=db, chat=schemas.ChatCreate(type="assistant", content=ai_content), user_id=current_user.id)

        except Exception as e:
            yield f"Error: {str(e)}"

    return StreamingResponse(event_stream(), media_type="text/plain")

@router.get("/list", response_model=list[schemas.ChatResponse])
def list_chats(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    chats = crud.get_all_chats_by_user(db, current_user.id)
    return chats

@router.post("/clear-chat")
def clear_chat(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    crud.delete_all_chats_by_user(db, current_user.id)
    return {"message": "Chat history cleared successfully"}