from pydantic import BaseModel


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

class TestChat(BaseModel):
    query: str

class ChatStreamInput(BaseModel):
    query: str