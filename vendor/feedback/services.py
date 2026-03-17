from io import BytesIO
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid
from fastapi import HTTPException, status
from bson import ObjectId
from utils.email_utils import _send_email
from utils.templates import vendor_feedback_notification_template
from utils.blob_utils import upload_blob_from_file
import logging

from .enums import FeedbackCategory
from .db import feedback_col, registered_vendor_col  # adjust import path if needed
from .models import FeedbackIn, FeedbackDB


logger = logging.getLogger(__name__)


async def create_feedback(payload: FeedbackIn, files: list[tuple[str, BytesIO]]) -> Dict[str, Any]:
    # optional: validate vendor exists (by email)
    print("Files received at service:", files)
    print("Payload:", payload)
    reg = await registered_vendor_col.find_one({"vendor_email": payload.vendor_email})
    if not reg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Registered vendor not found")
    
    project_manager_email: str = "shivam.gupta@onmeridian.com"
    
    # generate tracking ids
    tracking_id = str(uuid.uuid4())
    short_tracking_id = tracking_id.split('-')[0]

    # Upload each file and collect URLs
    attachments: List[Dict[str, str]] = []
    for filename, content in files:
        try:
            blob_name = f"{tracking_id}/{filename}"
            url = upload_blob_from_file(blob_name, content)
            attachments.append({"filename": filename, "url": url})
        except Exception as e:
            logger.error(f"Failed to upload {filename}: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="File upload failed")


    doc = FeedbackDB(
        vendor_email=payload.vendor_email,
        category=payload.category,
        communication_quality = payload.communication_quality,
        team_collaboration = payload.team_collaboration,
        overall_satisfaction = payload.overall_satisfaction,
        tracking_id=tracking_id,
        comments=payload.comments,
        created_at=datetime.now(),
        feedback_attachments=attachments
    ).dict(by_alias=True)
    res = await feedback_col.insert_one(doc)
    doc["_id"] = str(res.inserted_id)
    
    # --- Send email notification to Project Manager (best-effort) ---
    try:
        # get PM contact - change to literal string if you want hardcoded

        html = vendor_feedback_notification_template(
            feedback_id=short_tracking_id,
            vendor_email=doc["vendor_email"],
            category=FeedbackCategory(doc['category']).value.replace('_', ' ').title(),
            team_member_id=doc.get("team_member_id"),
            communication_quality = doc.get("communication_quality"),
            team_collaboration = doc.get("team_collaboration"),
            overall_satisfaction = doc.get("overall_satisfaction"),
            comments=doc.get("comments"),
            created_at=doc["created_at"],
            attachments=doc["feedback_attachments"]
        )
        subject = f"[Feedback #{short_tracking_id}] — {FeedbackCategory(doc['category']).value.replace('_', ' ').title()}"
        print("Suject:", subject)
        await _send_email(project_manager_email, subject, html)
        doc["success"] = True
    except Exception as e:
        logger.error("Failed to send feedback notification email: %s", e)

    return doc

