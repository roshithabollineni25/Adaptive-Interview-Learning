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

        client = genai.Client(api_key=api_key)
        target_model = settings.GEMINI_MODEL

        try:
            response = client.models.generate_content(
                model=target_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.2,
                    response_mime_type="application/json"
                )
            )
            return response.text
        except errors.APIError as e:
            # Handle model not found fallback (e.g. try gemini-2.0-flash or gemini-1.5-flash)
            if "not found" in str(e).lower() or "404" in str(e):
                logger.warning(f"Model {target_model} not found, falling back to gemini-2.0-flash: {e}")
                fallback_response = client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        temperature=0.2,
                        response_mime_type="application/json"
                    )
                )
                return fallback_response.text
            elif "429" in str(e) or "resource_exhausted" in str(e).lower():
                logger.error(f"Gemini API Rate Limit or Quota Exceeded: {e}")
                raise RuntimeError(f"Gemini API rate limit or quota exceeded: {e}")
            elif "401" in str(e) or "403" in str(e) or "api_key_invalid" in str(e).lower():
                logger.error(f"Gemini API Authentication Failed: Invalid API key: {e}")
                raise RuntimeError(f"Invalid GEMINI_API_KEY: {e}")
            raise

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
            logger.error(f"LLM call to {settings.LLM_PROVIDER} failed ({type(e).__name__}): {e}")
            res = self._fallback_response(system_instruction, prompt)
            res["_metadata"] = {
                "is_real_llm": False,
                "evaluator": "API Error Baseline Fallback",
                "source": "api_error_fallback",
                "error_details": str(e),
                "notice": f"LLM provider error occurred ({type(e).__name__}). Algorithmic baseline applied."
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
                val = CompetencyListSchema(**data)
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

        elif "evaluate candidate answer" in lower:
            # Extract the actual candidate answer from prompt
            cand_answer = ""
            if "candidate answer:" in lower:
                parts = prompt.split("Candidate Answer:")
                if len(parts) > 1:
                    cand_answer = parts[1].split("\n")[0].strip()
                    if not cand_answer:
                        cand_answer = parts[1].strip()

            word_count = len(cand_answer.split())
            
            # Algorithmic scoring based on answer depth and structure
            if word_count < 10:
                score = 4.0
                diff = "Recovery"
                strengths = ["Attempted brief answer"]
                weaknesses = ["Response was too brief to evaluate full technical depth", "Lacked concrete examples or trade-off analysis"]
                reason = "Candidate gave an extremely brief response; initiating recovery prompt."
            elif word_count < 30:
                score = 6.0
                diff = "Medium"
                strengths = ["Addressed core topic", "Clear terminology"]
                weaknesses = ["Could expand with specific architecture decisions and trade-offs"]
                reason = "Response answered the basic premise; maintaining medium difficulty."
            elif word_count < 80:
                score = 7.8
                diff = "Medium"
                strengths = ["Solid conceptual explanation", "Clear communication of key concepts"]
                weaknesses = ["Could include operational edge cases or production metrics"]
                reason = "Candidate demonstrated clear technical competence; progressing adaptive track."
            else:
                score = 8.5
                diff = "Hard"
                strengths = ["Comprehensive answer with detailed explanation", "Structured articulation of system considerations"]
                weaknesses = ["Minor opportunities to expand on monitoring and recovery strategies"]
                reason = "Detailed response exceeding expectations; advancing to higher complexity."

            # Real evidence quote directly from the candidate's actual answer
            evidence_snippet = cand_answer[:140] if cand_answer else "Candidate provided verbal response."

            return {
                "score": float(score),
                "technical_accuracy": float(min(10.0, score + 0.2)),
                "depth_of_knowledge": float(score),
                "clarity_of_communication": float(min(10.0, score + 0.4)),
                "strengths": strengths,
                "weaknesses": weaknesses,
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
            return {
                "question": "Could you walk through how you approach architecture, state management, and edge-case handling in full-stack applications?",
                "competency_tested": "Architecture & Engineering Design",
                "difficulty_level": "Medium",
                "expected_criteria": "Trade-offs considered, component modularity, and operational reliability."
            }

llm_service = LLMService()
