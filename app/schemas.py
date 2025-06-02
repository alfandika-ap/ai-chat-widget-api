from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional

# Schema untuk registrasi
class UserCreate(BaseModel):
    email: EmailStr
    username: str
    password: str

# Schema untuk login
class UserLogin(BaseModel):
    username: str
    password: str

# Schema untuk response user
class UserResponse(BaseModel):
    id: int
    email: str
    username: str
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# Schema untuk token
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class ChatCreate(BaseModel):
    type: str
    content: str

class ChatResponse(BaseModel):
    id: int
    type: str
    content: str
    user_id: int

    class Config:
        orm_mode = True