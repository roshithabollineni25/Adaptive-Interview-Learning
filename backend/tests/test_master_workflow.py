import pytest
import datetime
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import SessionLocal
from app.models.entities import User, Candidate, JobDescription, InterviewSession, InterviewQuestion

client = TestClient(app)

def test_full_recruiter_and_candidate_workflow():
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
    
    # Check email delivery report: SMTP is disabled in dev by default, so it honestly reports configuration_required
    assert sched_data["email_delivery"]["delivered"] is False
    assert "SMTP" in sched_data["email_delivery"]["message"]

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

    # 8. Attempt verification probe with invalid frame -> Must fail gate
    empty_frame = np.ones((400, 400, 3), dtype=np.uint8) * 50
    _, empty_buf = cv2.imencode('.jpg', empty_frame)
    empty_b64 = "data:image/jpeg;base64," + base64.b64encode(empty_buf).decode('utf-8')
    probe_fail = client.post(f"/api/interview/{session_token}/verify-identity", json={
        "probe_frame_base64": empty_b64
    })
    assert probe_fail.status_code == 200
    assert probe_fail.json()["verified"] is False

    # 9. Verify with genuine enrolled face probe -> Must unlock gate & Q1
    probe_pass = client.post(f"/api/interview/{session_token}/verify-identity", json={
        "probe_frame_base64": face_b64
    })
    assert probe_pass.status_code == 200
    assert probe_pass.json()["verified"] is True
    assert "first_question" in probe_pass.json()
    q1 = probe_pass.json()["first_question"]
    assert q1["order_index"] == 1

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

    # 12. Recruiter records human hiring decision
    dec_res = client.patch(f"/api/recruitment/sessions/{session_id}/decision", json={
        "recruiter_decision": "Hired",
        "recruiter_notes": "Candidate proved solid knowledge of distributed consensus and failover mechanisms."
    }, headers=recruiter_headers)
    assert dec_res.status_code == 200
    assert dec_res.json()["decision"] == "Hired"
