import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, Optional
from datetime import datetime
from app.core.config import settings

logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self):
        self.server = settings.SMTP_SERVER
        self.port = settings.SMTP_PORT
        self.username = settings.SMTP_USERNAME
        self.password = settings.SMTP_PASSWORD
        self.from_email = settings.SMTP_FROM_EMAIL
        self.enabled = settings.SMTP_ENABLED

    def send_interview_invitation(
        self,
        candidate_email: str,
        candidate_name: str,
        job_title: str,
        scheduled_start: datetime,
        session_token: str
    ) -> Dict[str, Any]:
        """
        Sends confirmed interview schedule and secure access link.
        Returns status dict with delivery state and diagnostics.
        """
        interview_url = f"{settings.FRONTEND_URL}/interview/{session_token}"
        formatted_time = scheduled_start.strftime("%A, %B %d, %Y at %I:%M %p UTC")

        subject = f"Interview Scheduled: {job_title} at Adaptive Interview Intelligence"
        body = f"""Dear {candidate_name},

Your technical interview for the position of {job_title} has been confirmed.

SCHEDULED TIME:
{formatted_time}

SECURE INTERVIEW ACCESS LINK:
{interview_url}

IMPORTANT INSTRUCTIONS:
1. Access Window: Your interview link becomes usable {settings.INTERVIEW_EARLY_ACCESS_MINUTES} minutes before the scheduled time and expires after {settings.INTERVIEW_WINDOW_MINUTES} minutes.
2. Identity Verification: Before starting, you will undergo a mandatory webcam biometric identity verification and consent process.
3. System Requirements: Please ensure you have a working camera, microphone, and stable internet connection in a quiet environment.

We wish you the best for your interview.

Sincerely,
Recruitment Committee
Adaptive Interview Intelligence
"""

        if not self.enabled or not self.username or not self.password or self.username == "your_email@gmail.com":
            logger.warning(
                f"SMTP not fully configured. Email invitation prepared for {candidate_email}: {interview_url}"
            )
            return {
                "status": "configuration_required",
                "delivered": False,
                "message": "SMTP credentials not configured in .env. Invitation record and link generated successfully in database.",
                "candidate_email": candidate_email,
                "interview_url": interview_url,
                "scheduled_time": formatted_time
            }

        try:
            msg = MIMEMultipart()
            msg["From"] = self.from_email
            msg["To"] = candidate_email
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain"))

            server = smtplib.SMTP(self.server, self.port, timeout=10)
            server.starttls()
            server.login(self.username, self.password)
            server.send_message(msg)
            server.quit()
            logger.info(f"Interview invitation email sent to {candidate_email}")
            return {
                "status": "delivered",
                "delivered": True,
                "message": f"Invitation successfully delivered to {candidate_email}",
                "candidate_email": candidate_email,
                "interview_url": interview_url
            }
        except Exception as e:
            logger.error(f"Failed to send email to {candidate_email}: {e}")
            return {
                "status": "delivery_failed",
                "delivered": False,
                "message": f"SMTP delivery failed: {str(e)}",
                "candidate_email": candidate_email,
                "interview_url": interview_url
            }

email_service = EmailService()
