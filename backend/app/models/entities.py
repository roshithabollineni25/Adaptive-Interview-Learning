import enum
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, ForeignKey, 
    Enum, Float, JSON, Boolean
)
from sqlalchemy.orm import relationship
from app.core.database import Base

class UserRole(str, enum.Enum):
    RECRUITER = "recruiter"
    ADMIN = "admin"
    CANDIDATE = "candidate"

class InterviewStatus(str, enum.Enum):
    SETUP = "setup"
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    EVALUATED = "evaluated"

class IntegrityEventType(str, enum.Enum):
    TAB_SWITCH = "tab_switch"
    WINDOW_BLUR = "window_blur"
    PASTE_DETECTED = "paste_detected"
    FULLSCREEN_EXIT = "fullscreen_exit"
    FACE_NOT_VISIBLE = "face_not_visible"
    MULTIPLE_FACES = "multiple_faces"
    CAMERA_INTERRUPTED = "camera_interrupted"
    DISCONNECT = "disconnect"
    RECONNECT = "reconnect"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), default=UserRole.RECRUITER, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    interviews_as_recruiter = relationship("InterviewSession", back_populates="recruiter", foreign_keys="InterviewSession.recruiter_id")
    candidate_profile = relationship("Candidate", back_populates="user", uselist=False)

class JobDescription(Base):
    __tablename__ = "job_descriptions"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    department = Column(String(255), nullable=True)
    raw_text = Column(Text, nullable=False)
    required_competencies = Column(JSON, default=list)  # list of strings/objects
    experience_level = Column(String(100), default="Mid-Senior")
    created_at = Column(DateTime, default=datetime.utcnow)

    interviews = relationship("InterviewSession", back_populates="job_description")

class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # link to candidate user
    full_name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    target_role = Column(String(255), nullable=True)
    resume_filename = Column(String(255), nullable=True)
    resume_raw_text = Column(Text, nullable=True)
    extracted_skills = Column(JSON, default=list)
    extracted_experience = Column(JSON, default=list)
    extracted_education = Column(JSON, default=list)
    
    # Biometric enrollment reference
    enrolled_face_reference = Column(Text, nullable=True)  # Base64 encoded reference face thumbnail
    enrolled_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="candidate_profile")
    interviews = relationship("InterviewSession", back_populates="candidate")

    @property
    def has_enrolled_face(self) -> bool:
        return bool(self.enrolled_face_reference and str(self.enrolled_face_reference).strip())

class InterviewSession(Base):
    __tablename__ = "interview_sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_token = Column(String(100), unique=True, index=True, nullable=False)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False)
    job_description_id = Column(Integer, ForeignKey("job_descriptions.id"), nullable=False)
    recruiter_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    status = Column(Enum(InterviewStatus), default=InterviewStatus.SETUP, nullable=False)
    
    # Scheduling & Window enforcement
    scheduled_start = Column(DateTime, nullable=True)
    scheduled_end = Column(DateTime, nullable=True)
    invitation_sent_at = Column(DateTime, nullable=True)
    invitation_email_status = Column(String(50), default="pending")  # sent, failed, simulated
    
    # Identity Verification Gate
    identity_verified = Column(Boolean, default=False)
    identity_verification_details = Column(JSON, nullable=True)
    identity_verified_at = Column(DateTime, nullable=True)
    
    current_question_index = Column(Integer, default=0)
    current_difficulty = Column(String(50), default="Medium")  # Easy, Medium, Hard, Recovery
    
    # Final hiring decision and evaluation
    final_score = Column(Float, nullable=True)
    final_recommendation = Column(String(100), nullable=True)  # Strong Hire, Hire, Lean No, No Hire
    recruiter_decision = Column(String(100), nullable=True)    # Selected (Hired), Rejected, Under Review (Pending), On Hold
    recruiter_notes = Column(Text, nullable=True)             # Confidential internal recruiter notes
    candidate_feedback = Column(Text, nullable=True)          # Optional approved candidate-facing feedback
    decision_at = Column(DateTime, nullable=True)             # Timestamp when recruiter recorded decision
    decision_notification_status = Column(String(50), nullable=True) # accepted, delivered, delivery_failed, configuration_required
    decision_notification_error = Column(Text, nullable=True)        # Safe diagnostic details of notification outcome

    # Reports
    skill_gap_analysis = Column(JSON, nullable=True)
    evidence_report = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    candidate = relationship("Candidate", back_populates="interviews")
    job_description = relationship("JobDescription", back_populates="interviews")
    recruiter = relationship("User", back_populates="interviews_as_recruiter", foreign_keys=[recruiter_id])
    questions = relationship("InterviewQuestion", back_populates="session", cascade="all, delete-orphan")
    integrity_events = relationship("IntegrityEvent", back_populates="session", cascade="all, delete-orphan")

class InterviewQuestion(Base):
    __tablename__ = "interview_questions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("interview_sessions.id"), nullable=False)
    order_index = Column(Integer, nullable=False)
    question_text = Column(Text, nullable=False)
    competency_tested = Column(String(255), nullable=False)
    difficulty_level = Column(String(50), nullable=False)  # Easy, Medium, Hard, Recovery
    expected_criteria = Column(Text, nullable=True)
    
    candidate_answer = Column(Text, nullable=True)
    answered_at = Column(DateTime, nullable=True)
    
    # Question format & answer modes (Priority 4)
    question_type = Column(String(50), default="open_ended")  # open_ended, multiple_choice, fill_blank
    options = Column(JSON, nullable=True)                     # List of choices for multiple_choice
    answer_mode = Column(String(50), default="typed")         # typed, voice_transcript, option_selected
    voice_transcript = Column(Text, nullable=True)            # Original voice-to-text transcript if voice used
    
    # Adaptive Assessment
    score = Column(Float, nullable=True)  # 0 to 10
    rubric_scores = Column(JSON, nullable=True)  # {technical: 8, clarity: 7, depth: 8}
    strengths = Column(JSON, default=list)
    weaknesses = Column(JSON, default=list)
    evidence_quote = Column(Text, nullable=True)
    confidence_level = Column(String(50), default="High")  # High, Moderate, Uncertain
    adaptation_reason = Column(Text, nullable=True)

    session = relationship("InterviewSession", back_populates="questions")

class IntegrityEvent(Base):
    __tablename__ = "integrity_events"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("interview_sessions.id"), nullable=False)
    event_type = Column(String(100), nullable=False)
    severity = Column(String(50), default="low")  # low, medium, high
    confidence = Column(Float, nullable=True)
    metadata_info = Column(JSON, nullable=True)
    screenshot_base64 = Column(Text, nullable=True)  # Snapshot capture for qualifying integrity incidents
    timestamp = Column(DateTime, default=datetime.utcnow)

    session = relationship("InterviewSession", back_populates="integrity_events")
