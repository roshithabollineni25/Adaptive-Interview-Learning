import uuid
from typing import Dict, Any, List, Optional, Tuple
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
    def _get_competency_coverage(session: InterviewSession) -> Dict[str, Any]:
        """
        Analyzes the session's question and answer history against the required competencies
        and candidate resume skills. Identifies assessed, insufficiently assessed, and untested competencies.
        """
        job = session.job_description
        candidate = session.candidate
        
        all_reqs: List[str] = []
        for c in (job.required_competencies or []):
            if isinstance(c, dict) and "name" in c:
                all_reqs.append(str(c["name"]))
            elif isinstance(c, str):
                all_reqs.append(c)

        if not all_reqs:
            all_reqs = ["System Architecture", "Technical Problem Solving", "Data Modeling & Performance", "Code Reliability & Testing"]

        # Track evidence per competency
        assessed: Dict[str, List[Dict[str, Any]]] = {r: [] for r in all_reqs}
        for q in session.questions:
            if q.candidate_answer is not None and q.score is not None:
                # Find matching competency
                matched_comp = None
                for r in all_reqs:
                    if r.lower() in q.competency_tested.lower() or q.competency_tested.lower() in r.lower():
                        matched_comp = r
                        break
                if not matched_comp:
                    matched_comp = q.competency_tested
                    if matched_comp not in assessed:
                        assessed[matched_comp] = []
                assessed[matched_comp].append({
                    "question_id": q.id,
                    "order_index": q.order_index,
                    "score": q.score,
                    "evidence_quote": q.evidence_quote,
                    "confidence_level": q.confidence_level
                })

        tested_competencies = [comp for comp, evs in assessed.items() if len(evs) > 0]
        untested_competencies = [comp for comp, evs in assessed.items() if len(evs) == 0 and comp in all_reqs]
        
        # Insufficiently assessed: tested only once with moderate/uncertain confidence or score between 4.5 and 6.5
        insufficiently_assessed = []
        for comp, evs in assessed.items():
            if len(evs) == 1:
                ev = evs[0]
                if (ev.get("confidence_level") in ["Moderate", "Uncertain"]) or (4.5 <= (ev.get("score") or 0.0) <= 6.5):
                    insufficiently_assessed.append(comp)

        return {
            "all_required": all_reqs,
            "assessed": assessed,
            "tested_competencies": tested_competencies,
            "untested_competencies": untested_competencies,
            "insufficiently_assessed": insufficiently_assessed,
            "coverage_ratio": len(tested_competencies) / max(1, len(all_reqs))
        }

    @staticmethod
    def should_stop_interview(session: InterviewSession) -> Tuple[bool, str]:
        """
        Adaptive interview stopping policy based on:
        1. Configured safety limits (MIN_QUESTIONS and MAX_QUESTIONS)
        2. Competency coverage and uncertainty
        3. Remaining time window
        """
        answered_questions = [q for q in session.questions if q.candidate_answer is not None]
        num_answered = len(answered_questions)

        # 1. Hard maximum ceiling safety limit
        if num_answered >= settings.MAX_QUESTIONS_PER_SESSION:
            return True, f"Maximum question limit reached ({settings.MAX_QUESTIONS_PER_SESSION} questions)."

        # 2. Minimum questions requirement
        if num_answered < settings.MIN_QUESTIONS_PER_SESSION:
            return False, f"Minimum questions requirement not yet met ({num_answered}/{settings.MIN_QUESTIONS_PER_SESSION})."

        # 3. Time window constraint
        if session.scheduled_end:
            now = datetime.utcnow()
            if now >= session.scheduled_end - timedelta(minutes=5):
                return True, "Allocated interview time window concluding within 5 minutes."

        # 4. Competency coverage and uncertainty
        coverage = InterviewEngine._get_competency_coverage(session)
        untested = coverage["untested_competencies"]
        insufficient = coverage["insufficiently_assessed"]

        # If all competencies have been tested and none remain highly uncertain, we can stop adaptively
        if len(untested) == 0 and len(insufficient) == 0:
            return True, f"All {len(coverage['all_required'])} required competencies comprehensively assessed with sufficient confidence."

        # If only 1 untested remains and we've reached 6 questions, we can stop if overall score is clearly polarized
        if num_answered >= 6 and len(untested) <= 1:
            recent_scores = [q.score for q in answered_questions if q.score is not None]
            avg = sum(recent_scores) / len(recent_scores) if recent_scores else 7.0
            if avg >= 8.5 or avg <= 4.0:
                return True, f"Decisive candidate performance profile established (Average: {avg:.1f}/10 across {num_answered} questions)."

        return False, f"Continuing adaptive trajectory: {len(untested)} untested and {len(insufficient)} uncertain competencies."

    @staticmethod
    def generate_next_question(session: InterviewSession, db: Session) -> InterviewQuestion:
        order_index = len(session.questions) + 1
        job = session.job_description
        candidate = session.candidate

        # Collect text of previously asked questions to strictly prevent duplicate questions
        previous_questions = [q.question_text.strip().lower() for q in session.questions if q.question_text]

        # Analyze competency coverage so far
        coverage = InterviewEngine._get_competency_coverage(session)
        target_competency = "Technical Architecture"
        selection_rationale = ""

        if coverage["untested_competencies"]:
            target_competency = coverage["untested_competencies"][0]
            selection_rationale = f"Targeting previously untested required competency: '{target_competency}'."
        elif coverage["insufficiently_assessed"]:
            target_competency = coverage["insufficiently_assessed"][0]
            selection_rationale = f"Re-evaluating competency with insufficient confidence or borderline performance: '{target_competency}'."
        else:
            # Deep dive into claimed skills from resume
            cand_skills = candidate.extracted_skills or []
            tested_comps_lower = [c.lower() for c in coverage["tested_competencies"]]
            untested_claims = [s for s in cand_skills if str(s).lower() not in tested_comps_lower]
            if untested_claims:
                target_competency = str(untested_claims[0])
                selection_rationale = f"Validating candidate's resume-claimed skill: '{target_competency}'."
            else:
                target_competency = coverage["all_required"][0] if coverage["all_required"] else "System Design"
                selection_rationale = f"Assessing advanced depth in core competency: '{target_competency}'."

        # Determine target question type adaptively across trajectory:
        # Vary between open_ended, multiple_choice, fill_blank, and spoken_only
        suggested_type = "open_ended"
        if order_index == 2:
            suggested_type = "multiple_choice"
        elif order_index == 3:
            suggested_type = "fill_blank"
        elif order_index == 4:
            suggested_type = "spoken_only"
        elif order_index == 5:
            suggested_type = "multiple_choice"
        elif order_index >= 6:
            # Alternating type for higher index questions
            types_pool = ["open_ended", "fill_blank", "multiple_choice", "spoken_only"]
            suggested_type = types_pool[(order_index) % len(types_pool)]

        system_prompt = (
            "You are an expert technical interviewer conducting an adaptive interview. "
            "Output strictly a JSON object with keys: question, competency_tested, difficulty_level, expected_criteria, question_type, options. "
            "question_type must be one of: 'open_ended', 'multiple_choice' (include 4 options in 'options'), "
            "'fill_blank' (question sentence has a single blank '_____'), or 'spoken_only' (a question designed to be heard and answered verbally). "
            "Never repeat or closely paraphrase a question previously asked."
        )

        user_prompt = (
            f"Generate Question #{order_index} for the position '{job.title}'.\n"
            f"Target Competency to Assess: '{target_competency}'.\n"
            f"Selection Reason: {selection_rationale}\n"
            f"Target Question Type: '{suggested_type}'.\n"
            f"Required competencies: {job.required_competencies}\n"
            f"Candidate background skills: {candidate.extracted_skills}\n"
            f"Target difficulty: {session.current_difficulty}\n"
            f"Previously asked questions in this session (DO NOT REPEAT): {[q.question_text for q in session.questions]}\n"
        )

        llm_res = llm_service.invoke_structured(system_prompt, user_prompt)
        question_text = llm_res.get("question", "").strip()
        q_type = llm_res.get("question_type", suggested_type) or suggested_type
        options = llm_res.get("options", [])

        # Check for duplicate question against previous questions in session
        if not question_text or question_text.lower() in previous_questions:
            # Fallback to structured algorithmic generator with guarantee of uniqueness
            fallback_res = llm_service._fallback_response(
                "generate question",
                f"Question #{order_index} position '{job.title}' competency: '{target_competency}' target difficulty: {session.current_difficulty} type: {suggested_type}"
            )
            question_text = fallback_res.get("question", f"Explain how you design and implement {target_competency} in {job.title} for question #{order_index}.")
            q_type = fallback_res.get("question_type", suggested_type)
            options = fallback_res.get("options", [])
            competency = fallback_res.get("competency_tested", target_competency)
            difficulty = fallback_res.get("difficulty_level", session.current_difficulty)
            criteria = fallback_res.get("expected_criteria", f"Demonstrates knowledge and practical depth in {target_competency}.")
        else:
            competency = llm_res.get("competency_tested", target_competency)
            difficulty = llm_res.get("difficulty_level", session.current_difficulty)
            criteria = llm_res.get("expected_criteria", f"Demonstrates knowledge and practical depth in {competency}.")

        new_q = InterviewQuestion(
            session_id=session.id,
            order_index=order_index,
            question_text=question_text,
            competency_tested=competency,
            difficulty_level=difficulty,
            expected_criteria=criteria,
            question_type=q_type,
            options=options,
            adaptation_reason=selection_rationale
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
        # Idempotency check: If question already answered and scored, return existing evaluation
        if question.candidate_answer is not None and question.score is not None:
            # Check if interview is already complete or find next
            next_q = None
            if session.status != InterviewStatus.COMPLETED and session.status != "completed":
                unanswered = [q for q in session.questions if q.candidate_answer is None and q.id != question.id]
                next_q = unanswered[0] if unanswered else None
            return {
                "evaluation": {
                    "score": question.score,
                    "technical_accuracy": (question.rubric_scores or {}).get("technical_accuracy", question.score),
                    "depth_of_knowledge": (question.rubric_scores or {}).get("depth_of_knowledge", question.score),
                    "clarity_of_communication": (question.rubric_scores or {}).get("clarity_of_communication", question.score),
                    "strengths": question.strengths or [],
                    "weaknesses": question.weaknesses or [],
                    "evidence_quote": question.evidence_quote,
                    "confidence_level": question.confidence_level,
                    "adaptation_reason": question.adaptation_reason,
                    "idempotent": True
                },
                "next_question": next_q,
                "is_interview_complete": session.status == InterviewStatus.COMPLETED or session.status == "completed"
            }

        # Immediately persist candidate's response to database to avoid loss
        question.candidate_answer = answer_text
        question.answer_mode = answer_mode
        question.voice_transcript = voice_transcript or (answer_text if answer_mode == "voice" or answer_mode == "voice_transcript" else None)
        question.answered_at = datetime.utcnow()
        db.commit()

        system_prompt = (
            "You are an evidence-based assessment engine. Evaluate the candidate's answer against the question, competency, and criteria. "
            "Identify correct concepts, missing concepts, factual errors, reasoning quality, and concrete examples. "
            "Output strictly a JSON object with keys: score (float 0-10), technical_accuracy (float 0-10), "
            "depth_of_knowledge (float 0-10), clarity_of_communication (float 0-10), strengths (list of str), "
            "weaknesses (list of str), evidence_quote (str), confidence_level (High/Moderate/Uncertain), "
            "next_difficulty (Easy/Medium/Hard/Recovery), adaptation_reason (str)."
        )
        user_prompt = (
            f"Competency Tested: {question.competency_tested}\n"
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
        question.strengths = evaluation.get("strengths", ["Addressed core technical premise"])
        question.weaknesses = evaluation.get("weaknesses", [])
        question.evidence_quote = evaluation.get("evidence_quote", answer_text[:140])
        question.confidence_level = evaluation.get("confidence_level", "High")
        question.adaptation_reason = evaluation.get("adaptation_reason", f"Assessed {question.competency_tested} with score {score}/10.")

        # Update session difficulty adaptively
        next_difficulty = evaluation.get("next_difficulty", "Medium")
        session.current_difficulty = next_difficulty
        db.commit()

        # Check adaptive stopping policy
        should_stop, stop_reason = InterviewEngine.should_stop_interview(session)
        next_q = None
        if should_stop:
            InterviewEngine.finalize_interview(session, db, stopping_rationale=stop_reason)
        else:
            session.current_question_index += 1
            next_q = InterviewEngine.generate_next_question(session, db)
            db.commit()

        return {
            "evaluation": evaluation,
            "next_question": next_q,
            "is_interview_complete": session.status == InterviewStatus.COMPLETED or session.status == "completed",
            "stopping_rationale": stop_reason if should_stop else None
        }

    @staticmethod
    def finalize_interview(session: InterviewSession, db: Session, stopping_rationale: Optional[str] = None):
        session.status = InterviewStatus.COMPLETED
        session.completed_at = datetime.utcnow()

        # Compute average score across answered questions
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

        # Granular 4-Tier Skill-gap analysis connecting resume claims, job requirements, and interview evidence
        job = session.job_description
        candidate = session.candidate
        
        demonstrated = []
        claimed_unvalidated = []
        not_demonstrated = []
        not_assessed = []

        # Granular evidence breakdown for each competency
        detailed_competency_evidence: List[Dict[str, Any]] = []

        all_reqs: List[str] = []
        for c in (job.required_competencies or []):
            if isinstance(c, dict) and "name" in c:
                all_reqs.append(str(c["name"]))
            elif isinstance(c, str):
                all_reqs.append(c)

        if not all_reqs:
            all_reqs = ["System Architecture", "Technical Problem Solving", "Data Modeling & Performance", "Code Reliability & Testing"]

        cand_skills = candidate.extracted_skills or []
        
        for req in all_reqs:
            # Check interview questions for evidence
            tested = [
                q for q in session.questions 
                if (req.lower() in q.competency_tested.lower() or q.competency_tested.lower() in req.lower() or req.lower() in q.question_text.lower())
                and q.candidate_answer is not None
            ]
            
            # Check candidate resume claims
            matching_claim = [s for s in cand_skills if req.lower() in str(s).lower() or str(s).lower() in req.lower()]

            if tested:
                high_scores = [q for q in tested if (q.score or 0.0) >= 7.0]
                avg_comp_score = round(sum(q.score or 0.0 for q in tested) / len(tested), 1)
                quotes = [q.evidence_quote for q in tested if q.evidence_quote]
                quote_snippet = quotes[0] if quotes else (tested[0].candidate_answer[:120] if tested[0].candidate_answer else "")

                if high_scores:
                    status_cat = "Demonstrated"
                    demonstrated.append(req)
                    explanation = f"Demonstrated in Question #{tested[0].order_index} with score {avg_comp_score}/10: \"{quote_snippet}\""
                else:
                    status_cat = "Not Demonstrated"
                    not_demonstrated.append(req)
                    weaknesses_list = []
                    for q in tested:
                        if q.weaknesses:
                            weaknesses_list.extend(q.weaknesses)
                    weak_str = f" Gaps noted: {', '.join(weaknesses_list[:2])}." if weaknesses_list else ""
                    explanation = f"Assessed in Question #{tested[0].order_index} but failed to meet proficiency threshold ({avg_comp_score}/10).{weak_str}"

                detailed_competency_evidence.append({
                    "competency": req,
                    "status": status_cat,
                    "score": avg_comp_score,
                    "question_id": tested[0].id,
                    "question_order": tested[0].order_index,
                    "evidence_quote": quote_snippet,
                    "explanation": explanation,
                    "resume_claimed": bool(matching_claim)
                })
            else:
                # Competency was not tested in interview
                if matching_claim:
                    status_cat = "Claimed but Unvalidated"
                    claimed_unvalidated.append(req)
                    explanation = f"Claimed on candidate resume ('{matching_claim[0]}') but not directly assessed during this interview trajectory."
                else:
                    status_cat = "Not Assessed"
                    not_assessed.append(req)
                    explanation = "Job requirement was not assessed during this interview trajectory and was not found on resume."

                detailed_competency_evidence.append({
                    "competency": req,
                    "status": status_cat,
                    "score": None,
                    "question_id": None,
                    "question_order": None,
                    "evidence_quote": None,
                    "explanation": explanation,
                    "resume_claimed": bool(matching_claim)
                })

        match_pct = int((len(demonstrated) / max(1, len(all_reqs))) * 100)

        session.skill_gap_analysis = {
            "match_percentage": match_pct,
            "demonstrated": demonstrated,
            "claimed_unvalidated": claimed_unvalidated,
            "not_demonstrated": not_demonstrated,
            "not_assessed": not_assessed,
            "matching_skills": demonstrated,
            "missing_skills": not_demonstrated + claimed_unvalidated,
            "detailed_evidence": detailed_competency_evidence,
            "recommendation": f"{len(demonstrated)} of {len(all_reqs)} competencies verified through direct interview evidence."
        }

        # Check if real LLM was used for any questions
        has_real_llm = any(
            bool(q.rubric_scores and q.rubric_scores.get("is_real_llm")) 
            for q in session.questions
        )

        # Integrity summary
        integrity_events = session.integrity_events or []
        mismatch_events = [e for e in integrity_events if "mismatch" in e.event_type]
        tab_events = [e for e in integrity_events if e.event_type in ["tab_switch", "fullscreen_exit"]]
        face_missing_events = [e for e in integrity_events if "face_missing" in e.event_type or "face_not_visible" in e.event_type]
        
        integrity_risk_level = "Low"
        if mismatch_events or len(tab_events) >= 2:
            integrity_risk_level = "High"
        elif tab_events or face_missing_events:
            integrity_risk_level = "Moderate"

        # Suggested follow-up technical questions for unvalidated or gap competencies
        suggested_followups = []
        for gap in (claimed_unvalidated + not_demonstrated)[:3]:
            suggested_followups.append(f"In-depth architectural review of practical production experience with {gap}.")

        # Candidate Decision Dossier & Evidence Report
        session.evidence_report = {
            "candidate_name": candidate.full_name,
            "candidate_email": candidate.email,
            "job_title": job.title,
            "summary": f"Completed {len(session.questions)} adaptive technical interview questions with overall evidence rating of {session.final_score}/10.",
            "recommendation": session.final_recommendation,
            "identity_verified": session.identity_verified,
            "stopping_rationale": stopping_rationale or f"Concluded after {len(session.questions)} questions.",
            "integrity_summary": {
                "risk_level": integrity_risk_level,
                "total_events": len(integrity_events),
                "tab_switches_count": len(tab_events),
                "mismatch_count": len(mismatch_events),
                "face_anomalies_count": len(face_missing_events),
                "explanation": f"Observed {len(integrity_events)} telemetry event(s) across assessment." if integrity_events else "Zero integrity anomalies recorded. Full session compliance."
            },
            "evaluator_type": "Live Gemini LLM" if has_real_llm else "Algorithmic Baseline Engine (Configure GEMINI_API_KEY in .env for production LLM)",
            "is_real_llm": has_real_llm,
            "generated_at": datetime.utcnow().isoformat(),
            "demonstrated_count": len(demonstrated),
            "unvalidated_count": len(claimed_unvalidated),
            "gap_count": len(not_demonstrated),
            "not_assessed_count": len(not_assessed),
            "suggested_followups": suggested_followups
        }

        db.commit()

interview_engine = InterviewEngine()
