from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import logging
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.auth import require_candidate
from app.models.entities import User, Candidate, InterviewSession, JobDescription
from app.schemas.api_schemas import (
    CandidateApplicationResponse, FaceEnrollmentRequest
)
from app.services.document_parser import extract_document_text
from app.services.llm_service import llm_service
from app.services.identity_service import extract_face_region, decode_base64_image

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/candidate-portal", tags=["Candidate Portal"])

@router.get("/profile", response_model=CandidateApplicationResponse)
def get_candidate_profile(db: Session = Depends(get_db), user: User = Depends(require_candidate)):
    cand = db.query(Candidate).filter(Candidate.email == user.email).first()
    if not cand:
        cand = Candidate(user_id=user.id, full_name=user.full_name, email=user.email)
        db.add(cand)
        db.commit()
        db.refresh(cand)

    res = CandidateApplicationResponse.model_validate(cand)
    res.has_enrolled_face = bool(cand.enrolled_face_reference)
    return res

@router.post("/application")
async def submit_candidate_application(
    target_role: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_candidate)
):
    content = await file.read()
    raw_text = extract_document_text(file.filename, content)

    # LLM extraction of candidate profile
    sys_prompt = "Extract technical skills, work experience summary, and education from resume text. Return JSON with keys: extracted_skills (list of str), experience_summary (list of str), education (list of str)."
    profile_data = llm_service.invoke_structured(sys_prompt, raw_text)

    cand = db.query(Candidate).filter(Candidate.email == user.email).first()
    if not cand:
        cand = Candidate(
            user_id=user.id,
            full_name=user.full_name,
            email=user.email,
            target_role=target_role,
            resume_filename=file.filename,
            resume_raw_text=raw_text,
            extracted_skills=profile_data.get("extracted_skills", []),
            extracted_experience=profile_data.get("experience_summary", []),
            extracted_education=profile_data.get("education", [])
        )
        db.add(cand)
    else:
        cand.target_role = target_role
        cand.resume_filename = file.filename
        cand.resume_raw_text = raw_text
        cand.extracted_skills = profile_data.get("extracted_skills", [])
        cand.extracted_experience = profile_data.get("experience_summary", [])
        cand.extracted_education = profile_data.get("education", [])

    db.commit()
    db.refresh(cand)

    return {
        "message": "Application and resume submitted successfully. The system will match your profile for scheduling.",
        "candidate": CandidateApplicationResponse.model_validate(cand)
    }

@router.post("/enroll-face")
def enroll_candidate_face(
    req: FaceEnrollmentRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_candidate)
):
    """
    Enrolls the candidate's reference photo for pre-interview biometric verification.
    Validates that a single usable face is present, in focus, and verified through OpenCV.
    """
    try:
        cv_img = decode_base64_image(req.face_image_base64)
        if cv_img is None:
            raise HTTPException(status_code=400, detail="Invalid image encoding. Please ensure webcam feed is transmitting valid frames.")

        face_count, face_roi, meta = extract_face_region(cv_img)
        if face_count == 0:
            raise HTTPException(status_code=400, detail="No face detected in video frame. Please ensure your camera is positioned directly in front of your face with adequate lighting.")
        if face_count > 1:
            raise HTTPException(status_code=400, detail=f"Multiple faces detected ({face_count}). Only the registered candidate should appear in the camera frame.")
        if not meta.get("usable", False):
            raise HTTPException(status_code=400, detail="Image is too blurry or out of focus (sharpness score below threshold). Please hold steady and try again.")

        cand = db.query(Candidate).filter(Candidate.email == user.email).first()
        if not cand:
            cand = Candidate(user_id=user.id, full_name=user.full_name, email=user.email)
            db.add(cand)

        cand.enrolled_face_reference = req.face_image_base64
        cand.enrolled_at = datetime.utcnow()
        db.commit()

        return {
            "status": "success",
            "message": "Biometric face reference successfully enrolled with verified liveness indicators.",
            "metadata": {
                "stage": meta.get("stage", "reference_enrollment"),
                "face_count": int(meta.get("face_count", 1)),
                "usable": bool(meta.get("usable", True)),
                "eye_detected": bool(meta.get("eye_detected", False)),
                "sharpness_score": float(meta.get("sharpness_score", 0.0))
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during face enrollment: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal biometric processing error: {str(e)}")

@router.get("/interviews")
def list_candidate_interviews(db: Session = Depends(get_db), user: User = Depends(require_candidate)):
    cand = db.query(Candidate).filter(Candidate.email == user.email).first()
    if not cand:
        return []

    sessions = db.query(InterviewSession).filter(InterviewSession.candidate_id == cand.id).order_by(InterviewSession.created_at.desc()).all()
    results = []
    now = datetime.utcnow()

    for s in sessions:
        # Check window status
        window_status = "upcoming"
        if s.scheduled_start:
            from app.core.config import settings
            from datetime import timedelta
            early_start = s.scheduled_start - timedelta(minutes=settings.INTERVIEW_EARLY_ACCESS_MINUTES)
            window_end = s.scheduled_end or (s.scheduled_start + timedelta(minutes=settings.INTERVIEW_WINDOW_MINUTES))
            if now < early_start:
                window_status = "too_early"
            elif now > window_end:
                window_status = "expired"
            else:
                window_status = "open"

        results.append({
            "id": s.id,
            "session_token": s.session_token,
            "job_title": s.job_description.title,
            "status": s.status,
            "scheduled_start": s.scheduled_start,
            "scheduled_end": s.scheduled_end,
            "window_status": window_status,
            "identity_verified": s.identity_verified,
            "interview_url": f"/interview/{s.session_token}",
            "created_at": s.created_at
        })
    return results
