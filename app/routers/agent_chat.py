import asyncio
import json
import time
from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app import crud, models, schemas
from app.database import get_db
from app.dependencies_auth import get_current_user
from typing import Generator, Dict, Any
from agents import Agent, Runner, function_tool
from app.modules.chat.schema import ChatStreamInput
from openai.types.responses import ResponseTextDeltaEvent
import queue
from concurrent.futures import ThreadPoolExecutor
from app.methods.generate_sql import generate_sql_from_natural_language

from app.utils.templates.chat_system_prompt import chat_system_prompt_template
from db_connection import DatabaseConnection

router = APIRouter(prefix="/agent-chat", tags=["agent-chat"])

# Global variables to store context for function tools
_current_db = None
_current_user = None

def set_tool_context(db: Session, user: models.User):
    """Set context for function tools"""
    global _current_db, _current_user
    _current_db = db
    _current_user = user

@function_tool
def show_query_store(question: str):
    """Generate SQL from natural language and store in QueryStore - ONLY return JSON format"""
    global _current_db, _current_user
    
    if not _current_db or not _current_user:
        return json.dumps({
            "type": "tool_call_result",
            "tool_name": "show_query_store",
            "content": {"error": "Database context not available"},
            "status": "error"
        }, ensure_ascii=False)
    
    try:
        print(f"show_query_store: {question}")
        
        # Generate SQL from natural language
        sql_result = generate_sql_from_natural_language(question, _current_user.id)
        
        # Create new QueryStore entry
        query_store = models.QueryStore(
            user_id=_current_user.id,
            question=question,
            generated_sql=sql_result.get("generated_sql", ""),
            response_type=sql_result.get("response_type", ""),
            answer_template=sql_result.get("answer_template", ""),
            display_type=sql_result.get("response_type", "")
        )
        
        _current_db.add(query_store)
        _current_db.commit()
        _current_db.refresh(query_store)

        # PENTING: Hanya return JSON format yang diinginkan
        json_format = {
            "type": "tool_call_result",
            "tool_name": "show_query_store",
            "content": {
                "query_id": query_store.id,
            },
            "status": "success"
        }
        
        return json.dumps(json_format, ensure_ascii=False)
        
    except Exception as e:
        print(f"Error in show_query_store: {str(e)}")
        error_format = {
            "type": "tool_call_result",
            "tool_name": "show_query_store",
            "content": {"error": str(e)},
            "status": "error"
        }
        return json.dumps(error_format, ensure_ascii=False)

def create_stream_event(event_type: str, content: Any = None, **kwargs) -> str:
    """Helper function untuk membuat NDJSON event"""
    timestamp = None
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            timestamp = loop.time()
    except RuntimeError:
        timestamp = time.time()
    
    event = {
        "type": event_type,
        "timestamp": timestamp,
        **kwargs
    }
    
    if content is not None:
        event["content"] = content
    
    return json.dumps(event, ensure_ascii=False) + "\n"

@router.post("/stream")
def stream_chat_agents_background(
    chat_input: ChatStreamInput,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):  
    def event_stream() -> Generator[str, None, None]:
        try:
            yield create_stream_event("start", {"message": "Starting chat processing"})
            
            # Set tool context for function tools
            set_tool_context(db, current_user)
            
            # Simpan user message
            crud.create_chat(
                db=db,
                chat=schemas.ChatCreate(type="user", content=chat_input.query),
                user_id=current_user.id
            )
            
            # Setup untuk streaming
            result_queue = queue.Queue()
            ai_content_container = {"content": ""}
            tool_used = {"used": False}  # Flag untuk track tool usage
            
            def async_stream_task():
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    schema_db = DatabaseConnection()
                    schema_text = schema_db.get_schema_text()
                    
                    async def do_streaming():
                        # Get recent conversation context
                        last_chats = crud.get_last_chats_by_user(db, current_user.id, limit=8)
                        is_first_interaction = len(last_chats) == 0
                        chat_context = ""
                        if last_chats and not is_first_interaction:
                            chat_entries = []
                            for chat in last_chats[-8:]:
                                role = "User" if chat.type == "user" else "Assistant"
                                chat_entries.append(f"{role}: {chat.content[:150]}") 
                            chat_context = "RECENT CONVERSATION HISTORY:\n" + "\n".join(chat_entries)

                        # Generate system prompt dengan template yang sudah diperbaiki
                        data = {
                            "full_name": current_user.full_name,
                            "system_lang": "Bahasa Indonesia",
                            "schema_text": schema_text,
                            "chat_context": chat_context
                        }
                        template = chat_system_prompt_template
                        for key, value in data.items():
                            template = template.replace(f"{{{key}}}", value)
                        
                        system_prompt = template

                        # Run agent dengan instruksi yang lebih ketat
                        agent = Agent(
                            name="Assistant",
                            instructions=system_prompt,
                            model="gpt-4o",
                            tools=[show_query_store]
                        )
                        
                        result = Runner.run_streamed(agent, input=chat_input.query)
                        
                        async for event in result.stream_events():
                            # Handle text delta - tapi hanya jika tidak ada tool yang dipanggil
                            if (event.type == "raw_response_event" and 
                                isinstance(event.data, ResponseTextDeltaEvent) and 
                                event.data.delta and
                                not tool_used["used"]):
                                
                                ai_content_container["content"] += event.data.delta
                                result_queue.put({
                                    "type": "text_delta",
                                    "content": event.data.delta
                                })

                            elif event.type == "run_item_stream_event":
                                if event.item.type == "tool_call_item":
                                    tool_used["used"] = True
                                    # Clear any previous AI content since we're using a tool
                                    ai_content_container["content"] = ""
                                    
                                    result_queue.put({
                                        "type": "tool_call_start",
                                        "tool_name": getattr(event.item, "name", "unknown"),
                                        "tool_id": getattr(event.item, "id", None),
                                        "arguments": getattr(event.item, "arguments", {}),
                                    })
                                    print(f"-- Tool called: {getattr(event.item, 'name', 'unknown')}")
                                    
                                elif event.item.type == "tool_call_output_item":
                                    # Tool output - ini yang akan menjadi respons final
                                    tool_output = event.item.output
                                    print(f"-- Tool output: {tool_output}")
                                    
                                    # Set tool output sebagai content final
                                    ai_content_container["content"] = tool_output
                                    
                                    # Send tool result
                                    result_queue.put({
                                        "type": "tool_call_result", 
                                        "content": tool_output
                                    })
                                    
                                elif event.item.type == "message_output_item":
                                    # Jika ada message output setelah tool, abaikan jika tool sudah dipanggil
                                    if not tool_used["used"]:
                                        pass  # Handle normal message
                        
                        # Send completion
                        result_queue.put({
                            "type": "completion",
                            "content": ai_content_container["content"]
                        })
                        result_queue.put(None)  # End signal
                    
                    loop.run_until_complete(do_streaming())
                    
                except Exception as e:
                    print(f"Streaming error: {str(e)}")
                    result_queue.put({
                        "type": "error",
                        "content": str(e),
                        "error_code": "STREAMING_ERROR"
                    })
                    result_queue.put(None)
                finally:
                    loop.close()
            
            # Jalankan streaming di background
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(async_stream_task)
                
                # Stream hasil
                while True:
                    try:
                        chunk = result_queue.get(timeout=60)
                        if chunk is None:
                            break
                        
                        # Convert chunk to NDJSON
                        if isinstance(chunk, dict):
                            yield json.dumps(chunk, ensure_ascii=False) + "\n"
                        else:
                            # Fallback untuk string biasa
                            yield create_stream_event("text", chunk)
                            
                    except queue.Empty:
                        yield create_stream_event("error", "Connection timeout", error_code="TIMEOUT")
                        break
                
                # Tunggu task selesai
                try:
                    future.result(timeout=5)
                except Exception as e:
                    print(f"Future result error: {str(e)}")
            
            # Send final end event
            yield create_stream_event("end", {"message": "Stream completed"})
            
            # Simpan response di background task
            def save_response():
                if ai_content_container["content"].strip():
                    crud.create_chat(
                        db=db,
                        chat=schemas.ChatCreate(type="assistant", content=ai_content_container["content"]),
                        user_id=current_user.id
                    )
            
            background_tasks.add_task(save_response)
            
        except Exception as e:
            print(f"General error: {str(e)}")
            yield create_stream_event("error", str(e), error_code="GENERAL_ERROR")
    
    return StreamingResponse(
        event_stream(), 
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )