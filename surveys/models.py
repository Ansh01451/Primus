from pydantic import BaseModel, Field
from typing import List, Optional, Any
from datetime import datetime
from admin.db import PyObjectId

class SurveyQuestion(BaseModel):
    text: str
    type: str = "rating"

class CreateSurveyRequest(BaseModel):
    title: str
    category: str
    deadline: datetime
    target_roles: List[str] = []
    user_ids: List[str] = []
    questions: List[SurveyQuestion]  # Mixed types of questions
    is_published: bool = True
    form_link: Optional[str] = None

class Survey(BaseModel):
    id: PyObjectId = Field(..., alias="_id")
    title: str
    category: str
    deadline: datetime
    target_roles: List[str]
    user_ids: List[str]
    questions: List[dict]
    is_published: bool
    created_at: datetime
    form_link: Optional[str] = None

    class Config:
        populate_by_name = True
        json_encoders = {datetime: lambda dt: dt.isoformat()}

class SurveyResponsePayload(BaseModel):
    responses: List[Any]  # Mixed responses (int for rating, str for text)

class SurveyResponse(BaseModel):
    id: PyObjectId = Field(..., alias="_id")
    survey_id: str
    user_id: str
    user_email: str
    user_name: str
    responses: List[Any]
    submitted_at: datetime

    class Config:
        populate_by_name = True
        json_encoders = {datetime: lambda dt: dt.isoformat()}
