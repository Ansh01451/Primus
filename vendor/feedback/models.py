from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, Field, EmailStr
from bson import ObjectId
from .db import PyObjectId



class FeedbackIn(BaseModel):
    vendor_email: EmailStr
    category: str          
    communication_quality: Optional[int] = Field(None, ge=1, le=5)
    team_collaboration: Optional[int] = Field(None, ge=1, le=5)
    overall_satisfaction: Optional[int] = Field(None, ge=1, le=5)
    comments: Optional[str] = None

class FeedbackDB(BaseModel):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    vendor_email: EmailStr
    tracking_id: str
    category: str
    communication_quality: Optional[int] = None
    team_collaboration: Optional[int] = None
    overall_satisfaction: Optional[int] = None
    comments: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now())
    feedback_attachments: Optional[List[Dict[str, str]]] = Field(default=[])

    class Config:
        json_encoders = { ObjectId: str, datetime: lambda dt: dt.isoformat() }
        validate_by_name = True

