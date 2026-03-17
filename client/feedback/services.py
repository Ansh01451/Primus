import hashlib
from io import BytesIO
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid
from fastapi import HTTPException, status
from bson import ObjectId
from utils.email_utils import _send_email
from utils.templates import client_feedback_notification_template
import logging
from utils.blob_utils import upload_blob_from_file
from .db import feedback_col, reg_col  # adjust import path if needed
from .models import FeedbackIn, FeedbackDB
from .enums import FeedbackCategory, AttachmentCategory

logger = logging.getLogger(__name__)


async def create_feedback(payload: FeedbackIn, files: list[tuple[str, BytesIO]]) -> Dict[str, Any]:
    # optional: validate client exists (by email)
    print("Files received at service:", files)
    print("Payload:", payload)
    reg = await reg_col.find_one({"client_email": payload.client_email})
    if not reg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Registered client not found")
    
    project_manager_email: str = "shivam.gupta@onmeridian.com"
    
    # generate tracking ids
    tracking_id = str(uuid.uuid4())
    short_tracking_id = tracking_id.split('-')[0]

    # Prepare attachment buckets per category
    attachments_experience: List[Dict[str, str]] = []
    attachments_appreciation: List[Dict[str, str]] = []
    attachments_completion: List[Dict[str, str]] = []

    # Upload each file and collect URLs
    for filename, content_io, attachment_enum in files:
        try:
        # CHANGED: upload path includes attachment category enum value
            blob_name = f"{tracking_id}/{attachment_enum.value}/{filename}"
            url = upload_blob_from_file(blob_name, content_io)
            entry = {"filename": filename, "url": url, "category": attachment_enum.value}


            if attachment_enum == AttachmentCategory.EXPERIENCE_LETTER:
                attachments_experience.append(entry)
            elif attachment_enum == AttachmentCategory.APPRECIATION_LETTER:
                attachments_appreciation.append(entry)
            elif attachment_enum == AttachmentCategory.COMPLETION_CERTIFICATE:
                attachments_completion.append(entry)
            else:
                # Safety: unknown category -> put into completion by default
                attachments_completion.append(entry)
        except Exception as e:
            logger.error(f"Failed to upload {filename}: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="File upload failed")

    doc = FeedbackDB(
        client_email=payload.client_email,
        project_no=payload.project_no,
        project_name=payload.project_name,
        project_manager_email=project_manager_email,
        category=payload.category,
        team_member_id=payload.team_member_id,
        milestone_name=payload.milestone_name,
        communication_quality = payload.communication_quality,
        team_collaboration = payload.team_collaboration,
        solution_quality = payload.solution_quality,
        overall_satisfaction = payload.overall_satisfaction,
        tracking_id=tracking_id,
        comments=payload.comments,
        created_at=datetime.now(),
    ).dict(by_alias=True)
    res = await feedback_col.insert_one(doc)
    doc["_id"] = str(res.inserted_id)

    # For email/template convenience, create a unified attachments list (preserves categories)
    unified_attachments = attachments_experience + attachments_appreciation + attachments_completion
    doc["feedback_attachments"] = unified_attachments # CHANGED: added for backward compatibility with templates
    
    # --- Send email notification to Project Manager (best-effort) ---
    try:
        # get PM contact - change to literal string if you want hardcoded

        html = client_feedback_notification_template(
            feedback_id=short_tracking_id,
            client_email=doc["client_email"],
            project_no=doc["project_no"],
            project_name=doc["project_name"],
            project_manager_email=doc["project_manager_email"],
            category=FeedbackCategory(doc['category']).value.replace('_', ' ').title(),
            team_member_id=doc.get("team_member_id"),
            milestone_name=doc.get("milestone_name"),
            communication_quality = doc.get("communication_quality"),
            team_collaboration = doc.get("team_collaboration"),
            solution_quality = doc.get("solution_quality"),
            overall_satisfaction = doc.get("overall_satisfaction"),
            comments=doc.get("comments"),
            created_at=doc["created_at"],
            attachments=doc["feedback_attachments"]
        )
        subject = f"[Feedback #{short_tracking_id}] {doc['project_no']} — {FeedbackCategory(doc['category']).value.replace('_', ' ').title()}"
        print("Suject:", subject)
        await _send_email(project_manager_email, subject, html)
        doc["success"] = True
    except Exception as e:
        logger.error("Failed to send feedback notification email: %s", e)

    return doc


async def get_feedback_by_id(feedback_id: str) -> Optional[Dict[str, Any]]:
    
    try:
        oid = ObjectId(feedback_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid feedback id")
    doc = await feedback_col.find_one({"_id": oid})
    if not doc:
        return None
    doc["_id"] = str(doc["_id"])
    return doc


async def update_feedback_by_id(feedback_id: str, payload) -> Optional[Dict[str, Any]]:
    """
    Partially update a feedback document. `payload` is a pydantic model (FeedbackIn) instance.
    Returns the updated document (with _id as str) or raises HTTPException on errors.
    """
    try:
        oid = ObjectId(feedback_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid feedback id")

    # Build update dict from fields actually sent by client
    update_data = payload.dict(exclude_unset=True)

    # If you prefer explicit nulls to clear values, remove the next line.
    update_data = {k: v for k, v in update_data.items() if v is not None}

    if not update_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields provided to update")

    # add modified timestamp
    update_data["modified_at"] = datetime.now()

    result = await feedback_col.update_one({"_id": oid}, {"$set": update_data})
    if result.matched_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feedback not found")

    doc = await feedback_col.find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feedback not found after update")

    # normalize id for response
    doc["_id"] = str(doc["_id"])
    return doc


async def list_feedback(skip: int = 0, limit: int = 20,
                        project_no: Optional[str] = None,
                        client_email: Optional[str] = None) -> Dict[str, Any]:
    query = {}
    if project_no:
        query["project_no"] = project_no
    if client_email:
        query["client_email"] = client_email

    cursor = feedback_col.find(query).sort("created_at", -1).skip(skip).limit(limit)
    items = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        items.append(doc)
    total = await feedback_col.count_documents(query)
    return {"total": total, "items": items}


