from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.dependencies_auth import get_current_user
from app.api.v1.api import api_router
from app.core.database import engine
from app.core.database import Base
from app.models.user import User

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="AI SQL Assistant",
    description="AI SQL Assistant",
    version="1.0.0"
)

# Configure CORS
origins = [
    "http://localhost",
    "http://localhost:3000",    # React default port
    "http://localhost:5173",    # Vite default port
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router with v1 prefix
app.include_router(api_router, prefix="/api/v1")

@app.get("/")
def root():
    return {"message": "FastAPI Authentication System"}

@app.get("/protected")
def protected_route(current_user: User = Depends(get_current_user)):
    return {"message": f"Hello {current_user.username}, this is a protected route!"}