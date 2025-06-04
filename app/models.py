from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from sqlalchemy import ForeignKey
from app.database import Base

# Untuk menjalankan migrasi dengan Alembic, ikuti langkah-langkah berikut:

# 1. Inisialisasi Alembic (jika belum):
# alembic init alembic

# 2. Buat file migrasi baru:
# alembic revision --autogenerate -m "deskripsi perubahan"

# 3. Jalankan migrasi:
# alembic upgrade head

# 4. Untuk rollback migrasi:
# alembic downgrade -1  # rollback 1 versi
# alembic downgrade base  # rollback ke awal

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class Chat(Base):
    __tablename__ = "chats"

    id = Column(Integer, primary_key=True, index=True)
    type = Column(String, nullable=False)
    content = Column(String, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

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