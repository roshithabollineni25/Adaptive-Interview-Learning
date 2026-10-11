import json
import logging
import urllib.error
import urllib.request
from typing import Dict, Any
from datetime import datetime

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailService:
    def send_interview_invitation(
        self,
        candidate_email: str,
        candidate_name: str,
        job_title: str,
        scheduled_start: datetime,
        session_token: str,
    ) -> Dict[str, Any]:
        interview_url = (
            f"{settings.FRONTEND_URL}/interview/{session_token}"
        )
        formatted_time = scheduled_start.strftime(
            "%A, %B %d, %Y at %I:%M %p UTC"
        )

        subject = (
            f"Interview Scheduled: {job_title} "
            "at Adaptive Interview Intelligence"
        )

        body = f"""Dear {candidate_name},

Your interview for {job_title} has been confirmed.

SCHEDULED TIME:
{formatted_time}

SECURE INTERVIEW ACCESS LINK:
{interview_url}

IMPORTANT INSTRUCTIONS:
1. Your link opens {settings.INTERVIEW_EARLY_ACCESS_MINUTES} minutes before the scheduled time and expires after {settings.INTERVIEW_WINDOW_MINUTES} minutes.
2. Identity verification is required before the interview.
3. Please prepare a working camera, microphone, and stable internet connection.

We wish you the best for your interview.

Recruitment Committee
Adaptive Interview Intelligence
"""

        api_key = settings.RESEND_API_KEY
        from_email = settings.RESEND_FROM_EMAIL

        if not api_key:
            logger.error("Resend is not configured: RESEND_API_KEY is missing.")
            return {
                "status": "configuration_required",
                "delivered": False,
                "message": "Email provider is not configured.",
                "candidate_email": candidate_email,
                "interview_url": interview_url,
            }

        payload = {
            "from": from_email,
            "to": [candidate_email],
            "subject": subject,
            "text": body,
        }

        request = urllib.request.Request(
            "https://api.resend.com/emails",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "AdaptiveInterviewIntelligence/1.0",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                result = json.loads(response.read().decode("utf-8"))

            email_id = result.get("id")
            logger.info(
                "Resend accepted invitation for %s; email_id=%s",
                candidate_email,
                email_id,
            )

            return {
                "status": "accepted",
                "delivered": True,
                "message": "Email accepted by the email provider.",
                "candidate_email": candidate_email,
                "interview_url": interview_url,
                "email_id": email_id,
            }

        except urllib.error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            logger.error(
                "Resend API returned HTTP %s: %s",
                exc.code,
                details,
            )
            return {
                "status": "delivery_failed",
                "delivered": False,
                "message": f"Email provider returned HTTP {exc.code}.",
                "candidate_email": candidate_email,
                "interview_url": interview_url,
            }

        except Exception:
            logger.exception(
                "Could not send invitation to %s",
                candidate_email,
            )
            return {
                "status": "delivery_failed",
                "delivered": False,
                "message": "Could not connect to the email provider.",
                "candidate_email": candidate_email,
                "interview_url": interview_url,
            }


email_service = EmailService()
