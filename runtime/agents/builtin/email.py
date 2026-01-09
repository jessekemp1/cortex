"""Email Agent - Email notification and delivery.

Provides email sending capabilities for notifications,
reports, and briefings.
"""

import os
from typing import Any, Dict, Optional

import structlog

from cortex.runtime.agents.base import AgentMetadata, BaseAgent
from cortex.runtime.models import AgentResult

logger = structlog.get_logger()


class EmailAgent(BaseAgent):
    """Email notification agent.

    Sends emails for notifications, reports, and briefing delivery.
    Supports Gmail OAuth integration.
    """

    def __init__(
        self,
        agent_id: str = "email_agent",
        email_address: Optional[str] = None,
    ):
        super().__init__(
            agent_id=agent_id,
            name="Email Notification Agent",
            description="Sends email notifications and reports",
            metadata=AgentMetadata(
                version="1.0",
                tags=["notification", "email"],
            ),
        )
        self.email_address = email_address or os.getenv("EMAIL_ADDRESS")

    def execute(self, context: Dict[str, Any]) -> AgentResult:
        """Send an email.

        Args:
            context: Execution context with:
                - to: Recipient email(s)
                - subject: Email subject
                - body: Email body (plain text or HTML)
                - html: If True, body is HTML

        Returns:
            AgentResult with send status
        """
        recipient = context.get("to", self.email_address)
        subject = context.get("subject", "Cortex Notification")
        body = context.get("body", "")
        is_html = context.get("html", False)

        if not recipient:
            return AgentResult(
                success=False,
                message="No recipient email address specified",
            )

        if not body:
            return AgentResult(
                success=False,
                message="No email body provided",
            )

        try:
            # Try to import and use Gmail API
            return self._send_via_gmail(recipient, subject, body, is_html)
        except ImportError:
            logger.warning("gmail_api_not_available")
            return AgentResult(
                success=False,
                message="Gmail API not available. Install google-api-python-client.",
                data={"recipient": recipient, "subject": subject},
            )
        except Exception as e:
            logger.error("email_send_failed", error=str(e))
            return AgentResult(
                success=False,
                message=f"Failed to send email: {str(e)}",
                data={"error": str(e)},
            )

    def _send_via_gmail(
        self, recipient: str, subject: str, body: str, is_html: bool
    ) -> AgentResult:
        """Send email via Gmail API.

        Requires OAuth credentials to be configured.
        """
        import base64
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        from pathlib import Path

        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build

        SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

        # Load or refresh credentials
        creds = None
        token_path = Path.home() / ".cortex" / "gmail_token.json"
        creds_path = Path.home() / ".cortex" / "credentials.json"

        if token_path.exists():
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            elif creds_path.exists():
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(creds_path), SCOPES
                )
                creds = flow.run_local_server(port=0)
            else:
                return AgentResult(
                    success=False,
                    message="Gmail credentials not configured",
                )

            # Save credentials
            token_path.parent.mkdir(parents=True, exist_ok=True)
            with open(token_path, "w") as token:
                token.write(creds.to_json())

        # Build message
        message = MIMEMultipart()
        message["to"] = recipient
        message["subject"] = subject

        mime_type = "html" if is_html else "plain"
        message.attach(MIMEText(body, mime_type))

        # Encode and send
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

        service = build("gmail", "v1", credentials=creds)
        service.users().messages().send(userId="me", body={"raw": raw}).execute()

        logger.info("email_sent", recipient=recipient, subject=subject)

        return AgentResult(
            success=True,
            message=f"Email sent to {recipient}",
            data={"recipient": recipient, "subject": subject},
        )
