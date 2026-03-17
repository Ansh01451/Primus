from io import BytesIO
import uuid
from datetime import datetime
import asyncio
from fastapi import HTTPException, status, Depends
from typing import Dict, List
from utils.log import logger
from ..dashboard.services import get_access_token
from .db import escalations_col, registered_vendor_col
from .models import EscalationIn, EscalationOut
from .enums import EscalationStatus
from auth.middleware import get_current_user
from utils.email_utils import send_mail_to_user
from utils.templates import vendor_escalation_notification_template
from utils.email_utils import _send_email
from utils.blob_utils import upload_blob_from_file
from auth.db import email_field_map
from pymongo.errors import DuplicateKeyError



class EscalationService:

    @staticmethod
    async def create_escalation(data: EscalationIn, files: list[tuple[str, BytesIO]], user : dict) -> EscalationOut:
        try:
            
            # get a token once, reuse for both project and team members
            token = await get_access_token()
            
            # Fetch vendor record
            vendor_email = user.get("email")  # NEW: fetched from request state
            if not vendor_email:
                logger.error(f"Missing vendor_email in user context for vendor_email={vendor_email}")
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Vendor email missing")
            
            vendor = registered_vendor_col.find_one({"vendor_email": vendor_email})
            if not vendor:
                logger.error(f"Vendor not found, vendor_email={vendor_email}")
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vendor not found")

            # Generate tracking ID and timestamp
            tracking_id = str(uuid.uuid4())
            now = datetime.now()

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

            project_manager_email = "shivam.gupta@onmeridian.com"  # hardcoded as requested

            max_retries = 5
            attempt = 0
            inserted = None
            while attempt < max_retries and not inserted:
                attempt += 1
                try:
                    # CHANGED: run count_documents in threadpool to avoid blocking
                    seq = int(escalations_col.count_documents({"vendor_email": vendor_email})) + 1
                    short_id = f"RE{seq:06d}"   # e.g., RE000001

                    doc = {
                        "tracking_id": tracking_id,
                        "short_id": short_id,            # NEW
                        "short_seq": seq, 
                        "vendor_id": vendor.get("vendor_id"),
                        "vendor_name": vendor.get("vendor_name"),
                        "vendor_email": vendor_email,
                        "date_of_escalation": now,
                        "execution_date": None,
                        "type": data.type.value,
                        "status": EscalationStatus.OPEN.value,
                        "urgency": data.urgency.value,
                        "subject": data.subject.strip(),
                        "description": data.description.strip(),
                        "escalation_attachments": attachments
                    }

                    # CHANGED: insert in threadpool
                    res = escalations_col.insert_one(doc)
                    doc["_id"] = str(res.inserted_id)
                    inserted = doc  # success -> break loop

                except DuplicateKeyError:
                    # someone inserted same short_id concurrently; recompute and retry
                    logger.warning("Duplicate short_id detected on attempt %s for vendor %s — retrying", attempt, vendor_email)
                    await asyncio.sleep(0.05 * attempt)
                    continue
                except Exception as e:
                    logger.exception("Error inserting escalation")
                    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create escalation")

            if not inserted:
                logger.error("Failed to allocate unique short_id after retries")
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to allocate escalation ID")


            # Email PM
            try:
                html = vendor_escalation_notification_template(
                    tracking_id=doc["short_id"],
                    vendor_id=doc["vendor_id"],
                    vendor_name=vendor.get("vendor_name"),  
                    vendor_email=doc["vendor_email"],
                    escalation_type=doc["type"],
                    urgency=doc["urgency"], 
                    subject=doc["subject"],
                    description=doc["description"],
                    date_of_escalation=doc["date_of_escalation"],
                    attachments=doc["escalation_attachments"]
                )

                subject = f"[Request {doc["short_id"]}] {doc["subject"]}"
                # print("dsfgbdfnhgfdsfvb nbgfd")
                await _send_email(project_manager_email, subject, html)

            except Exception as e:
                logger.error(f"Failed to send escalation email: {e}")  # NEW logging

            return EscalationOut(**doc)
        
        except HTTPException:
            raise
        except Exception as e:
            logger.exception("Unexpected error creating escalation")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create escalation")

    
    @staticmethod
    async def list_escalations_for_vendor(
        user: dict, 
        BACKEND_TO_FRONTEND_TYPE: dict[str, str]
    ) -> List[EscalationOut]:
        try:
            vendor_email = user.get("email")
            if not vendor_email:
                raise HTTPException(status_code=400, detail="Vendor email missing in token")

            # Filter by vendor_email + project_no
            query = {"vendor_email": vendor_email}

            escalations = list(escalations_col.find(query))
            for esc in escalations:
                esc["_id"] = str(esc["_id"])  # Convert ObjectId to string

                # ✅ Convert enum back to frontend label if exists
                if "type" in esc and esc["type"] in BACKEND_TO_FRONTEND_TYPE:
                    esc["type"] = BACKEND_TO_FRONTEND_TYPE[esc["type"]]

            return [EscalationOut(**e) for e in escalations]

        except Exception as e:
            logger.exception("Failed to fetch vendor escalations")
            raise HTTPException(status_code=500, detail="Failed to fetch escalations")




        