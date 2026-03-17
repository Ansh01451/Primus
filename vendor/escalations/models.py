from bson import ObjectId
from pydantic import BaseModel, Field, EmailStr, HttpUrl
from typing import Dict, List, Optional
from datetime import datetime
from .db import PyObjectId
from .enums import EscalationType, Urgency, EscalationStatus

class EscalationIn(BaseModel):
    type: EscalationType
    urgency: Urgency
    subject: str
    description: str
    execution_date: Optional[datetime] = None

class EscalationOut(BaseModel):
    id: PyObjectId = Field(..., alias="_id")
    short_id: str                              # NEW: human-friendly serial like RE000001
    short_seq: int                             # NEW: numeric sequence (useful for sorting)
    tracking_id: str
    vendor_id: str
    vendor_email: EmailStr
    vendor_name: Optional[str] = None          # NEW: vendor name was present in the doc
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









