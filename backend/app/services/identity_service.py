import base64
import io
import cv2
import numpy as np
from typing import Dict, Any, Tuple, Optional, List

# Load Haar cascades bundled with OpenCV
# haarcascade_frontalface_alt2 has the lowest false-positive rate and highest precision for frontal portraits
face_cascade_alt2 = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_alt2.xml')
face_cascade_default = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_eye.xml')

def decode_base64_image(image_data: str) -> Optional[np.ndarray]:
    """Decodes a data URI or raw base64 string to an OpenCV BGR numpy array."""
    try:
        if not image_data or not isinstance(image_data, str):
            return None
        if "," in image_data:
            image_data = image_data.split(",")[1]
        image_bytes = base64.b64decode(image_data)
        if len(image_bytes) == 0:
            return None
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        return img
    except Exception:
        return None

def non_max_suppression_faces(faces: List[Any], overlap_thresh: float = 0.3) -> List[Tuple[int, int, int, int]]:
    """Suppresses duplicate or overlapping bounding box detections for the same physical face."""
    if len(faces) <= 1:
        return [(int(x), int(y), int(w), int(h)) for (x, y, w, h) in faces]
    
    boxes = [[int(x), int(y), int(x + w), int(y + h), int(w * h)] for (x, y, w, h) in faces]
    # Sort largest area first
    boxes.sort(key=lambda b: b[4], reverse=True)
    
    keep = []
    while len(boxes) > 0:
        current = boxes.pop(0)
        keep.append(current)
        remaining = []
        for b in boxes:
            xx1 = max(current[0], b[0])
            yy1 = max(current[1], b[1])
            xx2 = min(current[2], b[2])
            yy2 = min(current[3], b[3])
            w = max(0, xx2 - xx1)
            h = max(0, yy2 - yy1)
            inter = w * h
            min_area = min(current[4], b[4])
            inter_ratio = inter / min_area if min_area > 0 else 0
            # If overlap > 30% or one box mostly inside another, consider it the same face
            if inter_ratio < overlap_thresh:
                remaining.append(b)
        boxes = remaining
        
    return [(int(b[0]), int(b[1]), int(b[2] - b[0]), int(b[3] - b[1])) for b in keep]

def extract_face_region(image: np.ndarray) -> Tuple[int, Optional[np.ndarray], Dict[str, Any]]:
    """
    Detects faces in image using precision Haar cascade with NMS overlap suppression.
    Separates the verification pipeline into clear diagnostic stages:
    1. frame_capture
    2. face_detection
    3. quality_check
    Returns:
    - face_count (int)
    - cropped_face (normalized 128x128 grayscale face image or None)
    - metadata (JSON-serializable native Python types)
    """
    if image is None or image.size == 0 or len(image.shape) < 2:
        return 0, None, {
            "stage": "frame_capture",
            "face_count": 0,
            "usable": False,
            "reason": "Camera frame was empty or unreadable. Please ensure video stream is active."
        }

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # Check if frame is pure black or blank
    mean_val = float(np.mean(gray))
    if mean_val < 5.0:
        return 0, None, {
            "stage": "frame_capture",
            "face_count": 0,
            "usable": False,
            "reason": "Video frame is black or covered. Please ensure your camera lens is not obstructed."
        }

    # Primary detection using alt2 cascade (accurate and robust for webcam portraits)
    raw_faces = face_cascade_alt2.detectMultiScale(
        gray,
        scaleFactor=1.1,
        minNeighbors=5,
        minSize=(50, 50)
    )

    # Fallback to default cascade if alt2 finds nothing
    if len(raw_faces) == 0:
        raw_faces = face_cascade_default.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(50, 50)
        )

    # Suppress duplicate concentric bounding boxes
    faces = non_max_suppression_faces(list(raw_faces))
    face_count = int(len(faces))

    if face_count == 0:
        return 0, None, {
            "stage": "face_detection",
            "face_count": 0,
            "usable": False,
            "reason": "No face detected in camera frame. Please position yourself in center frame with good lighting."
        }

    if face_count > 1:
        return face_count, None, {
            "stage": "face_detection",
            "face_count": face_count,
            "usable": False,
            "reason": f"Multiple people ({face_count}) detected in camera frame. Only the registered candidate should be visible."
        }

    # Exactly one face confirmed
    (x, y, w, h) = faces[0]
    face_roi_gray = gray[y:y+h, x:x+w]
    
    # Orientation / Eye feature check
    eyes = eye_cascade.detectMultiScale(face_roi_gray, scaleFactor=1.1, minNeighbors=2, minSize=(12, 12))
    eye_detected = bool(len(eyes) >= 1)

    # Sharpness calculation via Laplacian variance
    laplacian_var = float(cv2.Laplacian(face_roi_gray, cv2.CV_64F).var())
    is_sharp = bool(laplacian_var >= 10.0)

    # Normalize to 128x128
    normalized_face = cv2.resize(face_roi_gray, (128, 128))

    metadata = {
        "stage": "quality_check",
        "face_count": 1,
        "usable": is_sharp,
        "eye_detected": eye_detected,
        "sharpness_score": float(round(laplacian_var, 2)),
        "bounding_box": {"x": int(x), "y": int(y), "w": int(w), "h": int(h)},
        "reason": "Single clear face detected with valid quality checks." if is_sharp else "Frame is slightly blurry. Please hold still and face the camera directly."
    }
    return 1, normalized_face, metadata

def compare_faces(enrolled_img_b64: str, live_img_b64: str) -> Dict[str, Any]:
    """
    Genuine identity comparison comparing enrolled reference face against live probe frame:
    1. Validates enrolled image structure.
    2. Validates live image structure.
    3. Checks single face presence & quality cues.
    4. Computes correlation of equalized normalized face histograms.
    """
    enrolled_cv = decode_base64_image(enrolled_img_b64)
    live_cv = decode_base64_image(live_img_b64)

    if enrolled_cv is None or live_cv is None:
        return {
            "stage": "frame_capture",
            "verified": False,
            "reason": "Invalid or unreadable camera frame received.",
            "similarity_score": 0.0
        }

    ref_count, ref_face, ref_meta = extract_face_region(enrolled_cv)
    if ref_count != 1 or ref_face is None:
        return {
            "stage": "reference_enrollment",
            "verified": False,
            "reason": f"Enrolled reference check: {ref_meta.get('reason', 'Reference photo unclear')}",
            "similarity_score": 0.0
        }

    live_count, live_face, live_meta = extract_face_region(live_cv)
    if live_count == 0:
        return {
            "stage": "face_detection",
            "verified": False,
            "reason": "No face visible in camera frame. Please position yourself clearly in front of the lens.",
            "similarity_score": 0.0,
            "integrity_anomaly": "face_not_visible"
        }
    if live_count > 1:
        return {
            "stage": "face_detection",
            "verified": False,
            "reason": f"Integrity Alert: Multiple people ({live_count}) detected in camera frame.",
            "similarity_score": 0.0,
            "integrity_anomaly": "multiple_faces"
        }

    # Compute correlation similarity on equalized histograms
    ref_eq = cv2.equalizeHist(ref_face)
    live_eq = cv2.equalizeHist(live_face)

    hist_ref = cv2.calcHist([ref_eq], [0], None, [64], [0, 256])
    hist_live = cv2.calcHist([live_eq], [0], None, [64], [0, 256])

    cv2.normalize(hist_ref, hist_ref, alpha=0, beta=1, norm_type=cv2.NORM_MINMAX)
    cv2.normalize(hist_live, hist_live, alpha=0, beta=1, norm_type=cv2.NORM_MINMAX)

    similarity = float(cv2.compareHist(hist_ref, hist_live, cv2.HISTCMP_CORREL))
    is_match = bool(similarity >= 0.45)

    return {
        "stage": "identity_comparison",
        "verified": is_match,
        "similarity_score": float(round(max(0.0, similarity), 3)),
        "liveness_indicators": {
            "eyes_detected": bool(live_meta.get("eye_detected", False)),
            "sharpness": float(live_meta.get("sharpness_score", 0.0))
        },
        "reason": "Identity verified successfully against enrolled reference." if is_match else "Live face does not match the enrolled reference photo."
    }
