from sqlalchemy import Column, ForeignKey, Integer, String, DateTime
from sqlalchemy.sql import func
from app.core.database import Base

class QueryStore(Base):
    __tablename__ = "query_store" 

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    question = Column(String, nullable=True, default="")
    generated_sql = Column(String, nullable=True, default="")
    response_type = Column(String, nullable=True, default="")
    answer_template = Column(String, nullable=True, default="")
    display_type = Column(String, nullable=True, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())