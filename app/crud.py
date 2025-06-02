from sqlalchemy.orm import Session
from app import dependencies_auth, models, schemas

def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()

def get_user_by_username(db: Session, username: str):
    return db.query(models.User).filter(models.User.username == username).first()

def create_user(db: Session, user: schemas.UserCreate):
    hashed_password = dependencies_auth.get_password_hash(user.password)
    db_user = models.User(
        email=user.email,
        username=user.username,
        hashed_password=hashed_password
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def authenticate_user(db: Session, username: str, password: str):
    user = get_user_by_username(db, username)
    if not user:
        return False
    if not dependencies_auth.verify_password(password, user.hashed_password):
        return False
    return user

def create_chat(db: Session, chat: schemas.ChatCreate, user_id: int) -> models.Chat:
    db_chat = models.Chat(
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
        db.query(models.Chat)
        .filter(models.Chat.user_id == user_id)
        .order_by(models.Chat.created_at.desc())
        .limit(limit)
        .all()
    )

def get_all_chats_by_user(db: Session, user_id: int):
    return (
        db.query(models.Chat)
        .filter(models.Chat.user_id == user_id)
        .order_by(models.Chat.created_at.asc())
        .all()
    )

def delete_all_chats_by_user(db: Session, user_id: int):
    db.query(models.Chat).filter(models.Chat.user_id == user_id).delete()
    db.commit()