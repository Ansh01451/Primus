from datetime import datetime
import logging
from azure.communication.email import EmailClient
from fastapi import HTTPException, status
from config import settings
from .log import logger


COMMUNICATION_CONNECTION_STRING = settings.mail_cnn_string
email_client = EmailClient.from_connection_string(COMMUNICATION_CONNECTION_STRING)


# placeholder email sender
async def _send_email(to_address: str, subject: str, html_body: str) -> None:
    try:
        await send_mail_to_user(
            sender="DoNotReply@onmeridian.com",
            to=[{"address": to_address}],
            subject=subject,
            html=html_body
        )
        logger.info(f"Sent email to {to_address} with subject '{subject}'")
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to send email")
    

async def send_mail_to_user(
    sender: str,
    to: list[dict[str, str]],
    subject: str,
    plain_text: str = "",
    html: str = "",
) -> None:
    """
    sender: sender email address string
    to: list of {"address": "user@example.com", "display_name": "User Name"}
    """
    message = {
        "senderAddress": sender,
        "content": {
            "subject": subject,
            "plainText": plain_text,
            "html": html,
        },
        "recipients": {
            "to": to
        },
    }
    try:
        poller = email_client.begin_send(message)
        result = poller.result()
        # print(f"Email sent with status: {result}")
        if result.get("status", "").lower() != "succeeded":
            raise RuntimeError(f"Email send failed with status {result.get('status')}")
    except Exception as e:
        # Log or re‑raise as HTTPException
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send email: {e}"
        ) from e


