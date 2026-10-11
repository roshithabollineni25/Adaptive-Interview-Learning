from typing import Dict, Any
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.database import get_db
from app.core.config import settings
from app.api.auth import require_recruiter
from app.models.entities import User

router = APIRouter(prefix="/system", tags=["System Diagnostics"])

@router.get("/status")
def get_system_status(db: Session = Depends(get_db), user: User = Depends(require_recruiter)) -> Dict[str, Any]:
    """Protected recruiter diagnostic endpoint reporting honest LLM & database status."""
    db_connected = False
    try:
        db.execute(text("SELECT 1"))
        db_connected = True
    except Exception:
        db_connected = False

    import os
    gemini_key = settings.GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY")
    is_gemini_configured = bool(settings.LLM_PROVIDER == "gemini" and gemini_key and gemini_key.strip() and gemini_key != "your_gemini_api_key_here")
    openai_key = settings.OPENAI_API_KEY or os.environ.get("OPENAI_API_KEY")
    is_openai_configured = bool(settings.LLM_PROVIDER == "openai" and openai_key and openai_key.strip() and openai_key != "your_openai_api_key_here")
    llm_active = is_gemini_configured or is_openai_configured

    active_model = settings.GEMINI_MODEL if settings.LLM_PROVIDER == "gemini" else settings.OPENAI_MODEL

    return {
        "database_connected": db_connected,
        "llm_provider": settings.LLM_PROVIDER,
        "llm_configured": llm_active,
        "llm_model": active_model,
        "llm_status_message": (
            f"Active: Configured for {settings.LLM_PROVIDER.upper()} ({active_model})"
            if llm_active
            else "No active LLM API key configured in backend/.env. Engine is running in algorithmic fallback mode. Configure GEMINI_API_KEY in backend/.env to activate real LLM evaluations."
        )
    }
