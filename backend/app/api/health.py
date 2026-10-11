from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.database import get_db
from app.core.config import settings
from app.schemas.api_schemas import HealthCheckResponse

router = APIRouter(tags=["Health"])

@router.get("/health", response_model=HealthCheckResponse)
def health_check(db: Session = Depends(get_db)):
    db_connected = False
    try:
        # Simple ping query
        db.execute(text("SELECT 1"))
        db_connected = True
    except Exception:
        db_connected = False

    llm_ready = bool(
        (settings.LLM_PROVIDER == "gemini" and settings.GEMINI_API_KEY) or
        (settings.LLM_PROVIDER == "openai" and settings.OPENAI_API_KEY)
    )

    return HealthCheckResponse(
        status="healthy" if db_connected else "degraded",
        project_name=settings.PROJECT_NAME,
        environment=settings.ENVIRONMENT,
        database_connected=db_connected,
        llm_configured=llm_ready,
        timestamp=datetime.utcnow()
    )
