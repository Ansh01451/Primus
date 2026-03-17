from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, Field, EmailStr
from bson import ObjectId
from .db import PyObjectId



class FeedbackIn(BaseModel):
    client_email: EmailStr
    project_no: str
    project_name: str
    category: str            # use FeedbackCategory.value from frontend or backend
    team_member_id: Optional[str] = None
    milestone_name: Optional[str] = None
    communication_quality: Optional[int] = Field(None, ge=0, le=5)
    team_collaboration: Optional[int] = Field(None, ge=0, le=5)
    solution_quality: Optional[int] = Field(None, ge=0, le=5)
    overall_satisfaction: Optional[int] = Field(None, ge=0, le=5)
    comments: Optional[str] = None
    

class FeedbackDB(BaseModel):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    client_email: EmailStr
    tracking_id: str
    project_no: str
    project_name: str
    project_manager_email: str
    category: str
    team_member_id: Optional[str] = None
    milestone_name: Optional[str] = None
    communication_quality: Optional[int] = None
    team_collaboration: Optional[int] = None
    solution_quality: Optional[int] = None
    overall_satisfaction: Optional[int] = None
    comments: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    feedback_attachments_experience_letter: Optional[List[Dict[str, str]]] = Field(default_factory=list)
    feedback_attachments_appreciation_letter: Optional[List[Dict[str, str]]] = Field(default_factory=list)
    feedback_attachments_completion_certificate: Optional[List[Dict[str, str]]] = Field(default_factory=list)

    class Config:
        json_encoders = { ObjectId: str, datetime: lambda dt: dt.isoformat() }
        validate_by_name = True



class FeedbackUpdate(BaseModel):
    # All fields optional for PATCH semantics
    client_email: Optional[EmailStr] = None
    project_no: Optional[str] = None
    project_name: Optional[str] = None
    category: Optional[str] = None
    team_member_id: Optional[str] = None
    communication_quality: Optional[int] = Field(None, ge=0, le=5)
    team_collaboration: Optional[int] = Field(None, ge=0, le=5)
    solution_quality: Optional[int] = Field(None, ge=0, le=5)
    overall_satisfaction: Optional[int] = Field(None, ge=0, le=5)
    comments: Optional[str] = None

