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
    def update_competency_profile(
        session: InterviewSession, 
        question: InterviewQuestion, 
        evaluation: Dict[str, Any], 
        db: Session
    ) -> Dict[str, Any]:
        """
        Updates and persists the candidate's real-time competency profile.
        Maintains independent difficulty levels and status for each required competency.
        """
        analysis_data = dict(session.skill_gap_analysis or {}) if isinstance(session.skill_gap_analysis, dict) else {}
        profile = dict(analysis_data.get("competency_profile") or {})
        
        job = session.job_description
        all_reqs = []
        for c in (job.required_competencies or []):
            if isinstance(c, dict) and "name" in c:
                all_reqs.append(str(c["name"]))
            elif isinstance(c, str):
                all_reqs.append(c)
        if not all_reqs:
            all_reqs = ["System Architecture", "Technical Problem Solving", "Data Modeling & Performance", "Code Reliability & Testing"]

        # Ensure all required competencies are seeded in profile
        for req in all_reqs:
            if req not in profile:
                profile[req] = {
                    "competency": req,
                    "status": "Untested",
                    "current_difficulty": "Medium",
                    "scores": [],
                    "average_score": None,
                    "questions_count": 0,
                    "strengths": [],
                    "weaknesses": [],
                    "missing_concepts": [],
                    "history": []
                }

        # Find best matching competency in profile
        matched_key = question.competency_tested
        for req in profile:
            if req.lower() in question.competency_tested.lower() or question.competency_tested.lower() in req.lower():
                matched_key = req
                break
        
        if matched_key not in profile:
            profile[matched_key] = {
                "competency": matched_key,
                "status": "Untested",
                "current_difficulty": "Medium",
                "scores": [],
                "average_score": None,
                "questions_count": 0,
                "strengths": [],
                "weaknesses": [],
                "missing_concepts": [],
                "history": []
            }

        entry = profile[matched_key]
        score = float(evaluation.get("score", 7.0))
        entry["scores"].append(score)
        entry["average_score"] = round(sum(entry["scores"]) / len(entry["scores"]), 1)
        entry["questions_count"] += 1
        
        new_strengths = evaluation.get("strengths") or []
        for s in new_strengths:
            if s not in entry["strengths"]:
                entry["strengths"].append(s)
                
        new_weaknesses = evaluation.get("weaknesses") or []
        for w in new_weaknesses:
            if w not in entry["weaknesses"]:
                entry["weaknesses"].append(w)
                
        new_missing = evaluation.get("missing_concepts") or [w for w in new_weaknesses if any(k in w.lower() for k in ["miss", "lack", "omit", "not", "fail", "incorrect"])]
        for m in new_missing:
            if m not in entry["missing_concepts"]:
                entry["missing_concepts"].append(m)

        # Independent per-competency adaptation:
        # Strong answer (>= 7.5): Demonstrated, probe Hard
        # Partially correct (4.5 <= score < 7.5): Partially Demonstrated, Medium
        # Weak/incorrect (< 4.5): Needs Prerequisite Review, Recovery/Easy
        if score >= 7.5:
            entry["status"] = "Demonstrated"
            entry["current_difficulty"] = "Hard"
        elif score >= 4.5:
            entry["status"] = "Partially Demonstrated"
            entry["current_difficulty"] = "Medium"
        else:
            entry["status"] = "Needs Prerequisite Review"
            entry["current_difficulty"] = "Recovery" if score < 3.5 else "Easy"

        entry["history"].append({
            "question_id": question.id,
            "order_index": question.order_index,
            "score": score,
            "difficulty": question.difficulty_level,
            "evidence_quote": evaluation.get("evidence_quote") or question.evidence_quote,
            "timestamp": datetime.utcnow().isoformat()
        })

        analysis_data["competency_profile"] = profile
        session.skill_gap_analysis = analysis_data
        session.current_difficulty = entry["current_difficulty"]
        db.commit()
        return profile

    @staticmethod
    def determine_next_adaptive_strategy(
        session: InterviewSession,
        last_question: Optional[InterviewQuestion],
        last_evaluation: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Closed-loop decision engine that maps the previous answer evaluation
        directly to the next question's competency, difficulty, topic, and question type.
        """
        job = session.job_description
        candidate = session.candidate
        coverage = InterviewEngine._get_competency_coverage(session)
        profile = (session.skill_gap_analysis or {}).get("competency_profile", {})

        # Default strategy for Q1 or missing evaluation
        if not last_question or not last_evaluation:
            target = coverage["untested_competencies"][0] if coverage["untested_competencies"] else "System Architecture"
            return {
                "action": "initial_assessment",
                "target_competency": target,
                "target_topic": f"Foundational architecture and principles of {target}",
                "target_difficulty": "Medium",
                "suggested_type": "open_ended",
                "rationale": f"Initial baseline assessment of core competency: '{target}'.",
                "context_for_prompt": f"Begin assessment on core required competency '{target}' at Medium difficulty."
            }

        score = float(last_evaluation.get("score", 7.0))
        last_comp = last_question.competency_tested
        weaknesses = last_evaluation.get("weaknesses") or []
        missing_concepts = last_evaluation.get("missing_concepts") or []
        strengths = last_evaluation.get("strengths") or []

        # RULE 3: Weak or Incorrect Answer (score < 4.5) -> Step down to prerequisite concepts
        if score < 4.5:
            target_diff = "Recovery" if score < 3.5 else "Easy"
            return {
                "action": "step_down_prerequisite",
                "target_competency": last_comp,
                "target_topic": f"Fundamental prerequisites, core definitions, and basic logic of {last_comp}",
                "target_difficulty": target_diff,
                "suggested_type": "multiple_choice",
                "rationale": f"Candidate struggled with question #{last_question.order_index} in '{last_comp}' (score: {score:.1f}/10). Stepping down to prerequisite concepts to establish baseline understanding.",
                "context_for_prompt": (
                    f"The candidate struggled on question #{last_question.order_index} regarding '{last_comp}' with score {score:.1f}/10. "
                    f"Candidate's answer was: '{last_question.candidate_answer}'. Weaknesses: {weaknesses}. "
                    f"Action: Step down to fundamental prerequisite concepts, elementary definitions, or simpler diagnostic questions at {target_diff} difficulty."
                )
            }

        # RULE 2: Partially Correct Answer (4.5 <= score < 7.5) -> Investigate the specific missing concept
        if score < 7.5:
            missing_topic = None
            if missing_concepts:
                missing_topic = missing_concepts[0]
            elif weaknesses:
                missing_topic = weaknesses[0]
            else:
                missing_topic = f"edge cases and operational recovery mechanisms in {last_comp}"

            suggested_type = "fill_blank" if any(k in str(missing_topic).lower() for k in ["term", "syntax", "name", "keyword", "command", "token"]) else "open_ended"
            return {
                "action": "investigate_missing_concept",
                "target_competency": last_comp,
                "target_topic": f"Specific missing concept: {missing_topic}",
                "target_difficulty": "Medium",
                "suggested_type": suggested_type,
                "rationale": f"Candidate provided a partially correct answer on '{last_comp}' (score: {score:.1f}/10). Investigating missing concept: '{missing_topic}'.",
                "context_for_prompt": (
                    f"The candidate's response to question #{last_question.order_index} on '{last_comp}' was partially correct (score: {score:.1f}/10). "
                    f"Strengths: {strengths}. Missing concepts: '{missing_topic}'. "
                    f"Action: Ask a focused follow-up question specifically probing and investigating this missing concept."
                )
            }

        # RULE 1: Strong Answer (score >= 7.5) -> Probe deeper or advance to next competency
        # If this competency has not been tested at Hard difficulty, probe deeper into complex trade-offs
        if last_question.difficulty_level != "Hard":
            return {
                "action": "probe_deeper",
                "target_competency": last_comp,
                "target_topic": f"Advanced scale, concurrency, edge cases, and architectural trade-offs in {last_comp}",
                "target_difficulty": "Hard",
                "suggested_type": "open_ended",
                "rationale": f"Candidate demonstrated strong command of '{last_comp}' (score: {score:.1f}/10). Probing deeper into advanced scale, failure modes, and production trade-offs at Hard difficulty.",
                "context_for_prompt": (
                    f"The candidate gave a strong answer to question #{last_question.order_index} on '{last_comp}' (score: {score:.1f}/10). "
                    f"Strengths: {strengths}. Evidence: '{last_question.evidence_quote}'. "
                    f"Action: Probe deeper into high-scale challenges, distributed trade-offs, performance bottlenecks, or complex edge cases at Hard difficulty."
                )
            }

        # If already validated at Hard, transition to next untested competency or candidate resume skill
        untested = coverage.get("untested_competencies") or []
        if untested:
            next_comp = untested[0]
            comp_diff = profile.get(next_comp, {}).get("current_difficulty", "Medium")
            return {
                "action": "advance_to_next_competency",
                "target_competency": next_comp,
                "target_topic": f"Core principles and architecture of {next_comp}",
                "target_difficulty": comp_diff,
                "suggested_type": "open_ended",
                "rationale": f"Candidate validated mastery in '{last_comp}'. Advancing to untested required competency: '{next_comp}'.",
                "context_for_prompt": (
                    f"Candidate successfully validated '{last_comp}' at Hard difficulty. "
                    f"Action: Advance to assess previously untested required competency '{next_comp}' for the role of {job.title}."
                )
            }

        # If all required competencies tested, explore candidate's resume claimed skills
        cand_skills = candidate.extracted_skills or []
        tested_comps_lower = [c.lower() for c in coverage.get("tested_competencies", [])]
        untested_claims = [s for s in cand_skills if str(s).lower() not in tested_comps_lower]
        if untested_claims:
            target_claim = str(untested_claims[0])
            return {
                "action": "validate_resume_claim",
                "target_competency": target_claim,
                "target_topic": f"Practical application of resume-claimed skill: {target_claim}",
                "target_difficulty": "Medium",
                "suggested_type": "open_ended",
                "rationale": f"All core requirements assessed. Validating candidate's resume claim: '{target_claim}'.",
                "context_for_prompt": f"Candidate claimed '{target_claim}' on their resume. Ask a practical application question to validate this claim."
            }

        # Otherwise, deep-dive into comprehensive system design
        return {
            "action": "comprehensive_synthesis",
            "target_competency": coverage["all_required"][0] if coverage["all_required"] else "System Architecture",
            "target_topic": "Holistic system integration and multi-component trade-offs",
            "target_difficulty": "Hard",
            "suggested_type": "open_ended",
            "rationale": "Synthesizing competencies into advanced end-to-end architecture question.",
            "context_for_prompt": "Generate a comprehensive end-to-end architecture question testing multiple competencies simultaneously."
        }

    @staticmethod
    def generate_next_question(
        session: InterviewSession, 
        db: Session,
        adaptive_strategy: Optional[Dict[str, Any]] = None
    ) -> InterviewQuestion:
        order_index = len(session.questions) + 1
        job = session.job_description
        candidate = session.candidate

        # Collect text of previously asked questions to strictly prevent duplicate questions
        previous_questions = [q.question_text.strip().lower() for q in session.questions if q.question_text]

        # If adaptive strategy not passed, compute it from session state
        if not adaptive_strategy:
            answered_qs = [q for q in session.questions if q.candidate_answer is not None and q.score is not None]
            if answered_qs:
                last_q = sorted(answered_qs, key=lambda x: x.order_index)[-1]
                last_eval = {
                    "score": last_q.score,
                    "strengths": last_q.strengths or [],
                    "weaknesses": last_q.weaknesses or [],
                    "evidence_quote": last_q.evidence_quote,
                    "confidence_level": last_q.confidence_level
                }
                strategy = InterviewEngine.determine_next_adaptive_strategy(session, last_q, last_eval)
            else:
                strategy = InterviewEngine.determine_next_adaptive_strategy(session, None, None)
        else:
            strategy = adaptive_strategy

        target_competency = strategy["target_competency"]
        target_difficulty = strategy["target_difficulty"]
        suggested_type = strategy.get("suggested_type", "open_ended")
        selection_rationale = strategy["rationale"]
        context_directive = strategy.get("context_for_prompt", "")

        system_prompt = (
            "You are an expert technical interviewer conducting an adaptive interview. "
            "Output strictly a JSON object with keys: question, competency_tested, difficulty_level, expected_criteria, question_type, options. "
            "question_type must be one of: 'open_ended', 'multiple_choice' (include 4 options in 'options'), "
            "'fill_blank' (question sentence has a single blank '_____'), or 'spoken_only'. "
            "Never repeat or closely paraphrase a question previously asked."
        )

        user_prompt = (
            f"Generate Question #{order_index} for the position '{job.title}'.\n"
            f"Target Competency to Assess: '{target_competency}'.\n"
            f"Target Difficulty Level: '{target_difficulty}'.\n"
            f"Target Question Type: '{suggested_type}'.\n"
            f"Adaptive Directive: {context_directive}\n"
            f"Adaptive Selection Reason: {selection_rationale}\n"
            f"Required Job Competencies: {job.required_competencies}\n"
            f"Candidate Resume Skills: {candidate.extracted_skills}\n"
            f"Candidate Experience Summary: {candidate.extracted_experience}\n"
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
                f"Question #{order_index} position '{job.title}' competency: '{target_competency}' target difficulty: {target_difficulty} type: {suggested_type} directive: {context_directive}"
            )
            question_text = fallback_res.get("question", f"In {job.title}, explain the key trade-offs in {target_competency} regarding {strategy['target_topic']} for question #{order_index}.")
            q_type = fallback_res.get("question_type", suggested_type)
            options = fallback_res.get("options", [])
            competency = fallback_res.get("competency_tested", target_competency)
            difficulty = fallback_res.get("difficulty_level", target_difficulty)
            criteria = fallback_res.get("expected_criteria", f"Demonstrates understanding in {target_competency} specifically regarding {strategy['target_topic']}.")
        else:
            competency = llm_res.get("competency_tested", target_competency)
            difficulty = llm_res.get("difficulty_level", target_difficulty)
            criteria = llm_res.get("expected_criteria", f"Demonstrates knowledge in {competency}.")

        # Persist the current difficulty on the session
        session.current_difficulty = difficulty

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
                "competency_profile": (session.skill_gap_analysis or {}).get("competency_profile", {}),
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
            "weaknesses (list of str), missing_concepts (list of str), evidence_quote (str), confidence_level (High/Moderate/Uncertain), "
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
        db.commit()

        # Update candidate's persistent competency profile immediately
        InterviewEngine.update_competency_profile(session, question, evaluation, db)

        # Check adaptive stopping policy
        should_stop, stop_reason = InterviewEngine.should_stop_interview(session)
        next_q = None
        if should_stop:
            InterviewEngine.finalize_interview(session, db, stopping_rationale=stop_reason)
        else:
            session.current_question_index += 1
            strategy = InterviewEngine.determine_next_adaptive_strategy(session, question, evaluation)
            next_q = InterviewEngine.generate_next_question(session, db, adaptive_strategy=strategy)
            db.commit()

        return {
            "evaluation": evaluation,
            "next_question": next_q,
            "competency_profile": (session.skill_gap_analysis or {}).get("competency_profile", {}),
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
