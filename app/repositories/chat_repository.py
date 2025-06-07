from sqlalchemy.orm import Session

from app.models.chat import Chat
from app.schemas.chat import ChatCreate


def create_chat(db: Session, chat: ChatCreate, user_id: int) -> Chat:
    db_chat = Chat(
        type=chat.type,
        content=chat.content,
        user_id=user_id
    )
    db.add(db_chat)
    db.commit()
    db.refresh(db_chat)
    return db_chat

def get_last_chats_by_user(db: Session, user_id: int, limit: int = 20):
    return (
        db.query(Chat)
        .filter(Chat.user_id == user_id)
        .order_by(Chat.created_at.desc())
        .limit(limit)
        .all()
    )

def get_all_chats_by_user(db: Session, user_id: int):
    return (
        db.query(Chat)
        .filter(Chat.user_id == user_id)
        .order_by(Chat.created_at.asc())
        .all()
    )

def delete_all_chats_by_user(db: Session, user_id: int):
    db.query(Chat).filter(Chat.user_id == user_id).delete()
    db.commit()