import pytest
import datetime
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import SessionLocal
from app.models.entities import User, Candidate, JobDescription, InterviewSession, InterviewQuestion

from unittest.mock import patch
from app.services.llm_service import llm_service

client = TestClient(app)

def mock_invoke_structured(system_instruction: str, prompt: str):
    """Deterministic mock for LLM calls during automated workflow tests to avoid burning real quota."""
    lower = f"{system_instruction} {prompt}".lower()
    if "competencies" in lower:
        return {
            "competencies": [
                {"name": "Python Systems", "weight": 0.4, "description": "High performance backend systems in Python"},
                {"name": "Distributed Storage", "weight": 0.3, "description": "PostgreSQL HA and distributed caching"},
                {"name": "API Design", "weight": 0.3, "description": "FastAPI and resilient REST architectures"}
            ],
            "_metadata": {"is_real_llm": True, "evaluator": "test_mock", "source": "mock"}
        }
    elif "resume" in lower or "extract profile" in lower or "technical skills" in lower:
        return {
            "extracted_skills": ["Python", "FastAPI", "Docker", "Distributed Consensus", "PostgreSQL"],
            "experience_summary": ["PhD in Computer Systems", "Senior Distributed Systems Engineer"],
            "education": ["PhD in Computer Systems"],
            "_metadata": {"is_real_llm": True, "evaluator": "test_mock", "source": "mock"}
        }
    elif "evaluate candidate answer" in lower or "assessment engine" in lower:
        return {
            "score": 8.5,
            "technical_accuracy": 8.5,
            "depth_of_knowledge": 8.0,
            "clarity_of_communication": 9.0,
            "strengths": ["Clear explanation of Raft consensus and PostgreSQL replication"],
            "weaknesses": ["Could expand on network partition recovery"],
            "evidence_quote": "Raft consensus and PostgreSQL read replicas with automated failover",
            "confidence_level": "High",
            "next_difficulty": "Hard",
            "adaptation_reason": "Candidate exhibited advanced distributed systems knowledge.",
            "_metadata": {"is_real_llm": True, "evaluator": "test_mock", "source": "mock"}
        }
    elif "question #" in lower or "generate question" in lower:
        target_comp = "Distributed Storage"
        if "target competency to assess:" in lower:
            import re
            m = re.search(r"target competency to assess:\s*['\"]([^'\"]+)['\"]", prompt, re.IGNORECASE)
            if m:
                target_comp = m.group(1)
        return {
            "question": f"How do you design and test resilient components for {target_comp}?",
            "competency_tested": target_comp,
            "difficulty_level": "Medium",
            "expected_criteria": f"Understanding of consensus, trade-offs, and practical depth in {target_comp}.",
            "_metadata": {"is_real_llm": True, "evaluator": "test_mock", "source": "mock"}
        }
    return {
        "competencies": [{"name": "Core Engineering", "weight": 1.0, "description": "Engineering"}],
        "extracted_skills": ["Python"],
        "score": 8.0,
        "_metadata": {"is_real_llm": True, "evaluator": "test_mock", "source": "mock"}
    }

def test_full_recruiter_and_candidate_workflow():
    with patch.object(llm_service, "invoke_structured", side_effect=mock_invoke_structured):
        _run_full_recruiter_and_candidate_workflow()

def _run_full_recruiter_and_candidate_workflow():
    # 1. Register Recruiter
    recruiter_email = f"recruiter.test.{datetime.datetime.utcnow().timestamp()}@adaptive.io"
    reg_recruiter = client.post("/api/auth/register", json={
        "email": recruiter_email,
        "password": "RecruiterPassword123!",
        "full_name": "Chief Technical Recruiter",
        "role": "recruiter"
    })
    assert reg_recruiter.status_code == 200
    recruiter_token = reg_recruiter.json()["access_token"]
    recruiter_headers = {"Authorization": f"Bearer {recruiter_token}"}

    # 2. Recruiter creates Job Description
    job_res = client.post("/api/recruitment/jobs", json={
        "title": "Principal Distributed Systems Engineer",
        "department": "Platform Core",
        "raw_text": "We need an engineer experienced with Python, FastAPI, distributed caching, and PostgreSQL high availability.",
        "experience_level": "Senior"
    }, headers=recruiter_headers)
    assert job_res.status_code == 200
    job_id = job_res.json()["id"]
    assert len(job_res.json()["required_competencies"]) > 0

    # 3. Register Candidate
    cand_email = f"candidate.test.{datetime.datetime.utcnow().timestamp()}@gmail.com"
    reg_cand = client.post("/api/auth/register", json={
        "email": cand_email,
        "password": "CandidatePassword123!",
        "full_name": "Dr. Sarah Chen",
        "role": "candidate"
    })
    assert reg_cand.status_code == 200
    cand_token = reg_cand.json()["access_token"]
    cand_headers = {"Authorization": f"Bearer {cand_token}"}

    # 4. Candidate submits Job Application & Resume
    resume_content = b"Sarah Chen, PhD in Computer Systems. Extensive background in Python, FastAPI, Docker, and distributed consensus."
    app_res = client.post(
        "/api/candidate-portal/application",
        data={"target_role": "Principal Distributed Systems Engineer"},
        files={"file": ("sarah_chen_resume.txt", resume_content, "text/plain")},
        headers=cand_headers
    )
    assert app_res.status_code == 200
    cand_profile = app_res.json()["candidate"]
    cand_id = cand_profile["id"]
    assert cand_profile["target_role"] == "Principal Distributed Systems Engineer"
    assert len(cand_profile["extracted_skills"]) > 0

    # 5. Recruiter schedules Interview Session (Window configured for right now)
    now = datetime.datetime.utcnow()
    scheduled_start = now.isoformat()
    sched_res = client.post("/api/recruitment/sessions/schedule", json={
        "candidate_id": cand_id,
        "job_description_id": job_id,
        "scheduled_start": scheduled_start
    }, headers=recruiter_headers)
    assert sched_res.status_code == 200
    sched_data = sched_res.json()
    session_token = sched_data["session_token"]
    session_id = sched_data["session_id"]
    
    # Check email delivery report: reports configuration_required when BREVO_API_KEY is not set
    assert sched_data["email_delivery"]["delivered"] is False
    assert "brevo" in sched_data["email_delivery"]["message"].lower() or "provider" in sched_data["email_delivery"]["message"].lower()

    # 6. Candidate accesses Gateway
    gw_res = client.get(f"/api/interview/{session_token}")
    assert gw_res.status_code == 200
    gw_data = gw_res.json()
    assert gw_data["identity_verified"] is False
    assert gw_data["active_question"] is None  # Gate closed until identity verified

    # 7. Candidate enrolls Biometric Reference (using synthetic frontal portrait)
    import cv2
    import numpy as np
    import base64

    # Create realistic face portrait canvas matching Haar features
    face_canvas = np.ones((400, 400, 3), dtype=np.uint8) * 220
    cv2.ellipse(face_canvas, (200, 200), (90, 120), 0, 0, 360, (180, 160, 150), -1)
    cv2.ellipse(face_canvas, (165, 170), (14, 8), 0, 0, 360, (60, 50, 40), -1)
    cv2.ellipse(face_canvas, (235, 170), (14, 8), 0, 0, 360, (60, 50, 40), -1)
    cv2.circle(face_canvas, (165, 170), 4, (10, 10, 10), -1)
    cv2.circle(face_canvas, (235, 170), 4, (10, 10, 10), -1)
    cv2.ellipse(face_canvas, (165, 150), (20, 4), -10, 0, 360, (50, 40, 30), -1)
    cv2.ellipse(face_canvas, (235, 150), (20, 4), 10, 0, 360, (50, 40, 30), -1)
    cv2.line(face_canvas, (200, 180), (200, 220), (120, 100, 90), 3)
    cv2.line(face_canvas, (200, 220), (190, 228), (120, 100, 90), 2)
    cv2.line(face_canvas, (190, 228), (210, 228), (120, 100, 90), 2)
    cv2.ellipse(face_canvas, (200, 260), (30, 10), 0, 0, 360, (100, 60, 70), -1)
    _, buf = cv2.imencode('.jpg', face_canvas)
    face_b64 = "data:image/jpeg;base64," + base64.b64encode(buf).decode('utf-8')

    enroll_res = client.post("/api/candidate-portal/enroll-face", json={
        "face_image_base64": face_b64
    }, headers=cand_headers)
    assert enroll_res.status_code == 200
    assert enroll_res.json()["status"] == "success"

    # 8. Attempt verification probe with invalid frame or missing ID card -> Must fail gate
    empty_frame = np.ones((400, 400, 3), dtype=np.uint8) * 50
    _, empty_buf = cv2.imencode('.jpg', empty_frame)
    empty_b64 = "data:image/jpeg;base64," + base64.b64encode(empty_buf).decode('utf-8')
    probe_fail = client.post(f"/api/interview/{session_token}/verify-identity", json={
        "probe_frame_base64": empty_b64
    })
    assert probe_fail.status_code == 200
    assert probe_fail.json()["verified"] is False

    # Create synthetic ID card frame with realistic rectangular shape and text
    id_card_canvas = np.ones((300, 450, 3), dtype=np.uint8) * 240
    cv2.rectangle(id_card_canvas, (20, 20), (430, 280), (70, 70, 70), 3)
    cv2.putText(id_card_canvas, "OFFICIAL IDENTITY CARD", (40, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (20, 20, 20), 2)
    cv2.putText(id_card_canvas, "DR. SARAH CHEN", (40, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (50, 50, 50), 2)
    cv2.rectangle(id_card_canvas, (40, 130), (140, 250), (120, 120, 120), 2)
    _, id_buf = cv2.imencode('.jpg', id_card_canvas)
    id_card_b64 = "data:image/jpeg;base64," + base64.b64encode(id_buf).decode('utf-8')

    # 9. Verify with genuine enrolled face probe and mandatory ID card -> Must unlock gate & Q1
    probe_pass = client.post(f"/api/interview/{session_token}/verify-identity", json={
        "probe_frame_base64": face_b64,
        "id_card_frame_base64": id_card_b64
    })
    assert probe_pass.status_code == 200
    assert probe_pass.json()["verified"] is True
    assert "first_question" in probe_pass.json()
    q1 = probe_pass.json()["first_question"]
    assert q1["order_index"] == 1
    assert "question_type" in q1

    # 10. Candidate answers questions adaptively
    for idx in range(1, 6):
        ans_res = client.post(f"/api/interview/{session_token}/submit-answer", json={
            "answer_text": "In distributed architectures, we maintain high availability using Raft consensus and PostgreSQL read replicas with automated failover and idempotency keys to protect state transitions."
        })
        assert ans_res.status_code == 200
        ans_data = ans_res.json()
        if ans_data.get("interview_completed"):
            break

    # 11. Recruiter reviews completed session report & dossier
    dossier_res = client.get(f"/api/recruitment/sessions/{session_id}", headers=recruiter_headers)
    assert dossier_res.status_code == 200
    dossier = dossier_res.json()
    assert dossier["status"] == "completed"
    assert dossier["final_score"] is not None
    assert dossier["identity_verified"] is True
    assert dossier["skill_gap_analysis"] is not None
    assert len(dossier["questions"]) > 0

    # 12. Recruiter records human hiring decision with candidate feedback and confidential internal notes
    dec_res = client.patch(f"/api/recruitment/sessions/{session_id}/decision", json={
        "recruiter_decision": "Selected",
        "recruiter_notes": "CONFIDENTIAL: Strong algorithms mastery, recommended level L5 senior.",
        "candidate_feedback": "Exceptional understanding of consensus algorithms and resilience patterns."
    }, headers=recruiter_headers)
    assert dec_res.status_code == 200
    assert dec_res.json()["decision"] == "Selected"

    # 12b. Candidate views their dashboard interviews: must see "Selected" and approved feedback, but NOT confidential recruiter notes
    cand_decision_view = client.get("/api/candidate-portal/interviews", headers=cand_headers)
    assert cand_decision_view.status_code == 200
    cand_sessions = cand_decision_view.json()
    assert len(cand_sessions) >= 1
    session_item = next(s for s in cand_sessions if s["id"] == session_id)
    assert session_item["decision_status"] == "Selected"
    assert session_item["candidate_feedback"] == "Exceptional understanding of consensus algorithms and resilience patterns."
    # Strict confidentiality check: internal notes must NOT be present in candidate payload
    assert "recruiter_notes" not in session_item
    assert "CONFIDENTIAL" not in str(cand_decision_view.content)

    # 13. Test Scheduling a new session for Reschedule & Delete verification
    sched2_res = client.post("/api/recruitment/sessions/schedule", json={
        "candidate_id": cand_id,
        "job_description_id": job_id,
        "scheduled_start": (datetime.datetime.utcnow() + datetime.timedelta(hours=2)).isoformat()
    }, headers=recruiter_headers)
    assert sched2_res.status_code == 200
    sess2_id = sched2_res.json()["session_id"]

    # 14. Recruiter reschedules session to tomorrow
    resched_time = (datetime.datetime.utcnow() + datetime.timedelta(days=1)).isoformat()
    resched_res = client.patch(f"/api/recruitment/sessions/{sess2_id}/reschedule", json={
        "new_scheduled_start": resched_time
    }, headers=recruiter_headers)
    assert resched_res.status_code == 200
    assert resched_res.json()["status"] == "scheduled"

    # 15. Candidate views updated interview list reflecting rescheduled time
    cand_invites = client.get("/api/candidate-portal/interviews", headers=cand_headers)
    assert cand_invites.status_code == 200
    matching_sess = [s for s in cand_invites.json() if s["id"] == sess2_id]
    assert len(matching_sess) == 1
    assert "interview_url" in matching_sess[0]

    # 16. Recruiter deletes session
    del_res = client.delete(f"/api/recruitment/sessions/{sess2_id}", headers=recruiter_headers)
    assert del_res.status_code == 200
    assert del_res.json()["session_id"] == sess2_id

    # 17. Deleted session is gone from queue
    get_deleted = client.get(f"/api/recruitment/sessions/{sess2_id}", headers=recruiter_headers)
    assert get_deleted.status_code == 404

def test_cors_headers_and_preflight():
    """Verify CORS preflight and production origin allow headers on authenticated and error responses."""
    origin = "https://adaptive-interview-frontend-b2ol.onrender.com"
    
    # 1. Preflight OPTIONS request
    opt_res = client.options("/api/candidate-portal/interviews", headers={
        "Origin": origin,
        "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "Authorization"
    })
    assert opt_res.status_code == 200
    assert opt_res.headers.get("access-control-allow-origin") == origin
    assert opt_res.headers.get("access-control-allow-credentials") == "true"

    # 2. Unauthenticated GET returns 401 with CORS headers preserved
    unauth_res = client.get("/api/candidate-portal/interviews", headers={"Origin": origin})
    assert unauth_res.status_code == 401
    assert unauth_res.headers.get("access-control-allow-origin") == origin

    # 3. 404 Not Found returns CORS headers preserved
    not_found_res = client.get("/api/interview/non-existent-token-12345", headers={"Origin": origin})
    assert not_found_res.status_code == 404
    assert not_found_res.headers.get("access-control-allow-origin") == origin

def test_candidate_routes_registration_and_auth():
    """Verify all candidate portal routes exist and enforce candidate role."""
    # Register a candidate
    email = f"route.cand.{datetime.datetime.utcnow().timestamp()}@adaptive.io"
    reg = client.post("/api/auth/register", json={
        "email": email,
        "password": "Password123!",
        "full_name": "Portal Route Candidate",
        "role": "candidate"
    })
    assert reg.status_code == 200
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # GET /api/candidate-portal/profile
    prof = client.get("/api/candidate-portal/profile", headers=headers)
    assert prof.status_code == 200
    assert prof.json()["email"] == email

    # GET /api/candidate-portal/interviews
    ints = client.get("/api/candidate-portal/interviews", headers=headers)
    assert ints.status_code == 200
    assert isinstance(ints.json(), list)

    # Invalid interview token deep link returns 404
    bad_token = client.get("/api/interview/invalid-token-xyz")
    assert bad_token.status_code == 404
    assert "not found" in bad_token.json()["detail"].lower()

def test_session_detail_robustness():
    """Verify get_session_detail handles scheduled/unevaluated sessions and missing references safely."""
    # Register recruiter
    rec_email = f"rec.detail.{datetime.datetime.utcnow().timestamp()}@adaptive.io"
    reg_rec = client.post("/api/auth/register", json={
        "email": rec_email,
        "password": "Password123!",
        "full_name": "Detail Test Recruiter",
        "role": "recruiter"
    })
    rec_headers = {"Authorization": f"Bearer {reg_rec.json()['access_token']}"}

    # Register candidate & job
    job = client.post("/api/recruitment/jobs", json={
        "title": "Backend SRE",
        "department": "Infrastructure",
        "raw_text": "Python and Linux",
        "experience_level": "Mid"
    }, headers=rec_headers).json()

    cand_res = client.post("/api/auth/register", json={
        "email": f"cand.detail.{datetime.datetime.utcnow().timestamp()}@gmail.com",
        "password": "Password123!",
        "full_name": "Scheduled Only Candidate",
        "role": "candidate"
    })
    assert cand_res.status_code == 200
    cand_data = cand_res.json()
    cand_token = cand_data["access_token"]
    cand_headers = {"Authorization": f"Bearer {cand_token}"}

    # Candidate submits application to have a candidate profile record
    app_res = client.post(
        "/api/candidate-portal/application",
        data={"target_role": "Backend SRE"},
        files={"file": ("resume.txt", b"SRE resume content with kubernetes and python", "text/plain")},
        headers=cand_headers
    )
    assert app_res.status_code == 200
    cand_id = app_res.json()["candidate"]["id"]

    # Schedule session (no questions completed yet, report is null)
    sched_res = client.post("/api/recruitment/sessions/schedule", json={
        "candidate_id": cand_id,
        "job_description_id": job["id"],
        "scheduled_start": datetime.datetime.utcnow().isoformat()
    }, headers=rec_headers)
    assert sched_res.status_code == 200
    sched = sched_res.json()
    sess_id = sched["session_id"]

    # Recruiter calls GET /api/recruitment/sessions/{sess_id}
    detail_res = client.get(f"/api/recruitment/sessions/{sess_id}", headers=rec_headers)
    assert detail_res.status_code == 200
    data = detail_res.json()
    assert data["id"] == sess_id
    assert data["candidate"]["full_name"] is not None
    assert data["job"]["title"] == "Backend SRE"
    assert data["final_score"] is None
    assert data["skill_gap_analysis"] is None
    assert isinstance(data["questions"], list)
    assert len(data["questions"]) == 0

    # Non-existent session returns 404
    not_found = client.get("/api/recruitment/sessions/999999", headers=rec_headers)
    assert not_found.status_code == 404

def test_reschedule_interview_ist():
    """Verify that interview rescheduling correctly handles IST timestamps and rejects past times."""
    ist_tz = datetime.timezone(datetime.timedelta(hours=5, minutes=30))

    # 1. Register Recruiter
    rec_email = f"rec.ist.{datetime.datetime.utcnow().timestamp()}@adaptive.io"
    rec_reg = client.post("/api/auth/register", json={
        "email": rec_email,
        "password": "RecruiterPass123!",
        "full_name": "IST Recruiter",
        "role": "recruiter"
    })
    rec_token = rec_reg.json()["access_token"]
    rec_headers = {"Authorization": f"Bearer {rec_token}"}

    # 2. Create Job
    job = client.post("/api/recruitment/jobs", json={
        "title": "Platform Lead",
        "department": "Infrastructure",
        "raw_text": "Lead platform reliability engineering with Docker, Kubernetes, and FastAPI.",
        "required_competencies": ["Kubernetes", "FastAPI"],
        "experience_level": "Senior"
    }, headers=rec_headers).json()

    # 3. Register Candidate & Submit App
    cand_reg = client.post("/api/auth/register", json={
        "email": f"cand.ist.{datetime.datetime.utcnow().timestamp()}@gmail.com",
        "password": "Password123!",
        "full_name": "Arjun Patel",
        "role": "candidate"
    }).json()
    cand_token = cand_reg["access_token"]
    cand_headers = {"Authorization": f"Bearer {cand_token}"}

    app_res = client.post(
        "/api/candidate-portal/application",
        data={"target_role": "Platform Lead"},
        files={"file": ("resume.txt", b"Platform Lead resume with Kubernetes and FastAPI experience", "text/plain")},
        headers=cand_headers
    )
    cand_id = app_res.json()["candidate"]["id"]

    # 4. Schedule Initial Session
    initial_start = (datetime.datetime.utcnow() + datetime.timedelta(hours=4)).isoformat()
    sched = client.post("/api/recruitment/sessions/schedule", json={
        "candidate_id": cand_id,
        "job_description_id": job["id"],
        "scheduled_start": initial_start
    }, headers=rec_headers).json()
    sess_id = sched["session_id"]

    # 5. Reschedule to a future time in IST (e.g. 3 hours in future with +05:30 offset)
    future_ist = (datetime.datetime.now(ist_tz) + datetime.timedelta(hours=3)).replace(second=0, microsecond=0)
    future_ist_str = future_ist.strftime("%Y-%m-%dT%H:%M:00+05:30")

    resched_res = client.patch(f"/api/recruitment/sessions/{sess_id}/reschedule", json={
        "new_scheduled_start": future_ist_str
    }, headers=rec_headers)
    assert resched_res.status_code == 200
    resched_data = resched_res.json()
    assert resched_data["status"] == "scheduled"
    # Verify the stored start time matches the expected UTC time
    expected_utc = future_ist.astimezone(datetime.timezone.utc).replace(tzinfo=None)
    parsed_stored = datetime.datetime.fromisoformat(resched_data["scheduled_start"])
    assert parsed_stored == expected_utc

    # 6. Attempt to reschedule to a past time in IST (e.g. 2 hours ago with +05:30 offset)
    past_ist = datetime.datetime.now(ist_tz) - datetime.timedelta(hours=2)
    past_ist_str = past_ist.strftime("%Y-%m-%dT%H:%M:00+05:30")

    past_resched_res = client.patch(f"/api/recruitment/sessions/{sess_id}/reschedule", json={
        "new_scheduled_start": past_ist_str
    }, headers=rec_headers)
    assert past_resched_res.status_code == 400
    assert "cannot be in the past" in past_resched_res.json()["detail"].lower()

def test_recruiter_decision_persistence_and_candidate_portal():
    """Verify that all 4 recruiter decisions save cleanly and reflect on the candidate portal."""
    with patch.object(llm_service, "invoke_structured", side_effect=mock_invoke_structured):
        rec_email = f"rec.dec.{datetime.datetime.utcnow().timestamp()}@adaptive.io"
        rec_reg = client.post("/api/auth/register", json={
            "email": rec_email,
            "password": "Password123!",
            "full_name": "Decisions Lead",
            "role": "recruiter"
        }).json()
        rec_headers = {"Authorization": f"Bearer {rec_reg['access_token']}"}

        job = client.post("/api/recruitment/jobs", json={
            "title": "Full Stack Lead",
            "department": "Engineering",
            "raw_text": "Python and React",
            "experience_level": "Senior"
        }, headers=rec_headers).json()

        cand_email = f"cand.dec.{datetime.datetime.utcnow().timestamp()}@gmail.com"
        cand_reg = client.post("/api/auth/register", json={
            "email": cand_email,
            "password": "Password123!",
            "full_name": "Candidate Decision Test",
            "role": "candidate"
        }).json()
        cand_headers = {"Authorization": f"Bearer {cand_reg['access_token']}"}

        app_res = client.post(
            "/api/candidate-portal/application",
            data={"target_role": "Full Stack Lead"},
            files={"file": ("resume.txt", b"Full stack lead resume", "text/plain")},
            headers=cand_headers
        )
        cand_id = app_res.json()["candidate"]["id"]

        sched_res = client.post("/api/recruitment/sessions/schedule", json={
            "candidate_id": cand_id,
            "job_description_id": job["id"],
            "scheduled_start": datetime.datetime.utcnow().isoformat()
        }, headers=rec_headers)
        assert sched_res.status_code == 200
        sched = sched_res.json()
        sess_id = sched["session_id"]

        for test_dec in ["Selected", "On Hold", "Under Review", "Rejected"]:
            patch_res = client.patch(f"/api/recruitment/sessions/{sess_id}/decision", json={
                "recruiter_decision": test_dec,
                "recruiter_notes": f"Internal confidential note for {test_dec}",
                "candidate_feedback": f"Feedback for candidate: {test_dec}"
            }, headers=rec_headers)
            assert patch_res.status_code == 200
            patch_data = patch_res.json()
            assert patch_data["decision"] == test_dec
            assert patch_data["candidate_feedback"] == f"Feedback for candidate: {test_dec}"

            # Verify Candidate Portal lists the decision
            cand_ints = client.get("/api/candidate-portal/interviews", headers=cand_headers).json()
            match_int = next((i for i in cand_ints if i["id"] == sess_id), None)
            assert match_int is not None
            assert match_int["decision_status"] == test_dec
            assert match_int["candidate_feedback"] == f"Feedback for candidate: {test_dec}"

def test_integrity_strike_termination():
    """Verify that 3 tab switches terminate session cleanly and record reason."""
    with patch.object(llm_service, "invoke_structured", side_effect=mock_invoke_structured):
        rec_email = f"rec.int.{datetime.datetime.utcnow().timestamp()}@adaptive.io"
        rec_reg = client.post("/api/auth/register", json={
            "email": rec_email,
            "password": "Password123!",
            "full_name": "Integrity Lead",
            "role": "recruiter"
        }).json()
        rec_headers = {"Authorization": f"Bearer {rec_reg['access_token']}"}

        job = client.post("/api/recruitment/jobs", json={
            "title": "Security Analyst",
            "raw_text": "Security",
            "experience_level": "Mid"
        }, headers=rec_headers).json()

        cand_reg = client.post("/api/auth/register", json={
            "email": f"cand.int.{datetime.datetime.utcnow().timestamp()}@gmail.com",
            "password": "Password123!",
            "full_name": "Proctor Candidate",
            "role": "candidate"
        }).json()
        cand_headers = {"Authorization": f"Bearer {cand_reg['access_token']}"}

        app_res = client.post(
            "/api/candidate-portal/application",
            data={"target_role": "Security Analyst"},
            files={"file": ("resume.txt", b"Security resume", "text/plain")},
            headers=cand_headers
        )
        cand_id = app_res.json()["candidate"]["id"]

        sched_res = client.post("/api/recruitment/sessions/schedule", json={
            "candidate_id": cand_id,
            "job_description_id": job["id"],
            "scheduled_start": datetime.datetime.utcnow().isoformat()
        }, headers=rec_headers)
        assert sched_res.status_code == 200
        sched = sched_res.json()
        sess_id = sched["session_id"]
        token = sched["session_token"]

        # Clean any existing events for this session and add exactly 2 spaced events using test db session
        try:
            from app.models.entities import IntegrityEvent
            from tests.conftest import TestingSessionLocal
            db = TestingSessionLocal()
        except ImportError:
            from app.core.database import SessionLocal
            db = SessionLocal()

        db.query(IntegrityEvent).filter(IntegrityEvent.session_id == sess_id).delete()
        db.commit()
        e1 = IntegrityEvent(session_id=sess_id, event_type="tab_switch", timestamp=datetime.datetime.utcnow() - datetime.timedelta(seconds=40))
        e2 = IntegrityEvent(session_id=sess_id, event_type="tab_switch", timestamp=datetime.datetime.utcnow() - datetime.timedelta(seconds=20))
        db.add(e1)
        db.add(e2)
        db.commit()
        cnt = db.query(IntegrityEvent).filter(IntegrityEvent.session_id == sess_id).count()
        db.close()
        assert cnt == 2, f"Expected 2 events inserted, found {cnt}"

        # The third tab switch event arrives and triggers termination
        r3 = client.post(f"/api/interview/{token}/integrity-event", json={"event_type": "tab_switch"})
        assert r3.status_code == 200
        assert r3.json().get("terminated") is True, f"Got: {r3.json()}"
        assert "terminated" in r3.json()["termination_reason"].lower()

def test_adaptive_intelligence_modules():
    """
    Focused test covering the 5 Core Intelligence Modules:
    Module 1: Adaptive Question Generation & Competency Targeting (untested competencies selected, stopping policy)
    Module 2: Real-Time Candidate Evaluation & Idempotent Answer Submission
    Module 3: Integrity Intelligence (qualifying screenshot capture and telemetry risk assessment)
    Module 4: 4-Tier Resume-to-Interview Skill Gap Intelligence (Demonstrated, Claimed, Not Demonstrated, Not Assessed)
    Module 5: Candidate Decision Intelligence & Dossier Report Persistence
    """
    with patch.object(llm_service, "invoke_structured", side_effect=mock_invoke_structured):
        # 1. Setup recruiter and job with 3 distinct competencies
        rec_email = f"rec.modules.{datetime.datetime.utcnow().timestamp()}@adaptive.io"
        rec_reg = client.post("/api/auth/register", json={
            "email": rec_email,
            "password": "Password123!",
            "full_name": "Lead Evaluator",
            "role": "recruiter"
        }).json()
        rec_headers = {"Authorization": f"Bearer {rec_reg['access_token']}"}

        job_res = client.post("/api/recruitment/jobs", json={
            "title": "Cloud Infrastructure Architect",
            "department": "Platform Engineering",
            "raw_text": "We require Kubernetes, Distributed Storage, and Python Systems architecture expertise.",
            "experience_level": "Senior"
        }, headers=rec_headers)
        assert job_res.status_code == 200
        job_id = job_res.json()["id"]

        # 2. Setup candidate with enrolled face and ID card
        cand_email = f"cand.modules.{datetime.datetime.utcnow().timestamp()}@gmail.com"
        cand_reg = client.post("/api/auth/register", json={
            "email": cand_email,
            "password": "Password123!",
            "full_name": "Dr. Jordan Hayes",
            "role": "candidate"
        }).json()
        cand_headers = {"Authorization": f"Bearer {cand_reg['access_token']}"}

        app_res = client.post(
            "/api/candidate-portal/application",
            data={"target_role": "Cloud Infrastructure Architect"},
            files={"file": ("resume.txt", b"Expertise in Python, Docker, and Distributed Consensus.", "text/plain")},
            headers=cand_headers
        )
        cand_id = app_res.json()["candidate"]["id"]

        # Enroll face with exact facial feature parameters satisfying Haar cascade alt2
        import numpy as np
        import cv2
        import base64
        face_canvas = np.ones((400, 400, 3), dtype=np.uint8) * 220
        cv2.ellipse(face_canvas, (200, 200), (90, 120), 0, 0, 360, (180, 160, 150), -1)
        cv2.ellipse(face_canvas, (165, 170), (14, 8), 0, 0, 360, (60, 50, 40), -1)
        cv2.ellipse(face_canvas, (235, 170), (14, 8), 0, 0, 360, (60, 50, 40), -1)
        cv2.circle(face_canvas, (165, 170), 4, (10, 10, 10), -1)
        cv2.circle(face_canvas, (235, 170), 4, (10, 10, 10), -1)
        cv2.ellipse(face_canvas, (165, 150), (20, 4), -10, 0, 360, (50, 40, 30), -1)
        cv2.ellipse(face_canvas, (235, 150), (20, 4), 10, 0, 360, (50, 40, 30), -1)
        cv2.line(face_canvas, (200, 180), (200, 220), (120, 100, 90), 3)
        cv2.line(face_canvas, (200, 220), (190, 228), (120, 100, 90), 2)
        cv2.line(face_canvas, (190, 228), (210, 228), (120, 100, 90), 2)
        cv2.ellipse(face_canvas, (200, 260), (30, 10), 0, 0, 360, (100, 60, 70), -1)
        _, buf = cv2.imencode('.jpg', face_canvas)
        face_b64 = "data:image/jpeg;base64," + base64.b64encode(buf).decode('utf-8')

        enroll_res = client.post("/api/candidate-portal/enroll-face", json={"face_image_base64": face_b64}, headers=cand_headers)
        assert enroll_res.status_code == 200

        # Schedule interview
        sched_res = client.post("/api/recruitment/sessions/schedule", json={
            "candidate_id": cand_id,
            "job_description_id": job_id,
            "scheduled_start": datetime.datetime.utcnow().isoformat()
        }, headers=rec_headers)
        session_data = sched_res.json()
        token = session_data["session_token"]
        session_id = session_data["session_id"]

        # Synthetic ID card
        id_canvas = np.ones((300, 450, 3), dtype=np.uint8) * 240
        cv2.rectangle(id_canvas, (20, 20), (430, 280), (70, 70, 70), 3)
        cv2.putText(id_canvas, "DR. JORDAN HAYES", (40, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (50, 50, 50), 2)
        _, id_buf = cv2.imencode('.jpg', id_canvas)
        id_b64 = "data:image/jpeg;base64," + base64.b64encode(id_buf).decode('utf-8')

        # Pass identity verification gate
        gate_res = client.post(f"/api/interview/{token}/verify-identity", json={
            "probe_frame_base64": face_b64,
            "id_card_frame_base64": id_b64
        })
        assert gate_res.status_code == 200
        assert gate_res.json()["verified"] is True
        assert "first_question" in gate_res.json()

        # Log an integrity screenshot event (Module 3)
        snap_res = client.post(f"/api/interview/{token}/integrity-event", json={
            "event_type": "face_missing",
            "severity": "high",
            "frame_base64": face_b64,
            "metadata_info": {"reason": "Test camera movement"}
        })
        assert snap_res.status_code == 200

        # Answer Question 1 (Module 2: Real-time evaluation)
        ans1_res = client.post(f"/api/interview/{token}/submit-answer", json={
            "answer_text": "We implement Raft consensus using etcd and state machine replication with automated leader election.",
            "answer_mode": "typed"
        })
        assert ans1_res.status_code == 200
        assert ans1_res.json()["evaluation"]["score"] >= 7.0

        # Idempotency check: duplicate submission on Question 1 does not raise error or duplicate questions
        ans1_dup = client.post(f"/api/interview/{token}/submit-answer", json={
            "question_id": ans1_res.json()["question_id"],
            "answer_text": "We implement Raft consensus using etcd and state machine replication with automated leader election.",
            "answer_mode": "typed"
        })
        assert ans1_dup.status_code == 200
        assert ans1_dup.json()["evaluation"]["idempotent"] is True

        # Answer remaining adaptive questions until interview completes according to adaptive policy
        for i in range(8):
            curr = client.get(f"/api/interview/{token}").json()
            if curr.get("status") == "completed" or not curr.get("active_question"):
                break
            ans_sub = client.post(f"/api/interview/{token}/submit-answer", json={
                "answer_text": f"Response {i}: We leverage distributed partitioning, fencing tokens, and automated heartbeat recovery across regions.",
                "answer_mode": "typed"
            })
            assert ans_sub.status_code == 200
            if ans_sub.json().get("is_interview_complete"):
                break

        # Verify Completed Dossier Report (Modules 4 & 5)
        dossier = client.get(f"/api/recruitment/sessions/{session_id}", headers=rec_headers).json()
        assert dossier["status"] == "completed"
        assert dossier["final_score"] is not None
        assert dossier["final_recommendation"] in ["Strong Hire", "Hire", "Lean No", "No Hire"]

        # Check 4-Tier Skill Gap Analysis (Module 4)
        sg = dossier["skill_gap_analysis"]
        assert "demonstrated" in sg
        assert "claimed_unvalidated" in sg
        assert "not_demonstrated" in sg
        assert "not_assessed" in sg
        assert "detailed_evidence" in sg
        assert len(sg["detailed_evidence"]) > 0

        # Check Evidence Report (Module 5)
        ev_rep = dossier["evidence_report"]
        assert ev_rep is not None
        assert "integrity_summary" in ev_rep
        assert "stopping_rationale" in ev_rep
        assert "suggested_followups" in ev_rep

        # Check integrity screenshot persistence (Module 3)
        assert len(dossier["integrity_events"]) > 0
        screenshot_events = [e for e in dossier["integrity_events"] if e.get("screenshot_base64")]
        assert len(screenshot_events) >= 1


def test_real_time_closed_loop_adaptive_engine():
    """
    Verifies the closed-loop real-time adaptive interview engine:
    1. Strong answer (score >= 7.5) -> updates profile to Demonstrated, probes deeper at Hard difficulty.
    2. Partially correct answer (4.5 <= score < 7.5) -> identifies missing concept, follows up specifically on that concept.
    3. Weak answer (score < 4.5) -> updates profile to Needs Prerequisite Review, steps down to prerequisite fundamentals at Recovery/Easy difficulty.
    4. Mixed performance -> maintains independent difficulty and status per competency.
    5. Reload recovery -> preserves adaptive state, does not reset difficulty, does not lose answers, does not duplicate questions.
    """
    # 1. Setup recruiter and job with defined competencies
    rec_email = f"rec.adaptive.{datetime.datetime.utcnow().timestamp()}@adaptive.io"
    rec_reg = client.post("/api/auth/register", json={
        "email": rec_email,
        "password": "Password123!",
        "full_name": "Senior Systems Architect",
        "role": "recruiter"
    }).json()
    rec_headers = {"Authorization": f"Bearer {rec_reg['access_token']}"}

    job_res = client.post("/api/recruitment/jobs", json={
        "title": "Distributed Systems Engineer",
        "department": "Infrastructure",
        "raw_text": "We require expertise in Distributed Consensus and High-Performance Network Protocols.",
        "experience_level": "Senior"
    }, headers=rec_headers)
    assert job_res.status_code == 200
    job_id = job_res.json()["id"]

    # 2. Setup candidate with enrolled face
    cand_email = f"cand.adaptive.{datetime.datetime.utcnow().timestamp()}@gmail.com"
    cand_reg = client.post("/api/auth/register", json={
        "email": cand_email,
        "password": "Password123!",
        "full_name": "Alex Mercer",
        "role": "candidate"
    }).json()
    cand_headers = {"Authorization": f"Bearer {cand_reg['access_token']}"}

    app_res = client.post(
        "/api/candidate-portal/application",
        data={"target_role": "Distributed Systems Engineer"},
        files={"file": ("resume.txt", b"Expertise in Distributed Systems, Raft, and C++.", "text/plain")},
        headers=cand_headers
    )
    cand_id = app_res.json()["candidate"]["id"]

    import numpy as np
    import cv2
    import base64
    face_canvas = np.ones((400, 400, 3), dtype=np.uint8) * 220
    cv2.ellipse(face_canvas, (200, 200), (90, 120), 0, 0, 360, (180, 160, 150), -1)
    cv2.ellipse(face_canvas, (165, 170), (14, 8), 0, 0, 360, (60, 50, 40), -1)
    cv2.ellipse(face_canvas, (235, 170), (14, 8), 0, 0, 360, (60, 50, 40), -1)
    cv2.circle(face_canvas, (165, 170), 4, (10, 10, 10), -1)
    cv2.circle(face_canvas, (235, 170), 4, (10, 10, 10), -1)
    cv2.ellipse(face_canvas, (165, 150), (20, 4), -10, 0, 360, (50, 40, 30), -1)
    cv2.ellipse(face_canvas, (235, 150), (20, 4), 10, 0, 360, (50, 40, 30), -1)
    cv2.line(face_canvas, (200, 180), (200, 220), (120, 100, 90), 3)
    cv2.line(face_canvas, (200, 220), (190, 228), (120, 100, 90), 2)
    cv2.line(face_canvas, (190, 228), (210, 228), (120, 100, 90), 2)
    cv2.ellipse(face_canvas, (200, 260), (30, 10), 0, 0, 360, (100, 60, 70), -1)
    _, buf = cv2.imencode('.jpg', face_canvas)
    face_b64 = "data:image/jpeg;base64," + base64.b64encode(buf).decode('utf-8')

    enroll_res = client.post("/api/candidate-portal/enroll-face", json={"face_image_base64": face_b64}, headers=cand_headers)
    assert enroll_res.status_code == 200

    # 3. Schedule interview
    sched_res = client.post("/api/recruitment/sessions/schedule", json={
        "candidate_id": cand_id,
        "job_description_id": job_id,
        "scheduled_start": datetime.datetime.utcnow().isoformat()
    }, headers=rec_headers)
    session_data = sched_res.json()
    token = session_data["session_token"]
    session_id = session_data["session_id"]

    # 4. Pass biometric and ID card verification gate
    id_canvas = np.ones((300, 450, 3), dtype=np.uint8) * 240
    cv2.rectangle(id_canvas, (20, 20), (430, 280), (70, 70, 70), 3)
    cv2.putText(id_canvas, "ALEX MERCER", (40, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (50, 50, 50), 2)
    _, id_buf = cv2.imencode('.jpg', id_canvas)
    id_b64 = "data:image/jpeg;base64," + base64.b64encode(id_buf).decode('utf-8')

    gate_res = client.post(f"/api/interview/{token}/verify-identity", json={
        "probe_frame_base64": face_b64,
        "id_card_frame_base64": id_b64
    })
    assert gate_res.status_code == 200
    q1 = gate_res.json()["first_question"]
    assert q1["order_index"] == 1
    assert q1["difficulty_level"] == "Medium"

    # 5. CYCLE 1: Strong Answer -> Probe deeper at Hard difficulty
    ans1_res = client.post(f"/api/interview/{token}/submit-answer", json={
        "question_id": q1["id"],
        "answer_text": "We implement Raft consensus using state machine replication, leader election heartbeats, term counters, and log compaction with snapshots to guarantee safety and liveness under crash fault conditions.",
        "answer_mode": "typed"
    })
    assert ans1_res.status_code == 200
    ans1_data = ans1_res.json()
    assert ans1_data["evaluation"]["score"] >= 7.5
    assert ans1_data["next_question_available"] is True
    q2 = ans1_data["next_question"]

    # Verify that strong performance on Q1 probed deeper into advanced scale at Hard difficulty
    assert q2["order_index"] == 2
    assert q2["difficulty_level"] == "Hard"
    assert "probe" in q2.get("adaptation_reason", "").lower() or "hard" in q2.get("adaptation_reason", "").lower() or "strong" in q2.get("adaptation_reason", "").lower()

    # 6. CYCLE 2: Partially Correct Answer on Q2 -> Focuses on Missing Concept at Medium difficulty
    ans2_res = client.post(f"/api/interview/{token}/submit-answer", json={
        "question_id": q2["id"],
        "answer_text": "We replicate across nodes with term numbers, but during network partitions we allow local reads.",
        "answer_mode": "typed"
    })
    assert ans2_res.status_code == 200
    ans2_data = ans2_res.json()
    assert 4.5 <= ans2_data["evaluation"]["score"] < 7.5
    assert ans2_data["next_question_available"] is True
    q3 = ans2_data["next_question"]

    # Verify that partially correct answer triggered focused investigation of missing concept
    assert q3["order_index"] == 3
    assert q3["difficulty_level"] == "Medium"
    assert "missing" in q3.get("adaptation_reason", "").lower() or "investigating" in q3.get("adaptation_reason", "").lower()

    # 7. CYCLE 3: Weak / Flawed Answer on Q3 -> Steps down to prerequisite fundamentals at Recovery/Easy difficulty
    ans3_res = client.post(f"/api/interview/{token}/submit-answer", json={
        "question_id": q3["id"],
        "answer_text": "Just reboot.",
        "answer_mode": "typed"
    })
    assert ans3_res.status_code == 200
    ans3_data = ans3_res.json()
    assert ans3_data["evaluation"]["score"] < 4.5
    assert ans3_data["next_question_available"] is True
    q4 = ans3_data["next_question"]

    # Verify that weak answer stepped down to fundamental prerequisite concepts at Recovery/Easy difficulty
    assert q4["order_index"] == 4
    assert q4["difficulty_level"] in ["Recovery", "Easy"]
    assert "prerequisite" in q4.get("adaptation_reason", "").lower() or "step" in q4.get("adaptation_reason", "").lower()

    # 8. Reload Resilience: reloading during active question recovers exact state without resetting difficulty
    reload_res = client.get(f"/api/interview/{token}")
    assert reload_res.status_code == 200
    reload_data = reload_res.json()
    assert reload_data["active_question"]["id"] == q4["id"]
    assert reload_data["active_question"]["difficulty_level"] == q4["difficulty_level"]
    assert reload_data["total_questions_completed"] == 3

    # 9. Answer Q4 to satisfy MIN_QUESTIONS_PER_SESSION and verify competency profile
    ans4_res = client.post(f"/api/interview/{token}/submit-answer", json={
        "question_id": q4["id"],
        "answer_text": "A) Atomic state validation and transaction logs in Distributed Consensus",
        "answer_mode": "typed"
    })
    assert ans4_res.status_code == 200

    # 10. Verify Completed Dossier and Persistent Competency Profile
    dossier = client.get(f"/api/recruitment/sessions/{session_id}", headers=rec_headers).json()
    assert "skill_gap_analysis" in dossier
    profile = dossier["skill_gap_analysis"].get("competency_profile")
    assert profile is not None
    assert len(profile) > 0
    # Confirm that candidate's performance history and scores were tracked per competency
    tracked_comps = [c for c in profile.values() if c.get("questions_count", 0) > 0]
    assert len(tracked_comps) > 0
    assert tracked_comps[0]["average_score"] is not None
    assert len(tracked_comps[0]["history"]) > 0





