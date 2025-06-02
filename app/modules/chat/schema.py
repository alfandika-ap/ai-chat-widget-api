from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional

class TestChat(BaseModel):
    query: str

class ChatStreamInput(BaseModel):
    query: str