from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime

class ClientProfileResponse(BaseModel):
    client_id: str
    client_email: EmailStr
    client_name: str
    roles: List[str]
    created_at: datetime
    project_id: List[str]
    address: str
    alternate_email: Optional[EmailStr] = None
    city: str
    phone: str
    state: str
    zip_code: str
    company_name: str
    country: str
    designation: str
    first_name: str
    gst_no: str
    last_name: str
    middle_name: str

class ClientProfileUpdate(BaseModel):
    address: Optional[str] = None
    alternate_email: Optional[EmailStr] = None
    city: Optional[str] = None
    phone: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    company_name: Optional[str] = None
    country: Optional[str] = None
    designation: Optional[str] = None
    first_name: Optional[str] = None
    gst_no: Optional[str] = None
    last_name: Optional[str] = None
    middle_name: Optional[str] = None
