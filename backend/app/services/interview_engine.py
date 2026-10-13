import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.entities import (
    InterviewSession, InterviewQuestion, InterviewStatus,
    Candidate, JobDescription, IntegrityEvent
)
from app.services.llm_service import llm_service
from app.services.email_service import email_service
from app.core.config import settings

class InterviewEngine:
    @staticmethod
    def schedule_session(
        candidate_id: int, 
        job_description_id: int, 
        recruiter_id: int, 
        scheduled_start: datetime,
        db: Session
    ) -> Dict[str, Any]:
        candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
        job = db.query(JobDescription).filter(JobDescription.id == job_description_id).first()
        if not candidate or not job:
            raise HTTPException(status_code=404, detail="Candidate or Job Description record not found")

        # If timezone-aware datetime is passed, convert to UTC naive
        if scheduled_start.tzinfo is not None:
            scheduled_start = scheduled_start.astimezone(timezone.utc).replace(tzinfo=None)

        session_token = str(uuid.uuid4())
        scheduled_end = scheduled_start + timedelta(minutes=settings.INTERVIEW_WINDOW_MINUTES)

        session = InterviewSession(
            session_token=session_token,
            candidate_id=candidate.id,
            job_description_id=job.id,
            recruiter_id=recruiter_id,
            status=InterviewStatus.SCHEDULED,
            scheduled_start=scheduled_start,
            scheduled_end=scheduled_end,
            current_question_index=0,
            current_difficulty="Medium"
        )
        db.add(session)
        db.commit()
        db.refresh(session)

        # Trigger real email invitation
        email_result = email_service.send_interview_invitation(
            candidate_email=candidate.email,
            candidate_name=candidate.full_name,
            job_title=job.title,
            scheduled_start=scheduled_start,
            session_token=session_token
        )

        session.invitation_sent_at = datetime.utcnow()
        session.invitation_email_status = email_result.get("status", "pending")
        db.commit()

        return {
            "session": session,
            "email_delivery": email_result
        }

    @staticmethod
    def verify_time_window(session: InterviewSession) -> Dict[str, Any]:
        """Enforces backend time restriction. Candidates cannot enter early or after expiry."""
        if not session.scheduled_start:
            return {"allowed": True, "reason": "No strict time window configured"}

        now = datetime.utcnow()
        early_bound = session.scheduled_start - timedelta(minutes=settings.INTERVIEW_EARLY_ACCESS_MINUTES)
        late_bound = session.scheduled_end or (session.scheduled_start + timedelta(minutes=settings.INTERVIEW_WINDOW_MINUTES))

        if now < early_bound:
            diff_mins = int((early_bound - now).total_seconds() / 60)
            return {
                "allowed": False,
                "reason": f"Interview window has not opened yet. You may enter starting {settings.INTERVIEW_EARLY_ACCESS_MINUTES} minutes before your scheduled start time (in approx {diff_mins} minutes).",
                "scheduled_start": session.scheduled_start.isoformat(),
                "now": now.isoformat()
            }
        
        if now > late_bound and session.status != InterviewStatus.IN_PROGRESS and session.status != InterviewStatus.COMPLETED:
            return {
                "allowed": False,
                "reason": "This interview invitation window has expired. Please contact your recruiter to reschedule.",
                "scheduled_end": late_bound.isoformat(),
                "now": now.isoformat()
            }

        return {"allowed": True, "reason": "Active interview window open."}

    @staticmethod
    def start_session_after_verification(session: InterviewSession, db: Session) -> InterviewQuestion:
        if not session.identity_verified:
            raise HTTPException(status_code=403, detail="Biometric identity verification must pass before accessing questions.")

        time_check = InterviewEngine.verify_time_window(session)
        if not time_check["allowed"]:
            raise HTTPException(status_code=403, detail=time_check["reason"])

        session.status = InterviewStatus.IN_PROGRESS
        session.started_at = datetime.utcnow()
        session.current_question_index = 1
        db.commit()

        # If question not yet generated, generate Q1
        if len(session.questions) == 0:
            return InterviewEngine.generate_next_question(session, db)
        return session.questions[0]

    @staticmethod
    def generate_next_question(session: InterviewSession, db: Session) -> InterviewQuestion:
        order_index = len(session.questions) + 1
        job = session.job_description
        candidate = session.candidate

        system_prompt = (
            "You are an expert technical interviewer conducting an adaptive interview. "
            "Output strictly a JSON object with keys: question, competency_tested, difficulty_level, expected_criteria, question_type, options. "
            "question_type must be 'open_ended', 'multiple_choice' (include 4 options in 'options'), or 'fill_blank' (question sentence has a blank '_____')."
        )
        user_prompt = (
            f"Generate Question #{order_index} for the position '{job.title}'.\n"
            f"Required competencies: {job.required_competencies}\n"
            f"Candidate background skills: {candidate.extracted_skills}\n"
            f"Target difficulty: {session.current_difficulty}\n"
        )

        llm_res = llm_service.invoke_structured(system_prompt, user_prompt)
        question_text = llm_res.get("question", f"Explain how you design scalable components in {job.title}.")
        competency = llm_res.get("competency_tested", "Technical Architecture")
        difficulty = llm_res.get("difficulty_level", session.current_difficulty)
        criteria = llm_res.get("expected_criteria", "Depth, accuracy, and clear communication.")
        q_type = llm_res.get("question_type", "open_ended")
        options = llm_res.get("options", [])

        new_q = InterviewQuestion(
            session_id=session.id,
            order_index=order_index,
            question_text=question_text,
            competency_tested=competency,
            difficulty_level=difficulty,
            expected_criteria=criteria,
            question_type=q_type,
            options=options
        )
        db.add(new_q)
        db.commit()
        db.refresh(new_q)
        return new_q

    @staticmethod
    def submit_and_evaluate_answer(
        session: InterviewSession, 
        question: InterviewQuestion, 
        answer_text: str, 
        db: Session,
        answer_mode: str = "typed",
        selected_option: Optional[str] = None,
        voice_transcript: Optional[str] = None
    ) -> Dict[str, Any]:
        # Immediately persist candidate's response to database to avoid loss
        question.candidate_answer = answer_text
        question.answer_mode = answer_mode
        question.voice_transcript = voice_transcript or (answer_text if answer_mode == "voice_transcript" else None)
        question.answered_at = datetime.utcnow()
        db.commit()

        system_prompt = (
            "You are an evidence-based assessment engine. Evaluate the candidate's answer against the question and criteria. "
            "Output strictly a JSON object with keys: score (float 0-10), technical_accuracy (float 0-10), "
            "depth_of_knowledge (float 0-10), clarity_of_communication (float 0-10), strengths (list of str), "
            "weaknesses (list of str), evidence_quote (str), confidence_level (High/Moderate/Uncertain), "
            "next_difficulty (Easy/Medium/Hard/Recovery), adaptation_reason (str)."
        )
        user_prompt = (
            f"Question: {question.question_text}\n"
            f"Question Type: {getattr(question, 'question_type', 'open_ended')}\n"
            f"Expected Criteria: {question.expected_criteria}\n"
            f"Candidate Answer: {answer_text}\n"
            f"Current Difficulty: {question.difficulty_level}\n"
        )

        evaluation = llm_service.invoke_structured(system_prompt, user_prompt)
        meta = evaluation.get("_metadata", {})

        score = float(evaluation.get("score", 7.0))
        question.score = score
        question.rubric_scores = {
            "technical_accuracy": evaluation.get("technical_accuracy", score),
            "depth_of_knowledge": evaluation.get("depth_of_knowledge", score),
            "clarity_of_communication": evaluation.get("clarity_of_communication", score),
            "evaluator": meta.get("evaluator", "Algorithmic Baseline"),
            "is_real_llm": bool(meta.get("is_real_llm", False)),
            "source": meta.get("source", "algorithmic_fallback"),
            "notice": meta.get("notice", "")
        }
        question.strengths = evaluation.get("strengths", ["Answered relevant aspects"])
        question.weaknesses = evaluation.get("weaknesses", [])
        question.evidence_quote = evaluation.get("evidence_quote", answer_text[:120])
        question.confidence_level = evaluation.get("confidence_level", "High")
        question.adaptation_reason = evaluation.get("adaptation_reason", "Adaptive progress based on score.")

        # Update session difficulty
        next_difficulty = evaluation.get("next_difficulty", "Medium")
        session.current_difficulty = next_difficulty
        db.commit()

        # Check if interview question limit reached
        next_q = None
        if len(session.questions) >= settings.MAX_QUESTIONS_PER_SESSION:
            InterviewEngine.finalize_interview(session, db)
        else:
            session.current_question_index += 1
            next_q = InterviewEngine.generate_next_question(session, db)
            db.commit()

        return {
            "evaluation": evaluation,
            "next_question": next_q,
            "is_interview_complete": session.status == InterviewStatus.COMPLETED or session.status == "completed"
        }

    @staticmethod
    def finalize_interview(session: InterviewSession, db: Session):
        session.status = InterviewStatus.COMPLETED
        session.completed_at = datetime.utcnow()

        # Compute average score
        scores = [q.score for q in session.questions if q.score is not None]
        avg_score = sum(scores) / len(scores) if scores else 0.0
        session.final_score = round(avg_score, 1)

        if avg_score >= 8.5:
            rec = "Strong Hire"
        elif avg_score >= 7.0:
            rec = "Hire"
        elif avg_score >= 5.0:
            rec = "Lean No"
        else:
            rec = "No Hire"
        session.final_recommendation = rec

        # Skill-gap analysis comparing:
        # 1. Job requirements, 2. Resume claims, 3. Interview evidence
        job = session.job_description
        candidate = session.candidate
        
        # Categorize skill statuses
        demonstrated = []
        claimed_unvalidated = []
        not_demonstrated = []
        not_assessed = []

        all_reqs = [c.get("name") if isinstance(c, dict) else str(c) for c in (job.required_competencies or [])]
        cand_skills = candidate.extracted_skills or []
        
        # Cross reference
        for req in all_reqs:
            # Check questions
            tested = [q for q in session.questions if req.lower() in q.competency_tested.lower() or req.lower() in q.question_text.lower()]
            if tested:
                # Scored
                high_scores = [q for q in tested if (q.score or 0) >= 7.0]
                if high_scores:
                    demonstrated.append(req)
                else:
                    not_demonstrated.append(req)
            else:
                # Not tested in questions
                matching_claim = [s for s in cand_skills if req.lower() in str(s).lower()]
                if matching_claim:
                    claimed_unvalidated.append(req)
                else:
                    not_assessed.append(req)

        match_pct = int((len(demonstrated) / max(1, len(all_reqs))) * 100)

        session.skill_gap_analysis = {
            "match_percentage": match_pct,
            "demonstrated": demonstrated,
            "claimed_unvalidated": claimed_unvalidated,
            "not_demonstrated": not_demonstrated,
            "not_assessed": not_assessed,
            "matching_skills": demonstrated,
            "missing_skills": not_demonstrated + claimed_unvalidated,
            "recommendation": f"{len(demonstrated)} competencies verified through direct interview evidence."
        }

        # Check if real LLM was used for any questions
        has_real_llm = any(
            bool(q.rubric_scores and q.rubric_scores.get("is_real_llm")) 
            for q in session.questions
        )

        # Evidence report
        session.evidence_report = {
            "candidate_name": candidate.full_name,
            "candidate_email": candidate.email,
            "job_title": job.title,
            "summary": f"Completed {len(session.questions)} adaptive technical interview questions with overall evidence rating of {session.final_score}/10.",
            "recommendation": session.final_recommendation,
            "identity_verified": session.identity_verified,
            "integrity_events_count": len(session.integrity_events),
            "evaluator_type": "Live Gemini LLM" if has_real_llm else "Algorithmic Baseline Engine (Configure GEMINI_API_KEY in .env for production LLM)",
            "is_real_llm": has_real_llm,
            "generated_at": datetime.utcnow().isoformat(),
            "demonstrated_count": len(demonstrated),
            "unvalidated_count": len(claimed_unvalidated),
            "gap_count": len(not_demonstrated)
        }

        db.commit()

interview_engine = InterviewEngine()
