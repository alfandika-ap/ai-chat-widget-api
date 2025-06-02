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
from app.utils.openai import openai_client
from app.methods.generate_sql import generate_sql_from_natural_language
from db_connection import DatabaseConnection
from openai.types.responses import ResponseTextDeltaEvent
import queue
from concurrent.futures import ThreadPoolExecutor

router = APIRouter(prefix="/agent-chat", tags=["agent-chat"])

@router.post("/stream")
def stream_chat_agents_background(
    chat_input: ChatStreamInput,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):  
    def event_stream() -> Generator[str, None, None]:
        try:
            # Simpan user message
            crud.create_chat(
                db=db,
                chat=schemas.ChatCreate(type="user", content=chat_input.query),
                user_id=current_user.id
            )
            
            # Setup untuk streaming
            result_queue = queue.Queue()
            ai_content_container = {"content": ""}
            
            def async_stream_task():
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    
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

                        system_lang = "Indonesian"
                        system_prompt = f"""
                        You are an intelligent database assistant with multilingual capabilities.

                        USER CONTEXT:
                        • Name: {current_user.username}
                        • Language: {system_lang}

                        RESPONSE LANGUAGE: Always respond in {system_lang}

                        CORE CAPABILITIES:
                        1. Generate accurate SQL queries from natural language
                        2. Provide clear, contextual database insights
                        3. Create appropriate response templates and visualizations
                        4. Suggest relevant follow-up questions
                        5. Explain complex database concepts simply
                        6. Maintain polite, professional communication

                        BEHAVIOR GUIDELINES:
                        • Always greet users politely, especially new users
                        • Use {system_lang} consistently in all responses
                        • Provide helpful suggestions based on database schema
                        • Validate SQL syntax and logic before responding
                        • Consider table relationships and constraints
                        • Format responses clearly with appropriate visualizations
                        • Be educational and explain your reasoning
                        • Ask clarifying questions when requests are ambiguous


                        {chat_context}

                        Remember: Be helpful, accurate, and always communicate respectfully in {system_lang}.
                        """

                        agent = Agent(
                            name="Assistant",
                            instructions=system_prompt,
                            model="gpt-4",
                        )
                        
                        result = Runner.run_streamed(agent, input=chat_input.query)
                        
                        async for event in result.stream_events():
                            if (event.type == "raw_response_event" and 
                                isinstance(event.data, ResponseTextDeltaEvent) and 
                                event.data.delta):
                                
                                ai_content_container["content"] += event.data.delta
                                result_queue.put(event.data.delta)
                        
                        result_queue.put(None)  # End signal
                    
                    loop.run_until_complete(do_streaming())
                    
                except Exception as e:
                    result_queue.put(f"Streaming Error: {str(e)}")
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
                        yield chunk
                    except queue.Empty:
                        yield "Connection timeout"
                        break
                
                # Tunggu task selesai
                future.result(timeout=5)
            
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
            yield f"Error: {str(e)}"
    
    return StreamingResponse(event_stream(), media_type="text/plain")


