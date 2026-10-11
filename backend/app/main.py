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

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure tables exist in database (PostgreSQL or SQLite) on startup
    Base.metadata.create_all(bind=engine)
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
    "https://adaptive-interview-learning.onrender.com"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"https://.*\.onrender\.com",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
