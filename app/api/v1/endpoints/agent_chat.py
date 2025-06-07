from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.dependencies_auth import get_current_user
from app.models.user import User
from app.schemas.chat import ChatResponse, ChatStreamInput
from app.services.agent_service import AgentService

router = APIRouter(prefix="/agent-chat", tags=["agent-chat"])

@router.post("/stream")
def stream_chat_agents_background(
    chat_input: ChatStreamInput,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):  
    # Initialize service
    agent_service = AgentService(db, current_user)
    
    # Use service to process streaming
    return StreamingResponse(
        agent_service.process_agent_streaming(chat_input.query), 
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@router.get("/list", response_model=list[ChatResponse])
def list_chats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    agent_service = AgentService(db, current_user)
    chats = agent_service.get_all_chats_by_user(current_user.id)
    return chats