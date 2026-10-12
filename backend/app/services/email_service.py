
import json
import logging
import urllib.error
import urllib.request
from typing import Dict, Any, Optional
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
            f"{settings.frontend_origin.rstrip('/')}/interview/"
            f"{session_token.strip()}"
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
        return self._send_email(candidate_email, subject, body, interview_url)

    def send_interview_rescheduled(
        self,
        candidate_email: str,
        candidate_name: str,
        job_title: str,
        new_scheduled_start: datetime,
        session_token: str,
    ) -> Dict[str, Any]:
        interview_url = (
            f"{settings.frontend_origin.rstrip('/')}/interview/"
            f"{session_token.strip()}"
        )
        formatted_time = new_scheduled_start.strftime(
            "%A, %B %d, %Y at %I:%M %p UTC"
        )

        subject = (
            f"Interview Rescheduled: {job_title} "
            "at Adaptive Interview Intelligence"
        )

        body = f"""Dear {candidate_name},

Your interview for {job_title} has been rescheduled to a new time window.

UPDATED SCHEDULED TIME:
{formatted_time}

SECURE INTERVIEW ACCESS LINK:
{interview_url}

IMPORTANT INSTRUCTIONS:
1. Your secure link opens {settings.INTERVIEW_EARLY_ACCESS_MINUTES} minutes before the new scheduled time and expires after {settings.INTERVIEW_WINDOW_MINUTES} minutes.
2. Identity verification is required before the interview begins.
3. Please prepare a working camera, microphone, and stable internet connection.

If you have any questions, please reach out to your recruiter.

Recruitment Committee
Adaptive Interview Intelligence
"""
        return self._send_email(candidate_email, subject, body, interview_url)

    def send_hiring_decision_notification(
        self,
        candidate_email: str,
        candidate_name: str,
        job_title: str,
        decision: str,
        candidate_feedback: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Sends the candidate's hiring outcome.
        Never includes private recruiter notes, facial data, or internal telemetry.
        """
        portal_url = (
            f"{settings.frontend_origin.rstrip('/')}/candidate/dashboard"
        )

        normalized_decision = decision.strip()

        if normalized_decision in ["Selected", "Hired"]:
            subject = (
                f"Update on your application for {job_title} "
                "at Adaptive Interview Intelligence"
            )
            decision_message = f"""Congratulations! We are pleased to inform you that following your interview, you have been selected for the {job_title} position.

Our recruiting team was impressed by your performance and demonstrated competencies. A member of our recruitment committee will be in touch with you shortly regarding the next steps in the offer and onboarding process."""
        elif normalized_decision == "Rejected":
            subject = (
                f"Update on your application for {job_title} "
                "at Adaptive Interview Intelligence"
            )
            decision_message = f"""Thank you for taking the time to interview with us for the {job_title} position.

After careful review and deliberation by our recruitment committee, we have decided to pursue other candidates whose experience more closely matches the current requirements for this specific role.

We truly appreciate the effort you invested in our adaptive interview process and encourage you to apply for future opportunities with us."""
        elif normalized_decision in ["On Hold", "Under Review"]:
            subject = (
                f"Application Status Update: {job_title} "
                "at Adaptive Interview Intelligence"
            )
            decision_message = f"""Thank you for completing your interview for the {job_title} position.

Your interview evaluation is currently under committee review. We are finalizing assessments and will provide a definitive update once our hiring deliberations conclude."""
        else:
            subject = (
                f"Application Status: {job_title} "
                "at Adaptive Interview Intelligence"
            )
            decision_message = (
                f"Your application status for the {job_title} position "
                f"has been updated to: {normalized_decision}."
            )

        feedback_section = ""
        if candidate_feedback and candidate_feedback.strip():
            feedback_section = (
                f"\n\nINTERVIEW FEEDBACK:\n"
                f"{candidate_feedback.strip()}\n"
            )

        body = f"""Dear {candidate_name},

{decision_message}
{feedback_section}
You can log in to your Candidate Portal to view your application history and status:
{portal_url}

Sincerely,

Recruitment Committee
Adaptive Interview Intelligence
"""
        return self._send_email(candidate_email, subject, body, portal_url)

    def _send_email(
        self,
        candidate_email: str,
        subject: str,
        body: str,
        interview_url: str,
    ) -> Dict[str, Any]:
        api_key = settings.BREVO_API_KEY
        from_email = settings.BREVO_FROM_EMAIL

        if not api_key or not api_key.strip():
            logger.error("Brevo is not configured: BREVO_API_KEY is missing.")
            return {
                "status": "configuration_required",
                "accepted_by_provider": False,
                "delivered": False,
                "message": "Email provider is not configured (BREVO_API_KEY missing).",
                "candidate_email": candidate_email,
                "interview_url": interview_url,
            }

        if not from_email or not from_email.strip():
            logger.error("Brevo is not configured: BREVO_FROM_EMAIL is missing.")
            return {
                "status": "configuration_required",
                "accepted_by_provider": False,
                "delivered": False,
                "message": "Configure BREVO_FROM_EMAIL with a verified sender address.",
                "candidate_email": candidate_email,
                "interview_url": interview_url,
            }

        payload = {
            "sender": {
                "name": "Adaptive Interview Intelligence",
                "email": from_email.strip(),
            },
            "to": [{"email": candidate_email}],
            "subject": subject,
            "textContent": body,
        }

        request = urllib.request.Request(
            "https://api.brevo.com/v3/smtp/email",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "api-key": api_key.strip(),
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                response_body = response.read().decode("utf-8")
                result = json.loads(response_body) if response_body else {}

            message_id = result.get("messageId")
            logger.info(
                "Brevo accepted email request for %s; message_id=%s",
                candidate_email,
                message_id,
            )

            return {
                "status": "accepted",
                "accepted_by_provider": True,
                "delivered": False,
                "message": (
                    "Brevo accepted the email request. "
                    "Check Brevo transactional logs to confirm delivery."
                ),
                "candidate_email": candidate_email,
                "interview_url": interview_url,
                "email_id": message_id,
            }

        except urllib.error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            logger.error(
                "Brevo API returned HTTP %s: %s",
                exc.code,
                details,
            )
            return {
                "status": "delivery_failed",
                "accepted_by_provider": False,
                "delivered": False,
                "message": f"Brevo returned HTTP {exc.code}. Check backend logs.",
                "candidate_email": candidate_email,
                "interview_url": interview_url,
            }

        except (urllib.error.URLError, TimeoutError, OSError):
            logger.exception(
                "Could not connect to Brevo while sending to %s",
                candidate_email,
            )
            return {
                "status": "delivery_failed",
                "accepted_by_provider": False,
                "delivered": False,
                "message": "Could not connect to the email provider.",
                "candidate_email": candidate_email,
                "interview_url": interview_url,
            }


email_service = EmailService()
