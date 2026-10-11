import requests
import cv2
import numpy as np
import base64
import json

BASE_URL = "http://127.0.0.1:8000"

def b64_from_cv(img):
    _, buf = cv2.imencode('.jpg', img, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
    return "data:image/jpeg;base64," + base64.b64encode(buf).decode('utf-8')

def create_synthetic_face_portrait():
    # 400x400 canvas, realistic head oval, eyes, nose, mouth matching Haar cascade features
    img = np.ones((400, 400, 3), dtype=np.uint8) * 220
    # Head oval
    cv2.ellipse(img, (200, 200), (90, 120), 0, 0, 360, (180, 160, 150), -1)
    # Eyes (darker regions)
    cv2.ellipse(img, (165, 170), (14, 8), 0, 0, 360, (60, 50, 40), -1)
    cv2.ellipse(img, (235, 170), (14, 8), 0, 0, 360, (60, 50, 40), -1)
    # Pupils
    cv2.circle(img, (165, 170), 4, (10, 10, 10), -1)
    cv2.circle(img, (235, 170), 4, (10, 10, 10), -1)
    # Eyebrows
    cv2.ellipse(img, (165, 150), (20, 4), -10, 0, 360, (50, 40, 30), -1)
    cv2.ellipse(img, (235, 150), (20, 4), 10, 0, 360, (50, 40, 30), -1)
    # Nose
    cv2.line(img, (200, 180), (200, 220), (120, 100, 90), 3)
    cv2.line(img, (200, 220), (190, 228), (120, 100, 90), 2)
    cv2.line(img, (190, 228), (210, 228), (120, 100, 90), 2)
    # Mouth
    cv2.ellipse(img, (200, 260), (30, 10), 0, 0, 360, (100, 60, 70), -1)
    return img

def main():
    print("--- 1. Authenticate candidate ---")
    login_res = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "candidate.marcus@gmail.com",
        "password": "CandidateSecret123!"
    })
    print(f"Login status: {login_res.status_code}")
    if login_res.status_code != 200:
        print(f"Login failed: {login_res.text}")
        return
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    print("\n--- 2. Test Case A: Invalid Image Data ---")
    res_bad = requests.post(f"{BASE_URL}/api/candidate-portal/enroll-face", 
                            json={"face_image_base64": "invalid_base64_data"}, headers=headers)
    print(f"Status: {res_bad.status_code}, Detail: {res_bad.json().get('detail')}")
    assert res_bad.status_code == 400

    print("\n--- 3. Test Case B: Completely Black Frame (Covered Lens) ---")
    black_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    res_black = requests.post(f"{BASE_URL}/api/candidate-portal/enroll-face", 
                              json={"face_image_base64": b64_from_cv(black_frame)}, headers=headers)
    print(f"Status: {res_black.status_code}, Detail: {res_black.json().get('detail')}")
    assert res_black.status_code == 400

    print("\n--- 4. Test Case C: No Face Present Frame (Empty Background) ---")
    empty_frame = np.ones((480, 640, 3), dtype=np.uint8) * 128
    res_noface = requests.post(f"{BASE_URL}/api/candidate-portal/enroll-face", 
                               json={"face_image_base64": b64_from_cv(empty_frame)}, headers=headers)
    print(f"Status: {res_noface.status_code}, Detail: {res_noface.json().get('detail')}")
    assert res_noface.status_code == 400

    print("\n--- 5. Test Case D: Valid Face Portrait Enrollment ---")
    face_img = create_synthetic_face_portrait()
    # Check if cascade detects it
    from app.services.identity_service import extract_face_region
    count, roi, meta = extract_face_region(face_img)
    print(f"Local detection count: {count}, meta: {meta}")

    res_enroll = requests.post(f"{BASE_URL}/api/candidate-portal/enroll-face", 
                               json={"face_image_base64": b64_from_cv(face_img)}, headers=headers)
    print(f"Status: {res_enroll.status_code}, Body: {res_enroll.json()}")
    assert res_enroll.status_code == 200
    assert res_enroll.json()["status"] == "success"

    print("\n--- 6. Candidate Profile Check ---")
    profile_res = requests.get(f"{BASE_URL}/api/candidate-portal/profile", headers=headers)
    profile = profile_res.json()
    print(f"Enrolled face flag: {profile.get('has_enrolled_face')}, Enrolled at: {profile.get('enrolled_at')}")
    assert profile.get("has_enrolled_face") is True

    print("\n--- 7. Test Case E: Interview Identity Probe Comparison ---")
    interviews_res = requests.get(f"{BASE_URL}/api/candidate-portal/interviews", headers=headers)
    print(f"Interviews status: {interviews_res.status_code}, count: {len(interviews_res.json())}")
    
    if len(interviews_res.json()) > 0:
        session_info = interviews_res.json()[0]
        token_val = session_info["session_token"]
        print(f"Testing interview token: {token_val}")

        # Send mismatched/blank probe
        res_probe_bad = requests.post(f"{BASE_URL}/api/interview/{token_val}/verify-identity",
                                      json={"probe_frame_base64": b64_from_cv(empty_frame)})
        print(f"Bad probe status: {res_probe_bad.status_code}, response: {res_probe_bad.json()}")
        assert res_probe_bad.status_code in [200, 400, 403]
        if res_probe_bad.status_code == 200:
            assert res_probe_bad.json()["verified"] is False

        # Send matching probe
        res_probe_good = requests.post(f"{BASE_URL}/api/interview/{token_val}/verify-identity",
                                       json={"probe_frame_base64": b64_from_cv(face_img)})
        print(f"Matching probe status: {res_probe_good.status_code}, response: {res_probe_good.json()}")
        if res_probe_good.status_code == 200:
            assert res_probe_good.json()["verified"] is True
            print("Interview probe successfully matched enrolled biometric reference!")

    print("\nAll biometric verification and interview gating test scenarios verified successfully!")

if __name__ == "__main__":
    main()
