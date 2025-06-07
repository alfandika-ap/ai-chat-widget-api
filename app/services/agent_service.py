import asyncio
import json
import time
import queue
from typing import Generator, Dict, Any, Optional
from sqlalchemy.orm import Session
from agents import Agent, Runner, function_tool
from openai.types.responses import ResponseTextDeltaEvent
from concurrent.futures import ThreadPoolExecutor

from app.models.query_store import QueryStore
from app.models.user import User
from app.schemas.chat import ChatCreate
from app.repositories.chat_repository import create_chat, get_all_chats_by_user, get_last_chats_by_user
from app.utils.generate_sql import generate_sql_from_natural_language
from app.utils.templates.chat_system_prompt import chat_system_prompt_template
from db_connection import DatabaseConnection


class AgentService:
    """Service for handling AI agent operations and streaming"""
    
    def __init__(self, db: Session, user: User):
        self.db = db
        self.user = user
        self._current_db = db
        self._current_user = user
    
    def get_all_chats_by_user(self, user_id: int):
        return get_all_chats_by_user(self.db, user_id)

    def create_stream_event(self, event_type: str, content: Any = None, **kwargs) -> str:
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
    
    def generate_system_prompt(self) -> str:
        """Generate system prompt with user context and schema"""
        schema_db = DatabaseConnection()
        schema_text = schema_db.get_schema_text()
        
        # Get recent conversation context
        last_chats = get_last_chats_by_user(self.db, self.user.id, limit=8)
        is_first_interaction = len(last_chats) == 0
        chat_context = ""
        
        if last_chats and not is_first_interaction:
            chat_entries = []
            for chat in last_chats[-8:]:
                role = "User" if chat.type == "user" else "Assistant"
                chat_entries.append(f"{role}: {chat.content[:150]}") 
            chat_context = "RECENT CONVERSATION HISTORY:\n" + "\n".join(chat_entries)

        # Generate system prompt dengan template
        data = {
            "full_name": self.user.full_name,
            "system_lang": "Bahasa Indonesia",
            "schema_text": schema_text,
            "chat_context": chat_context
        }
        
        template = chat_system_prompt_template
        for key, value in data.items():
            template = template.replace(f"{{{key}}}", value)
        
        return template
    
    def create_function_tools(self):
        """Create function tools with proper context"""
        
        @function_tool
        def show_query_store(question: str):
            """Generate SQL from natural language and store in QueryStore - ONLY return JSON format"""
            try:
                print(f"show_query_store: {question}")
                
                # Generate SQL from natural language
                sql_result = generate_sql_from_natural_language(question, self.user.id)
                
                # Create new QueryStore entry
                query_store = QueryStore(
                    user_id=self.user.id,
                    question=question,
                    generated_sql=sql_result.get("generated_sql", ""),
                    response_type=sql_result.get("response_type", ""),
                    answer_template=sql_result.get("answer_template", ""),
                    display_type=sql_result.get("response_type", "")
                )
                
                self.db.add(query_store)
                self.db.commit()
                self.db.refresh(query_store)

                # Return JSON format
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
        
        return [show_query_store]
    
    def save_user_message(self, content: str):
        """Save user message to database"""
        create_chat(
            db=self.db,
            chat=ChatCreate(type="user", content=content),
            user_id=self.user.id
        )
    
    def save_assistant_message(self, content: str):
        """Save assistant message to database"""
        if content.strip():
            create_chat(
                db=self.db,
                chat=ChatCreate(type="assistant", content=content),
                user_id=self.user.id
            )
    
    def process_agent_streaming(self, query: str) -> Generator[str, None, None]:
        """Main method for processing agent streaming with proper separation of concerns"""
        try:
            yield self.create_stream_event("start", {"message": "Starting chat processing"})
            
            # Save user message
            self.save_user_message(query)
            
            # Setup untuk streaming
            result_queue = queue.Queue()
            ai_content_container = {"content": ""}
            tool_used = {"used": False}
            
            def async_stream_task():
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    
                    async def do_streaming():
                        # Generate system prompt
                        system_prompt = self.generate_system_prompt()
                        
                        # Create function tools
                        function_tools = self.create_function_tools()
                        
                        # Run agent
                        agent = Agent(
                            name="Assistant",
                            instructions=system_prompt,
                            model="gpt-4o",
                            tools=function_tools
                        )
                        
                        result = Runner.run_streamed(agent, input=query)
                        
                        async for event in result.stream_events():
                            # Handle text delta
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
                                    ai_content_container["content"] = ""
                                    
                                    result_queue.put({
                                        "type": "tool_call_start",
                                        "tool_name": getattr(event.item, "name", "unknown"),
                                        "tool_id": getattr(event.item, "id", None),
                                        "arguments": getattr(event.item, "arguments", {}),
                                    })
                                    
                                elif event.item.type == "tool_call_output_item":
                                    tool_output = event.item.output
                                    ai_content_container["content"] = tool_output
                                    
                                    result_queue.put({
                                        "type": "tool_call_result", 
                                        "content": tool_output
                                    })
                        
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
                        
                        if isinstance(chunk, dict):
                            yield json.dumps(chunk, ensure_ascii=False) + "\n"
                        else:
                            yield self.create_stream_event("text", chunk)
                            
                    except queue.Empty:
                        yield self.create_stream_event("error", "Connection timeout", error_code="TIMEOUT")
                        break
                
                # Tunggu task selesai
                try:
                    future.result(timeout=5)
                except Exception as e:
                    print(f"Future result error: {str(e)}")
                    
                # Save assistant response
                self.save_assistant_message(ai_content_container["content"])
            
            # Send final end event
            yield self.create_stream_event("end", {"message": "Stream completed"})
            
        except Exception as e:
            print(f"General error: {str(e)}")
            yield self.create_stream_event("error", str(e), error_code="GENERAL_ERROR") 
