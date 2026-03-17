from bson import ObjectId
from pydantic import BaseModel, Field, EmailStr, HttpUrl
from typing import Dict, List, Optional
from datetime import datetime
from .db import PyObjectId
from .enums import EscalationType, Urgency, EscalationStatus

class EscalationIn(BaseModel):
    project_id: str
    type: EscalationType
    urgency: Urgency
    subject: str
    description: str
    execution_date: Optional[datetime] = None

class EscalationOut(BaseModel):
    id: PyObjectId = Field(..., alias="_id")
    short_id: str
    short_seq: int                       # <- numeric sequence for ordering
    tracking_id: str
    client_id: str
    client_email: EmailStr
    project_id: str
    project_name: str
    project_manager: str
    project_manager_email: EmailStr
    date_of_escalation: datetime
    type: str
    status: EscalationStatus
    urgency: Urgency
    subject: str
    description: str
    escalation_attachments: Optional[List[Dict[str, str]]] = Field(default=[])

    class Config:
        validate_by_name = True
        json_encoders = { ObjectId: str, datetime: lambda dt: dt.isoformat() }



