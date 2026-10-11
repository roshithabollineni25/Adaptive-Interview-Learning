from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, EmailStr

# Auth & User schemas
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    role: str = "recruiter"  # recruiter or candidate

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    created_at: datetime

    class Config:
        from_attributes = True

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

# Candidate Application schemas
class CandidateApplicationResponse(BaseModel):
    id: int
    full_name: str
    email: str
    target_role: Optional[str]
    resume_filename: Optional[str]
    extracted_skills: List[Any] = []
    extracted_experience: List[Any] = []
    extracted_education: List[Any] = []
    enrolled_at: Optional[datetime] = None
    created_at: datetime
    has_enrolled_face: bool = False

    class Config:
        from_attributes = True

class FaceEnrollmentRequest(BaseModel):
    face_image_base64: str

# Job Description schemas
class JobDescriptionCreate(BaseModel):
    title: str
    department: Optional[str] = None
    raw_text: str
    experience_level: Optional[str] = "Mid-Senior"

class JobDescriptionResponse(BaseModel):
    id: int
    title: str
    department: Optional[str]
    raw_text: str
    required_competencies: List[Any] = []
    experience_level: str
    created_at: datetime

    class Config:
        from_attributes = True

# Scheduling schemas
class ScheduleInterviewRequest(BaseModel):
    candidate_id: int
    job_description_id: int
    scheduled_start: datetime

# Identity Verification Probe
class IdentityVerificationProbe(BaseModel):
    probe_frame_base64: str

# Interview Session schemas
class QuestionAnswerSubmit(BaseModel):
    answer_text: str

class IntegrityEventCreate(BaseModel):
    event_type: str
    severity: Optional[str] = "low"
    confidence: Optional[float] = 1.0
    metadata_info: Optional[Dict[str, Any]] = None

class RecruiterDecisionUpdate(BaseModel):
    recruiter_decision: str  # Hired, Rejected, Under Review
    recruiter_notes: Optional[str] = None

# Health check schema
class HealthCheckResponse(BaseModel):
    status: str
    project_name: str
    environment: str
    database_connected: bool
    llm_configured: bool
    timestamp: datetime
