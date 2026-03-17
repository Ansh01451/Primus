# projects/models.py
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, EmailStr
from .db import PyObjectId

class ProjectSummary(BaseModel):
    project_id: str  # maps to project document 'no'
    project_name: str  # maps to project document 'description'

class PhaseOut(BaseModel):
    name: str
    status: str
    date: Optional[datetime] = None

class TaskOut(BaseModel):
    name: str
    priority: Optional[str] = None
    description: Optional[str] = None
    progress_percent: Optional[int] = None

class ProjectDetailsOut(BaseModel):
    id: PyObjectId = Field(..., alias="_id")
    project_id: str
    project_name: str
    assigned_to: Optional[str]
    assigned_to_email: Optional[EmailStr]
    start_date: Optional[str]  # keep string to match your project doc format
    status: Optional[str]
    team_members: List[Dict[str, str]] = []  # list of { memberID, memberName }
    phases: List[PhaseOut] = []
    tasks: List[TaskOut] = []
    extra: Dict[str, Any] = {}  # any extra fields you want to pass through

class DashboardOverview(BaseModel):
    projects: List[ProjectSummary]
    total_projects: int
    ongoing_projects: int
