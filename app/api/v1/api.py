from fastapi import APIRouter

from app.api.v1.endpoints import auth, chat, preview

api_router = APIRouter()

# Include all endpoint routers (routers sudah punya prefix masing-masing)
api_router.include_router(auth.router, tags=["Authentication"])
api_router.include_router(preview.router, tags=["Preview"]) 
api_router.include_router(chat.router, tags=["Chat"])
