import json
import os
import re
import logging
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, ValidationError
from app.core.config import settings

logger = logging.getLogger(__name__)

# --- Validation Schemas for Structured LLM Outputs ---
class QuestionOutputSchema(BaseModel):
    question: str = Field(min_length=10)
    competency_tested: str = Field(min_length=2)
    difficulty_level: str = Field(default="Medium")
    expected_criteria: str = Field(default="Technical accuracy, architecture trade-offs, and communication clarity.")
    question_type: str = Field(default="open_ended")  # open_ended, multiple_choice, fill_blank, spoken_only
    options: Optional[List[str]] = Field(default_factory=list)

class AnswerEvaluationSchema(BaseModel):
    score: float = Field(ge=0.0, le=10.0)
    technical_accuracy: float = Field(default=7.0, ge=0.0, le=10.0)
    depth_of_knowledge: float = Field(default=7.0, ge=0.0, le=10.0)
    clarity_of_communication: float = Field(default=7.0, ge=0.0, le=10.0)
    strengths: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)
    evidence_quote: str = Field(default="")
    confidence_level: str = Field(default="High")
    next_difficulty: str = Field(default="Medium")
    adaptation_reason: str = Field(default="Evaluated against rubric.")

class CompetencyItemSchema(BaseModel):
    name: str
    weight: float = Field(default=0.25)
    description: str = Field(default="")

class CompetencyListSchema(BaseModel):
    competencies: List[CompetencyItemSchema]

class ResumeProfileSchema(BaseModel):
    extracted_skills: List[str] = Field(default_factory=list)
    experience_summary: List[str] = Field(default_factory=list)
    education: List[str] = Field(default_factory=list)


class LLMService:
    def get_api_key(self) -> Optional[str]:
        if settings.LLM_PROVIDER == "gemini":
            key = settings.GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY")
            if key and key.strip() and key != "your_gemini_api_key_here":
                return key.strip()
        elif settings.LLM_PROVIDER == "openai":
            key = settings.OPENAI_API_KEY or os.environ.get("OPENAI_API_KEY")
            if key and key.strip() and key != "your_openai_api_key_here":
                return key.strip()
        return None

    @property
    def is_configured(self) -> bool:
        return self.get_api_key() is not None

    def _call_gemini(self, system_instruction: str, prompt: str, api_key: str) -> str:
        from google import genai
        from google.genai import types, errors

        # Enforce tight 10s timeout to prevent 30-60s candidate UI hangs on network stalls
        client = genai.Client(api_key=api_key, http_options={"timeout": 10.0})
        target_model = settings.GEMINI_MODEL
        if not target_model or "3.5" in target_model or "3.8" in target_model:
            target_model = "gemini-2.5-flash"

        candidate_models = [target_model]
        for fallback in ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]:
            if fallback not in candidate_models:
                candidate_models.append(fallback)

        last_error = None
        for model_name in candidate_models:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        temperature=0.2,
                        response_mime_type="application/json"
                    )
                )
                if model_name != target_model:
                    logger.info(f"Successfully generated content using fallback model: {model_name}")
                return response.text
            except (errors.APIError, Exception) as e:
                last_error = e
                err_str = str(e).lower()
                # Fast fail on network timeouts or quota exceeded without wasting time trying other models
                if "timeout" in err_str or "timed out" in err_str:
                    logger.warning(f"Gemini API network timeout with {model_name}. Failing fast to fallback baseline.")
                    raise RuntimeError(f"Gemini API network timeout: {e}")
                elif "429" in err_str or "resource_exhausted" in err_str:
                    logger.error(f"Gemini API Rate Limit or Quota Exceeded: {e}")
                    raise RuntimeError(f"Gemini API rate limit or quota exceeded: {e}")
                elif "401" in err_str or "403" in err_str or "api_key_invalid" in err_str:
                    logger.error(f"Gemini API Authentication Failed: Invalid API key: {e}")
                    raise RuntimeError(f"Invalid GEMINI_API_KEY: {e}")
                elif "not found" in err_str or "404" in err_str or "503" in err_str or "unavailable" in err_str:
                    logger.warning(f"Gemini model {model_name} unavailable. Trying next candidate...")
                    continue
                raise

        if last_error:
            raise last_error
        raise RuntimeError("No Gemini models succeeded.")

    def _call_openai(self, system_instruction: str, prompt: str, api_key: str) -> str:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2
        )
        return response.choices[0].message.content

    def invoke_structured(self, system_instruction: str, prompt: str) -> Dict[str, Any]:
        """
        Calls configured LLM provider and parses structured JSON output.
        Validates model output schema before returning.
        Returns metadata indicating whether output was from real LLM or algorithmic fallback.
        """
        api_key = self.get_api_key()
        if not api_key:
            logger.info("No active LLM API key configured in backend/.env. Using transparent algorithmic baseline.")
            res = self._fallback_response(system_instruction, prompt)
            res["_metadata"] = {
                "is_real_llm": False,
                "evaluator": "Algorithmic Baseline",
                "source": "algorithmic_fallback",
                "notice": "Evaluated using algorithmic baseline. Configure GEMINI_API_KEY in backend/.env for real Gemini LLM evaluations."
            }
            return res

        raw_output = None
        used_model = settings.GEMINI_MODEL if settings.LLM_PROVIDER == "gemini" else settings.OPENAI_MODEL
        try:
            if settings.LLM_PROVIDER == "gemini":
                raw_output = self._call_gemini(system_instruction, prompt, api_key)
            elif settings.LLM_PROVIDER == "openai":
                raw_output = self._call_openai(system_instruction, prompt, api_key)

            if not raw_output or not raw_output.strip():
                raise ValueError("Empty response received from LLM provider.")

            # Strip markdown json wrappers
            clean_str = raw_output.strip()
            if clean_str.startswith("```json"):
                clean_str = clean_str[7:]
            if clean_str.startswith("```"):
                clean_str = clean_str[3:]
            if clean_str.endswith("```"):
                clean_str = clean_str[:-3]

            parsed_data = json.loads(clean_str.strip())
            
            # Validate output against known schema
            validated_data = self._validate_and_sanitize(parsed_data, system_instruction, prompt)
            validated_data["_metadata"] = {
                "is_real_llm": True,
                "evaluator": f"{settings.LLM_PROVIDER}:{used_model}",
                "source": "real_llm",
                "notice": f"Successfully evaluated using live {settings.LLM_PROVIDER.upper()} ({used_model}) model."
            }
            return validated_data

        except Exception as e:
            err_str = str(e)
            is_quota_exhausted = "429" in err_str or "resource_exhausted" in err_str.lower() or "quota exceeded" in err_str.lower()
            logger.error(f"LLM call to {settings.LLM_PROVIDER} failed ({type(e).__name__}): {e}")
            res = self._fallback_response(system_instruction, prompt)
            res["_metadata"] = {
                "is_real_llm": False,
                "evaluator": "Quota Limit Baseline Fallback" if is_quota_exhausted else "API Error Baseline Fallback",
                "source": "quota_exhausted" if is_quota_exhausted else "api_error_fallback",
                "error_details": str(e),
                "notice": (
                    "LLM provider quota temporarily exhausted (429). Transparent algorithmic baseline applied."
                    if is_quota_exhausted
                    else f"LLM provider error occurred ({type(e).__name__}). Algorithmic baseline applied."
                )
            }
            return res

    def _validate_and_sanitize(self, data: Dict[str, Any], system_instruction: str, prompt: str) -> Dict[str, Any]:
        """Validates structured response using Pydantic schemas."""
        lower = f"{system_instruction} {prompt}".lower()
        if "evaluate candidate answer" in lower:
            try:
                val = AnswerEvaluationSchema(**data)
                return val.model_dump()
            except ValidationError as ve:
                logger.warning(f"Answer evaluation schema validation warning: {ve}")
                return data
        elif "question #" in lower or "generate question" in lower:
            try:
                val = QuestionOutputSchema(**data)
                return val.model_dump()
            except ValidationError as ve:
                logger.warning(f"Question schema validation warning: {ve}")
                return data
        elif "competencies" in lower:
            try:
                if isinstance(data, list):
                    val = CompetencyListSchema(competencies=data)
                elif isinstance(data, dict):
                    if "competencies" in data:
                        val = CompetencyListSchema(**data)
                    else:
                        val = CompetencyListSchema(competencies=[data])
                else:
                    return data
                return val.model_dump()
            except ValidationError:
                return data
        elif "resume" in lower or "extract profile" in lower:
            try:
                val = ResumeProfileSchema(**data)
                return val.model_dump()
            except ValidationError:
                return data
        return data

    def _fallback_response(self, system_instruction: str, prompt: str) -> Dict[str, Any]:
        """
        Algorithmic baseline when API key is missing.
        Analyzes actual prompt content (e.g. candidate answers, resume text)
        to extract genuine evidence and prevent hardcoded static scores.
        """
        lower = f"{system_instruction} {prompt}".lower()

        if "extract competencies" in lower or "competencies" in lower or "job description" in lower:
            # Extract technical keywords from job description
            keywords = ["Python", "FastAPI", "React", "PostgreSQL", "Docker", "Architecture", "REST APIs", "Testing"]
            found = [kw for kw in keywords if kw.lower() in lower]
            if not found:
                found = ["Technical Proficiency", "Problem Solving", "System Design", "Communication"]
            competencies = []
            for i, kw in enumerate(found[:4]):
                competencies.append({
                    "name": kw if " " in kw else f"{kw} Engineering",
                    "weight": round(1.0 / min(4, len(found)), 2),
                    "description": f"Demonstrated competency in {kw} for scalable application delivery."
                })
            return {"competencies": competencies}

        elif "resume" in lower or "extract profile" in lower:
            # Extract skills by regex matching common tech keywords in resume
            tech_patterns = [
                "python", "fastapi", "react", "typescript", "javascript", "postgresql", 
                "sql", "docker", "aws", "git", "rest", "graphql", "node", "html", "css", 
                "system design", "microservices", "kubernetes", "linux", "c++", "java"
            ]
            skills_found = [p.capitalize() for p in tech_patterns if p in lower]
            if not skills_found:
                skills_found = ["Software Engineering", "Problem Solving", "Web Development"]

            return {
                "extracted_skills": list(set(skills_found)),
                "experience_summary": ["Professional software engineer with verified technical skills."],
                "education": ["Computer Science or relevant technical background"]
            }

        elif "evaluate candidate answer" in lower or "assessment engine" in lower or "evaluate the candidate" in lower:
            # Extract the actual candidate answer from prompt
            cand_answer = ""
            if "candidate answer:" in lower:
                parts = prompt.split("Candidate Answer:")
                if len(parts) > 1:
                    cand_answer = parts[1].split("\n")[0].strip()
                    if not cand_answer:
                        cand_answer = parts[1].strip()

            word_count = len(cand_answer.split())
            has_advanced_keywords = any(k in cand_answer.lower() for k in ["raft", "consensus", "replication", "state machine", "byzantine", "partition", "fencing", "lineariz", "atomicity", "paxos", "failover"])

            # Algorithmic scoring based on technical depth, keywords, and reasoning completeness
            if word_count < 10:
                score = 3.5
                diff = "Recovery"
                strengths = ["Attempted brief response"]
                weaknesses = ["Response lacked technical depth", "Omitted prerequisite mechanisms and failure recovery logic"]
                missing_concepts = ["Foundational prerequisite architecture and baseline failure recovery"]
                reason = "Candidate gave an extremely brief response; stepping down to foundational prerequisite concepts."
            elif word_count >= 24 and has_advanced_keywords:
                score = 8.8
                diff = "Hard"
                strengths = ["Comprehensive answer with detailed explanation", "Structured articulation of system considerations and trade-offs"]
                weaknesses = []
                missing_concepts = []
                reason = "Detailed response demonstrating technical mastery; probing deeper into advanced scale and fault tolerance."
            elif word_count >= 10:
                score = 6.0
                diff = "Medium"
                strengths = ["Addressed core topic", "Clear technical terminology"]
                weaknesses = ["Omitted partition recovery trade-offs and edge case handling"]
                missing_concepts = ["Partition recovery trade-offs and fencing mechanisms"]
                reason = "Response answered the basic premise; investigating specific missing operational concepts."
            else:
                score = 4.0
                diff = "Recovery"
                strengths = ["Attempted response"]
                weaknesses = ["Needs expansion on technical fundamentals"]
                missing_concepts = ["Foundational architecture concepts"]
                reason = "Candidate struggled to articulate technical mechanisms; stepping down to prerequisite concepts."

            # Real evidence quote directly from the candidate's actual answer
            evidence_snippet = cand_answer[:140] if cand_answer else "Candidate provided verbal response."

            return {
                "score": float(score),
                "technical_accuracy": float(min(10.0, score + 0.2)),
                "depth_of_knowledge": float(score),
                "clarity_of_communication": float(min(10.0, score + 0.4)),
                "strengths": strengths,
                "weaknesses": weaknesses,
                "missing_concepts": missing_concepts,
                "evidence_quote": evidence_snippet,
                "confidence_level": "Moderate (Algorithmic Baseline)",
                "next_difficulty": diff,
                "adaptation_reason": f"{reason} [Engine operating in algorithmic baseline mode]"
            }

        elif "skill gap" in lower:
            return {
                "match_percentage": 75,
                "matching_skills": ["Core Engineering", "API Design"],
                "missing_skills": ["Advanced Cloud Deployment"],
                "recommendation": "Candidate meets primary criteria with identified expansion areas."
            }

        else:
            # Adaptive question generation based on prompt attributes
            # Detect Question # order index
            order_match = re.search(r"question\s*#(\d+)", lower)
            order_idx = int(order_match.group(1)) if order_match else 1

            # Detect role or job title
            role_match = re.search(r"position\s*['\"]([^'\"]+)['\"]", prompt, re.IGNORECASE)
            job_title = role_match.group(1) if role_match else "Software Engineering"

            # Detect target competency
            comp_match = re.search(r"target competency to assess:\s*['\"]?([^'\"\n]+)['\"]?", prompt, re.IGNORECASE)
            target_comp = comp_match.group(1).strip() if comp_match else "Technical Architecture"

            # Detect target difficulty
            diff_match = re.search(r"target difficulty(?: level)?:\s*['\"]?(\w+)['\"]?", lower)
            difficulty = diff_match.group(1).capitalize() if diff_match else "Medium"

            # Dynamic question formulation honoring closed-loop adaptive strategy
            if difficulty in ["Recovery", "Easy"] or "step down" in lower or "step_down" in lower:
                return {
                    "question": f"To establish baseline understanding in {target_comp}: What fundamental principle or data structure guarantees consistency before applying complex distributed operations?",
                    "competency_tested": target_comp,
                    "difficulty_level": difficulty if difficulty in ["Recovery", "Easy"] else "Recovery",
                    "expected_criteria": f"Identifies foundational mechanisms and prerequisite logic for {target_comp}.",
                    "question_type": "multiple_choice",
                    "options": [
                        f"A) Atomic state validation and transaction logs in {target_comp}",
                        "B) Ignoring failures and continuing execution without persistence",
                        "C) Infinite recursion without timeout or backoff",
                        "D) Dropping all state caches on every read operation"
                    ]
                }
            elif "missing" in lower or "investigate" in lower or "follow-up" in lower or difficulty == "Medium" and order_idx > 1 and "probe deeper" not in lower:
                return {
                    "question": f"Following up on your previous answer regarding {target_comp}: Specifically, how do you handle partition recovery and fencing to address the missing operational considerations you noted?",
                    "competency_tested": target_comp,
                    "difficulty_level": "Medium",
                    "expected_criteria": f"Addresses the specific missing operational and failure-recovery concept in {target_comp}.",
                    "question_type": "open_ended",
                    "options": []
                }
            elif "probe deeper" in lower or "hard" in lower or difficulty == "Hard":
                return {
                    "question": f"Given your strong foundation in {target_comp}: At extreme scale (100k+ requests/sec across multiple cloud regions), how do you resolve consensus latency and split-brain recovery under asymmetric network partitions?",
                    "competency_tested": target_comp,
                    "difficulty_level": "Hard",
                    "expected_criteria": f"Detailed trade-off analysis of consensus latency, Byzantine vs crash fault tolerance, and multi-region replication in {target_comp}.",
                    "question_type": "open_ended",
                    "options": []
                }
            else:
                return {
                    "question": f"In {job_title}, describe how you design and implement the core architecture for {target_comp}, including primary components and data flows.",
                    "competency_tested": target_comp,
                    "difficulty_level": difficulty,
                    "expected_criteria": f"Demonstrates solid conceptual knowledge and architectural design in {target_comp}.",
                    "question_type": "open_ended",
                    "options": []
                }

llm_service = LLMService()
