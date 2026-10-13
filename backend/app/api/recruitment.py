import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.core.database import get_db
from app.core.config import settings
from app.api.auth import require_recruiter
from app.models.entities import (
    User, JobDescription, Candidate, InterviewSession,
    InterviewQuestion, IntegrityEvent, InterviewStatus
)
from app.schemas.api_schemas import (
    JobDescriptionCreate, JobDescriptionResponse,
    CandidateApplicationResponse, ScheduleInterviewRequest,
    RescheduleInterviewRequest,
    QuestionAnswerSubmit, IntegrityEventCreate,
    RecruiterDecisionUpdate, IdentityVerificationProbe
)
from app.services.document_parser import extract_document_text
from app.services.llm_service import llm_service
from app.services.email_service import email_service
from app.services.interview_engine import interview_engine
from app.services.identity_service import compare_faces, verify_id_card_document

router = APIRouter(prefix="/recruitment", tags=["Recruitment"])

# ----------------- JOB ROLES -----------------
@router.post("/jobs", response_model=JobDescriptionResponse)
def create_job(job_in: JobDescriptionCreate, db: Session = Depends(get_db), user: User = Depends(require_recruiter)):
    system_prompt = "Extract key competencies with weights from this job description. Return JSON with 'competencies': [{'name': str, 'weight': float, 'description': str}]."
    llm_res = llm_service.invoke_structured(system_prompt, job_in.raw_text)
    competencies = llm_res.get("competencies", [])

    job = JobDescription(
        title=job_in.title,
        department=job_in.department,
        raw_text=job_in.raw_text,
        experience_level=job_in.experience_level,
        required_competencies=competencies
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job

@router.get("/jobs", response_model=List[JobDescriptionResponse])
def list_jobs(db: Session = Depends(get_db), user: User = Depends(require_recruiter)):
    return db.query(JobDescription).order_by(JobDescription.created_at.desc()).all()

# ----------------- CANDIDATES -----------------
@router.get("/candidates")
def list_candidates(db: Session = Depends(get_db), user: User = Depends(require_recruiter)):
    cands = db.query(Candidate).order_by(Candidate.created_at.desc()).all()
    results = []
    for c in cands:
        results.append({
            "id": c.id,
            "full_name": c.full_name,
            "email": c.email,
            "target_role": c.target_role,
            "resume_filename": c.resume_filename,
            "extracted_skills": c.extracted_skills,
            "extracted_experience": c.extracted_experience,
            "extracted_education": c.extracted_education,
            "has_enrolled_face": bool(c.enrolled_face_reference),
            "enrolled_at": c.enrolled_at,
            "created_at": c.created_at
        })
    return results

# ----------------- SCHEDULING INTERVIEWS -----------------
@router.post("/sessions/schedule")
def schedule_interview_session(
    req: ScheduleInterviewRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_recruiter)
):
    result = interview_engine.schedule_session(
        candidate_id=req.candidate_id,
        job_description_id=req.job_description_id,
        recruiter_id=user.id,
        scheduled_start=req.scheduled_start,
        db=db
    )
    session = result["session"]
    return {
        "session_id": session.id,
        "session_token": session.session_token,
        "status": session.status,
        "scheduled_start": session.scheduled_start,
        "interview_link": f"/interview/{session.session_token}",
        "email_delivery": result["email_delivery"]
    }

@router.get("/sessions")
def list_sessions(db: Session = Depends(get_db), user: User = Depends(require_recruiter)):
    sessions = db.query(InterviewSession).order_by(InterviewSession.created_at.desc()).all()
    results = []
    for s in sessions:
        cand_name = s.candidate.full_name if s.candidate else "Unknown Candidate"
        cand_email = s.candidate.email if s.candidate else ""
        job_name = s.job_description.title if s.job_description else "Unassigned Position"
        status_val = s.status.value if hasattr(s.status, "value") else str(s.status)

        results.append({
            "id": s.id,
            "session_token": s.session_token,
            "candidate_name": cand_name,
            "candidate_email": cand_email,
            "job_title": job_name,
            "status": status_val,
            "scheduled_start": s.scheduled_start,
            "scheduled_end": s.scheduled_end,
            "invitation_email_status": s.invitation_email_status,
            "identity_verified": bool(s.identity_verified),
            "final_score": s.final_score,
            "final_recommendation": s.final_recommendation,
            "recruiter_decision": s.recruiter_decision,
            "created_at": s.created_at,
            "questions_count": len(s.questions) if s.questions else 0,
            "integrity_events_count": len(s.integrity_events) if s.integrity_events else 0
        })
    return results

@router.get("/sessions/{session_id}")
def get_session_detail(session_id: int, db: Session = Depends(get_db), user: User = Depends(require_recruiter)):
    s = db.query(InterviewSession).filter(InterviewSession.id == session_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Interview session not found")
    
    questions_data = []
    for q in s.questions:
        questions_data.append({
            "id": q.id,
            "order_index": q.order_index,
            "question_text": q.question_text,
            "competency_tested": q.competency_tested,
            "difficulty_level": q.difficulty_level,
            "question_type": getattr(q, "question_type", "open_ended") or "open_ended",
            "options": getattr(q, "options", []) or [],
            "answer_mode": getattr(q, "answer_mode", "typed") or "typed",
            "voice_transcript": getattr(q, "voice_transcript", None),
            "candidate_answer": q.candidate_answer,
            "score": q.score,
            "rubric_scores": q.rubric_scores,
            "strengths": q.strengths,
            "weaknesses": q.weaknesses,
            "evidence_quote": q.evidence_quote,
            "confidence_level": q.confidence_level,
            "adaptation_reason": q.adaptation_reason,
            "answered_at": q.answered_at
        })

    integrity_data = []
    for ev in s.integrity_events:
        integrity_data.append({
            "id": ev.id,
            "event_type": ev.event_type,
            "severity": ev.severity,
            "confidence": ev.confidence,
            "metadata_info": ev.metadata_info,
            "timestamp": ev.timestamp
        })

    status_val = s.status.value if hasattr(s.status, "value") else str(s.status)

    if s.job_description:
        try:
            job_data = JobDescriptionResponse.model_validate(s.job_description).model_dump()
        except Exception:
            job_data = {
                "id": s.job_description.id,
                "title": s.job_description.title or "Unassigned Position",
                "department": s.job_description.department,
                "raw_text": s.job_description.raw_text or "",
                "required_competencies": s.job_description.required_competencies or [],
                "experience_level": s.job_description.experience_level or "Mid-Senior",
                "created_at": s.job_description.created_at or s.created_at
            }
    else:
        job_data = {
            "id": s.job_description_id or 0,
            "title": "Unassigned Position",
            "department": None,
            "raw_text": "",
            "required_competencies": [],
            "experience_level": "Mid-Senior",
            "created_at": s.created_at
        }

    if (status_val == "completed" or s.status == InterviewStatus.COMPLETED) and not s.evidence_report:
        try:
            interview_engine.finalize_interview(s, db)
            db.refresh(s)
        except Exception as e:
            logger.warning(f"Could not auto-finalize report for completed session {session_id}: {e}")

    return {
        "id": s.id,
        "session_token": s.session_token,
        "status": status_val,
        "scheduled_start": s.scheduled_start,
        "scheduled_end": s.scheduled_end,
        "invitation_email_status": s.invitation_email_status,
        "identity_verified": bool(s.identity_verified),
        "identity_verification_details": s.identity_verification_details,
        "current_difficulty": s.current_difficulty,
        "final_score": s.final_score,
        "final_recommendation": s.final_recommendation,
        "recruiter_decision": s.recruiter_decision,
        "recruiter_notes": s.recruiter_notes,
        "candidate_feedback": getattr(s, "candidate_feedback", None),
        "decision_at": getattr(s, "decision_at", None),
        "decision_notification_status": getattr(s, "decision_notification_status", None),
        "decision_notification_error": getattr(s, "decision_notification_error", None),
        "skill_gap_analysis": s.skill_gap_analysis,
        "evidence_report": s.evidence_report,
        "candidate": {
            "id": s.candidate.id if s.candidate else s.candidate_id,
            "full_name": s.candidate.full_name if s.candidate else "Unknown Candidate",
            "email": s.candidate.email if s.candidate else "",
            "target_role": s.candidate.target_role if s.candidate else None,
            "extracted_skills": s.candidate.extracted_skills if s.candidate and s.candidate.extracted_skills else [],
            "has_enrolled_face": bool(s.candidate.enrolled_face_reference) if s.candidate else False
        },
        "job": job_data,
        "questions": questions_data,
        "integrity_events": integrity_data
    }

@router.patch("/sessions/{session_id}/decision")
def update_recruiter_decision(
    session_id: int, 
    decision_data: RecruiterDecisionUpdate, 
    db: Session = Depends(get_db), 
    user: User = Depends(require_recruiter)
):
    session = db.query(InterviewSession).filter(InterviewSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Interview session not found")

    old_decision = session.recruiter_decision
    new_decision = decision_data.recruiter_decision.strip()

    session.recruiter_decision = new_decision
    session.decision_at = datetime.utcnow()
    if decision_data.recruiter_notes is not None:
        session.recruiter_notes = decision_data.recruiter_notes
    if decision_data.candidate_feedback is not None:
        session.candidate_feedback = decision_data.candidate_feedback

    # Send decision email if decision changed or notification not yet accepted
    email_delivery_report = None
    candidate = session.candidate
    job = session.job_description

    # Only send email when candidate exists and either decision changed or notification hasn't been accepted yet
    should_send_email = candidate and (
        old_decision != new_decision or getattr(session, "decision_notification_status", None) != "accepted"
    )

    if should_send_email:
        try:
            email_res = email_service.send_hiring_decision_notification(
                candidate_email=candidate.email,
                candidate_name=candidate.full_name,
                job_title=job.title if job else "Target Position",
                decision=new_decision,
                candidate_feedback=getattr(session, "candidate_feedback", None)
            )
            session.decision_notification_status = email_res.get("status", "pending")
            session.decision_notification_error = email_res.get("message")
            email_delivery_report = email_res
        except Exception as mail_err:
            logger.error(f"Error executing email notification: {mail_err}")
            session.decision_notification_status = "delivery_failed"
            session.decision_notification_error = str(mail_err)
            email_delivery_report = {
                "status": "delivery_failed",
                "delivered": False,
                "message": f"Email dispatch failed: {str(mail_err)}"
            }
    else:
        email_delivery_report = {
            "status": getattr(session, "decision_notification_status", None) or "unchanged",
            "delivered": getattr(session, "decision_notification_status", None) == "accepted",
            "message": "Decision unchanged; email notification previously processed."
        }

    try:
        # Persist the decision in database
        db.commit()
        db.refresh(session)
    except Exception as db_err:
        db.rollback()
        logger.error(f"Failed to persist recruiter decision: {db_err}")
        raise HTTPException(status_code=500, detail=f"Database error saving decision: {str(db_err)}")

    return {
        "message": f"Hiring decision '{new_decision}' successfully recorded in database.",
        "decision": session.recruiter_decision,
        "decision_at": getattr(session, "decision_at", None),
        "candidate_feedback": getattr(session, "candidate_feedback", None),
        "email_delivery": email_delivery_report
    }

@router.patch("/sessions/{session_id}/reschedule")
def reschedule_interview_session(
    session_id: int,
    reschedule_data: RescheduleInterviewRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_recruiter)
):
    session = db.query(InterviewSession).filter(InterviewSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Interview session not found")

    if session.status == InterviewStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Cannot reschedule a completed interview session.")

    new_start = reschedule_data.new_scheduled_start
    if new_start.tzinfo is not None:
        new_start = new_start.astimezone(timezone.utc).replace(tzinfo=None)
    else:
        # If naive datetime provided, treat as Asia/Kolkata (IST UTC+05:30) and convert to UTC
        ist_tz = timezone(timedelta(hours=5, minutes=30))
        new_start = new_start.replace(tzinfo=ist_tz).astimezone(timezone.utc).replace(tzinfo=None)

    now = datetime.utcnow()
    # Permit scheduling with small grace margin (e.g. 2 minutes in past) but reject clearly past dates
    if new_start < now - timedelta(minutes=2):
        raise HTTPException(status_code=400, detail="New scheduled start time cannot be in the past.")

    session.scheduled_start = new_start
    session.scheduled_end = new_start + timedelta(minutes=settings.INTERVIEW_WINDOW_MINUTES)
    session.status = InterviewStatus.SCHEDULED
    # Reset identity verification gate for the new rescheduled session window
    session.identity_verified = False
    session.identity_verified_at = None

    # Send rescheduled notification to candidate
    candidate = session.candidate
    job = session.job_description
    email_res = email_service.send_interview_rescheduled(
        candidate_email=candidate.email,
        candidate_name=candidate.full_name,
        job_title=job.title,
        new_scheduled_start=new_start,
        session_token=session.session_token
    )

    session.invitation_email_status = email_res.get("status", "pending")
    db.commit()
    db.refresh(session)

    return {
        "message": "Interview session successfully rescheduled.",
        "session_id": session.id,
        "scheduled_start": session.scheduled_start,
        "scheduled_end": session.scheduled_end,
        "status": session.status,
        "email_delivery": email_res
    }

@router.delete("/sessions/{session_id}")
def delete_interview_session(
    session_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_recruiter)
):
    session = db.query(InterviewSession).filter(InterviewSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Interview session not found")

    # If the session was completed with evaluated report data, prevent accidental loss of audit history
    # or handle cleanly. For scheduled/in-progress or non-final sessions, remove session and cascade-orphans.
    cand_name = session.candidate.full_name if session.candidate else "Candidate"
    job_title = session.job_description.title if session.job_description else "Position"

    db.delete(session)
    db.commit()

    return {
        "message": f"Interview session for {cand_name} ({job_title}) was successfully deleted.",
        "session_id": session_id
    }

# ----------------- CANDIDATE INTERVIEW EXPERIENCE -----------------
interview_router = APIRouter(prefix="/interview", tags=["Candidate Interview"])

@interview_router.get("/{token}")
def get_candidate_interview(token: str, db: Session = Depends(get_db)):
    session = db.query(InterviewSession).filter(InterviewSession.session_token == token).first()
    if not session:
        raise HTTPException(status_code=404, detail="Interview session not found or invalid link")

    time_check = interview_engine.verify_time_window(session)

    # Active pending question with automatic reload recovery
    active_question = None
    if session.identity_verified and session.status in ["in_progress", "setup"]:
        for q in session.questions:
            if q.candidate_answer is None:
                active_question = {
                    "id": q.id,
                    "order_index": q.order_index,
                    "question_text": q.question_text,
                    "competency_tested": q.competency_tested,
                    "difficulty_level": q.difficulty_level,
                    "question_type": getattr(q, "question_type", "open_ended") or "open_ended",
                    "options": getattr(q, "options", []) or []
                }
                break

        # Reload Recovery: If in progress and all existing questions are answered but total < max, generate next question!
        if not active_question and session.status == "in_progress" and len(session.questions) < settings.MAX_QUESTIONS_PER_SESSION:
            next_q = interview_engine.generate_next_question(session, db)
            active_question = {
                "id": next_q.id,
                "order_index": next_q.order_index,
                "question_text": next_q.question_text,
                "competency_tested": next_q.competency_tested,
                "difficulty_level": next_q.difficulty_level,
                "question_type": getattr(next_q, "question_type", "open_ended") or "open_ended",
                "options": getattr(next_q, "options", []) or []
            }

    return {
        "session_token": session.session_token,
        "status": session.status,
        "scheduled_start": session.scheduled_start,
        "scheduled_end": session.scheduled_end,
        "time_window_check": time_check,
        "candidate_name": session.candidate.full_name,
        "has_enrolled_reference": bool(session.candidate.enrolled_face_reference),
        "identity_verified": session.identity_verified,
        "job_title": session.job_description.title,
        "total_questions_completed": len([q for q in session.questions if q.candidate_answer is not None]),
        "active_question": active_question
    }

@interview_router.post("/{token}/verify-identity")
def verify_candidate_identity(token: str, probe: IdentityVerificationProbe, db: Session = Depends(get_db)):
    session = db.query(InterviewSession).filter(InterviewSession.session_token == token).first()
    if not session:
        raise HTTPException(status_code=404, detail="Interview session not found")

    # Time window check
    time_check = interview_engine.verify_time_window(session)
    if not time_check["allowed"]:
        raise HTTPException(status_code=403, detail=time_check["reason"])

    candidate = session.candidate
    if not candidate.enrolled_face_reference:
        raise HTTPException(
            status_code=400, 
            detail="Candidate has not enrolled an identity reference. Please complete identity enrollment in the Candidate Portal first."
        )

    # Mandatory ID card requirement (Priority 2)
    if not probe.id_card_frame_base64 or not str(probe.id_card_frame_base64).strip():
        return {
            "verified": False,
            "message": "Physical ID card document capture is required before starting the interview.",
            "similarity_score": 0.0,
            "stage": "id_card_verification"
        }

    # Run genuine face verification against enrolled reference
    result = compare_faces(candidate.enrolled_face_reference, probe.probe_frame_base64)
    
    if not result["verified"]:
        # Record verification failure event in integrity log
        ev = IntegrityEvent(
            session_id=session.id,
            event_type="identity_verification_failed",
            severity="high",
            confidence=result.get("similarity_score", 0.0),
            metadata_info={"reason": result.get("reason"), "similarity": result.get("similarity_score")}
        )
        db.add(ev)
        db.commit()
        return {
            "verified": False,
            "message": result.get("reason", "Identity verification failed. Please try again or contact support."),
            "similarity_score": result.get("similarity_score", 0.0),
            "stage": result.get("stage", "identity_comparison")
        }

    # Process mandatory ID card document check
    id_card_result = verify_id_card_document(probe.id_card_frame_base64, candidate.full_name)
    result["id_card_verification"] = id_card_result
    if not id_card_result["verified"]:
        return {
            "verified": False,
            "message": f"ID Card Verification Issue: {id_card_result['reason']}",
            "similarity_score": result.get("similarity_score", 0.0),
            "stage": "id_card_verification",
            "id_card_details": id_card_result
        }

    # Mark identity verified and transition session to in_progress
    session.identity_verified = True
    session.identity_verified_at = datetime.utcnow()
    session.identity_verification_details = result
    
    # Initialize questions
    first_q = interview_engine.start_session_after_verification(session, db)
    db.commit()

    return {
        "verified": True,
        "message": "Identity verified successfully. Technical interview initialized.",
        "similarity_score": result.get("similarity_score", 1.0),
        "verification_details": {
            "stage": result.get("stage", "identity_comparison"),
            "similarity_score": result.get("similarity_score", 1.0),
            "liveness_indicators": result.get("liveness_indicators", {}),
            "id_card_verification": id_card_result
        },
        "first_question": {
            "id": first_q.id,
            "order_index": first_q.order_index,
            "question_text": first_q.question_text,
            "competency_tested": first_q.competency_tested,
            "difficulty_level": first_q.difficulty_level,
            "question_type": getattr(first_q, "question_type", "open_ended") or "open_ended",
            "options": getattr(first_q, "options", []) or []
        }
    }

@interview_router.post("/{token}/submit-answer")
def submit_answer(token: str, answer_in: QuestionAnswerSubmit, db: Session = Depends(get_db)):
    session = db.query(InterviewSession).filter(InterviewSession.session_token == token).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if not session.identity_verified:
        raise HTTPException(status_code=403, detail="Identity verification required before submitting answers")
    if session.status == "completed":
        raise HTTPException(status_code=400, detail="Interview already completed")

    # Find the active unanswered question
    active_q = None
    for q in session.questions:
        if q.candidate_answer is None:
            active_q = q
            break

    if not active_q:
        raise HTTPException(status_code=400, detail="No active question waiting for response")

    # Submit and evaluate answer reliably
    eval_result = interview_engine.submit_and_evaluate_answer(
        session=session,
        question=active_q,
        answer_text=answer_in.answer_text,
        db=db,
        answer_mode=answer_in.answer_mode or "typed",
        selected_option=answer_in.selected_option,
        voice_transcript=answer_in.voice_transcript
    )

    next_q = eval_result.get("next_question")
    next_q_data = None
    if next_q:
        next_q_data = {
            "id": next_q.id,
            "order_index": next_q.order_index,
            "question_text": next_q.question_text,
            "competency_tested": next_q.competency_tested,
            "difficulty_level": next_q.difficulty_level,
            "question_type": getattr(next_q, "question_type", "open_ended") or "open_ended",
            "options": getattr(next_q, "options", []) or []
        }

    return {
        "status": session.status,
        "question_id": active_q.id,
        "is_interview_complete": eval_result.get("is_interview_complete", session.status == "completed"),
        "next_question_available": next_q is not None,
        "next_question": next_q_data,
        "total_questions_completed": len([q for q in session.questions if q.candidate_answer is not None]),
        "evaluation": {
            "score": active_q.score,
            "strengths": active_q.strengths,
            "weaknesses": active_q.weaknesses,
            "adaptation_reason": active_q.adaptation_reason,
            "next_difficulty": session.current_difficulty
        }
    }

@interview_router.post("/{token}/integrity-event")
def log_integrity_event(token: str, event_in: IntegrityEventCreate, db: Session = Depends(get_db)):
    session = db.query(InterviewSession).filter(InterviewSession.session_token == token).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # If session is already completed, ignore subsequent proctor events
    if session.status == InterviewStatus.COMPLETED or session.status == "completed":
        return {
            "status": "session_already_completed",
            "terminated": True,
            "reason": "Interview has concluded."
        }

    candidate = session.candidate
    actual_event_type = event_in.event_type
    severity = event_in.severity or "low"
    confidence = event_in.confidence or 1.0
    meta = event_in.metadata_info or {}

    # Continuous frame verification if frame_base64 is sent
    if event_in.frame_base64 and candidate and candidate.enrolled_face_reference:
        try:
            face_result = identity_service.compare_faces(
                candidate.enrolled_face_reference,
                event_in.frame_base64
            )
            sim = face_result.get("similarity", 0.0)
            meta["face_similarity"] = sim
            meta["continuous_check"] = True
            
            if not face_result.get("match", False):
                actual_event_type = "continuous_identity_mismatch"
                severity = "critical"
                confidence = float(round(1.0 - sim, 3))
                meta["face_verified"] = False
            else:
                meta["face_verified"] = True
        except Exception as frame_err:
            logger.warning(f"Continuous frame verification failed: {frame_err}")

    # Deduplication: Check if an identical event type was logged in the last 4 seconds to prevent camera noise flooding
    now = datetime.utcnow()
    recent_dup = None
    if session.integrity_events:
        for prev in reversed(session.integrity_events):
            if prev.event_type == actual_event_type:
                time_diff = (now - prev.timestamp).total_seconds() if prev.timestamp else 999
                if time_diff < 4:
                    recent_dup = prev
                    break

    if recent_dup:
        return {
            "status": "deduplicated",
            "terminated": False,
            "message": "Repeated event within debounce threshold suppressed."
        }

    event = IntegrityEvent(
        session_id=session.id,
        event_type=actual_event_type,
        severity=severity,
        confidence=confidence,
        metadata_info=meta,
        timestamp=now
    )
    db.add(event)
    db.commit()

    # Re-fetch events count for threshold evaluation
    all_events = db.query(IntegrityEvent).filter(IntegrityEvent.session_id == session.id).all()
    tab_switches = [e for e in all_events if e.event_type in ["tab_switch", "fullscreen_exit"]]
    identity_mismatches = [e for e in all_events if e.event_type in ["identity_mismatch", "continuous_identity_mismatch"]]
    
    terminated = False
    termination_reason = None

    # Threshold 1: 3 or more tab switch/fullscreen exit events
    if len(tab_switches) >= 3:
        terminated = True
        termination_reason = f"Session terminated: Exceeded maximum allowed tab switches (3 recorded)."
    # Threshold 2: Confirmed identity mismatch during continuous monitoring
    elif len(identity_mismatches) >= 2 or (len(identity_mismatches) >= 1 and event_in.event_type == "continuous_identity_mismatch"):
        terminated = True
        termination_reason = "Session terminated: Persistent facial identity mismatch detected during continuous monitoring."
    # Threshold 3: Overall integrity anomalies exceeding 5 unique alerts
    elif len(all_events) >= 6:
        terminated = True
        termination_reason = "Session terminated: Cumulative proctor integrity anomalies exceeded allowable threshold."

    if terminated:
        interview_engine.finalize_interview(session, db)
        session.recruiter_notes = f"{session.recruiter_notes or ''}\n[PROCTOR TERMINATION]: {termination_reason}".strip()
        db.commit()

    return {
        "status": "logged",
        "total_warnings": len(all_events),
        "tab_switches_count": len(tab_switches),
        "terminated": terminated,
        "termination_reason": termination_reason
    }
