from io import BytesIO
import uuid
from datetime import datetime
import asyncio
from fastapi import HTTPException, status, Depends
from typing import Dict, List
from utils.log import logger
from ..dashboard.services import get_access_token, get_project_by_no
from .db import escalations_col, registered_clients_col
from .models import EscalationIn, EscalationOut
from .enums import EscalationStatus
from auth.middleware import get_current_user
from utils.email_utils import send_mail_to_user
from utils.templates import client_escalation_notification_template
from utils.email_utils import _send_email
from utils.blob_utils import upload_blob_from_file
from auth.db import email_field_map
from pymongo.errors import DuplicateKeyError


class EscalationService:

    @staticmethod
    async def create_escalation(data: EscalationIn, files: list[tuple[str, BytesIO]], user : dict) -> EscalationOut:
        try:

            # print("Data in service:", data)
            
            # get a token once, reuse for both project and team members
            token = await get_access_token()

            # fetch single project by no
            proj = await get_project_by_no(data.project_id, token)
            if not proj:
                logger.warning("Project not found in Dynamics: %s", data.project_id)
                raise HTTPException(status_code=404, detail="Project not found")
            
            # Fetch client record
            client_email = user.get("email")  # NEW: fetched from request state
            if not client_email:
                logger.error(f"Missing client_email in user context for client_email={client_email}")
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Client email missing")
            
            client = registered_clients_col.find_one({"project_id": data.project_id, "client_email": client_email})
            if not client:
                logger.error(f"Client not found for project_id={data.project_id} and client_email={client_email}")
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")

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

            project_no = proj.get("no")
            project_name = proj.get("description")
            client_id = proj.get("billToCustomerNo")
            project_manager = proj.get("projectManagerPrimus") or ""
            project_manager_email = "shivam.gupta@onmeridian.com"  # hardcoded as requested

            max_retries = 5
            attempt = 0
            inserted = None
            while attempt < max_retries and not inserted:
                attempt += 1
                try:
                    # count existing escalations for this user and use length+1
                    seq = int(escalations_col.count_documents({"client_email": client_email})) + 1
                    short_id = f"RE{seq:06d}"   # e.g., RE000001

                    doc = {
                        "tracking_id": tracking_id,
                        "short_id": short_id,      # human-friendly serial
                        "short_seq": seq,         # numeric sequence
                        "client_id": client_id,
                        "client_name": client.get("client_name"),
                        "client_email": client_email,
                        "project_id": project_no,
                        "project_name": project_name,
                        "project_manager": project_manager,
                        "project_manager_email": project_manager_email,
                        "date_of_escalation": now,
                        "execution_date": None,
                        "type": data.type.value,
                        "status": EscalationStatus.OPEN.value,
                        "urgency": data.urgency.value,
                        "subject": data.subject.strip(),
                        "description": data.description.strip(),
                        "escalation_attachments": attachments
                    }

                    res = escalations_col.insert_one(doc)
                    doc["_id"] = str(res.inserted_id)
                    inserted = doc  # stop retry loop

                except DuplicateKeyError:
                    # someone inserted the same short_id concurrently; retry to recompute seq
                    logger.warning("Duplicate short_id detected on attempt %s for client %s — retrying", attempt, client_email)
                    # tiny backoff to reduce contention
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
                html = client_escalation_notification_template(
                    tracking_id=doc["short_id"],
                    client_id=doc["client_id"],
                    client_name=client.get("client_name"),  
                    client_email=doc["client_email"],
                    project_id=doc["project_id"],
                    project_manager=doc["project_manager"],
                    project_manager_email=doc["project_manager_email"],
                    project_name=doc["project_name"],
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
    async def list_escalations_for_client(
        user: dict, 
        project_no: str,
        BACKEND_TO_FRONTEND_TYPE: dict[str, str]
    ) -> List[EscalationOut]:
        try:
            client_email = user.get("email")
            if not client_email:
                raise HTTPException(status_code=400, detail="Client email missing in token")

            # Filter by client_email + project_no
            query = {"client_email": client_email}
            if project_no:
                query["project_id"] = project_no

            escalations = list(escalations_col.find(query))
            for esc in escalations:
                esc["_id"] = str(esc["_id"])  # Convert ObjectId to string
                esc["short_id"] = esc.get("short_id", "")
                esc["short_seq"] = esc.get("short_seq", 0)

                # Convert enum back to frontend label if exists
                if "type" in esc and esc["type"] in BACKEND_TO_FRONTEND_TYPE:
                    esc["type"] = BACKEND_TO_FRONTEND_TYPE[esc["type"]]

            return [EscalationOut(**e) for e in escalations]

        except Exception as e:
            logger.exception("Failed to fetch client escalations")
            raise HTTPException(status_code=500, detail="Failed to fetch escalations")

    @staticmethod
    async def reopen_escalation(tracking_id: str, user: dict) -> EscalationOut:
        try:
            client_email = user.get("email")
            if not client_email:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, 
                    detail="Client email missing in token"
                )

            esc = escalations_col.find_one({"tracking_id": tracking_id})
            if not esc:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, 
                    detail="Escalation not found"
                )

            # Ensure only the escalation’s client can reopen it
            if esc["client_email"] != client_email:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, 
                    detail="Not authorized to reopen this escalation"
                )

            # Update status back to OPEN + update timestamp
            escalations_col.update_one(
                {"tracking_id": tracking_id},
                {"$set": {
                    "status": EscalationStatus.OPEN.value,
                    "date_of_escalation": datetime.now()
                }}
            )

            esc["status"] = EscalationStatus.OPEN.value
            esc["_id"] = str(esc["_id"])  # convert ObjectId to string

            return EscalationOut(**esc)

        except HTTPException:
            raise
        except Exception as e:
            logger.exception("Failed to reopen escalation")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
                detail="Failed to reopen escalation"
            )



        