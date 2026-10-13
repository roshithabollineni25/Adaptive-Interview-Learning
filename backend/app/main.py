from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import engine, Base
from app.api.health import router as health_router
from app.api.auth import router as auth_router
from app.api.recruitment import router as recruitment_router, interview_router
from app.api.candidate_portal import router as candidate_portal_router
from app.api.system import router as system_router

from sqlalchemy import inspect, text

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure tables exist in database (PostgreSQL or SQLite) on startup
    Base.metadata.create_all(bind=engine)
    
    # Auto-migrate any newly introduced columns to existing database tables safely
    try:
        with engine.connect() as conn:
            inspector = inspect(engine)
            if "interview_sessions" in inspector.get_table_names():
                existing_cols = {c["name"] for c in inspector.get_columns("interview_sessions")}
                new_columns = [
                    ("candidate_feedback", "TEXT"),
                    ("decision_at", "TIMESTAMP"),
                    ("decision_notification_status", "VARCHAR(50)"),
                    ("decision_notification_error", "TEXT"),
                ]
                for col_name, col_type in new_columns:
                    if col_name not in existing_cols:
                        conn.execute(text(f"ALTER TABLE interview_sessions ADD COLUMN {col_name} {col_type};"))
                        conn.commit()
            if "interview_questions" in inspector.get_table_names():
                existing_q_cols = {c["name"] for c in inspector.get_columns("interview_questions")}
                new_q_columns = [
                    ("question_type", "VARCHAR(50) DEFAULT 'open_ended'"),
                    ("options", "JSON"),
                    ("answer_mode", "VARCHAR(50) DEFAULT 'typed'"),
                    ("voice_transcript", "TEXT"),
                ]
                for col_name, col_type in new_q_columns:
                    if col_name not in existing_q_cols:
                        conn.execute(text(f"ALTER TABLE interview_questions ADD COLUMN {col_name} {col_type};"))
                        conn.commit()
    except Exception as mig_err:
        import logging
        logging.getLogger("uvicorn.error").warning(f"Database auto-migration warning: {mig_err}")

    # Idempotently seed default demo accounts for recruiter and candidate if not already present
    try:
        from app.core.database import SessionLocal
        from app.models.entities import User, UserRole, Candidate
        from app.core.security import get_password_hash
        
        with SessionLocal() as db:
            # Demo Recruiter
            demo_rec = db.query(User).filter(User.email == "demo.recruiter@adaptiveinterview.io").first()
            if not demo_rec:
                demo_rec = User(
                    email="demo.recruiter@adaptiveinterview.io",
                    hashed_password=get_password_hash("DemoRecruiter123!"),
                    full_name="Lead Technical Recruiter (Demo)",
                    role=UserRole.RECRUITER
                )
                db.add(demo_rec)
                db.commit()

            # Demo Candidate
            demo_cand = db.query(User).filter(User.email == "demo.candidate@adaptiveinterview.io").first()
            if not demo_cand:
                demo_cand = User(
                    email="demo.candidate@adaptiveinterview.io",
                    hashed_password=get_password_hash("DemoCandidate123!"),
                    full_name="Alex Rivera (Demo Candidate)",
                    role=UserRole.CANDIDATE
                )
                db.add(demo_cand)
                db.commit()
                cand_profile = Candidate(
                    user_id=demo_cand.id,
                    full_name="Alex Rivera",
                    email="demo.candidate@adaptiveinterview.io",
                    target_role="Full Stack Distributed Systems Engineer",
                    extracted_skills=["Python", "FastAPI", "React", "PostgreSQL", "System Architecture"]
                )
                db.add(cand_profile)
                db.commit()
    except Exception as seed_err:
        import logging
        logging.getLogger("uvicorn.error").warning(f"Demo accounts seeding warning: {seed_err}")

    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Full-stack Adaptive Interview Intelligence application with persistent database, real LLM evaluation, and candidate experience.",
    version="1.0.0",
    lifespan=lifespan
)

# CORS setup for frontend
allowed_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://adaptive-interview-frontend-b2ol.onrender.com",
    "https://adaptive-interview-learning.onrender.com",
]
if settings.frontend_origin and settings.frontend_origin not in allowed_origins:
    allowed_origins.append(settings.frontend_origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"^https://.*\.onrender\.com$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Register routers under /api
app.include_router(health_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(recruitment_router, prefix="/api")
app.include_router(interview_router, prefix="/api")
app.include_router(candidate_portal_router, prefix="/api")
app.include_router(system_router, prefix="/api")

@app.get("/")
def root():
    return {
        "message": "Welcome to Adaptive Interview Intelligence API",
        "docs_url": "/docs",
        "health_check": "/api/health"
    }
