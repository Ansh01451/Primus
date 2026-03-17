from bson import ObjectId
from pydantic import BaseModel, EmailStr, Field
from typing import List, Literal, Optional
from datetime import datetime
from admin.db import PyObjectId


class UnregisteredClient(BaseModel):
    id: PyObjectId = Field(..., alias="_id")
    client_id: str
    client_email: EmailStr
    client_name: str
    added_at: datetime
    project_id: str

    class Config:
        json_encoders = { ObjectId: str, datetime: lambda dt: dt.isoformat() }
        validate_by_name = True


class RegisteredClient(BaseModel):
    id: PyObjectId = Field(..., alias="_id")
    client_id: str
    client_email: EmailStr
    client_name: str
    password_hash: str             # generated for them
    roles: list[str]               # e.g. ["user"]
    created_at: datetime
    project_id: list[str]

    class Config:
        json_encoders = { ObjectId: str, datetime: lambda dt: dt.isoformat() }
        validate_by_name = True


# ── Onboarding ──────────────────────────────────────────────────────────────

PortalRole = Literal["vendor", "client", "alumni", "advisor"]


class OnboardUserRequest(BaseModel):
    """Payload the admin submits to onboard a new user."""
    name: str
    email: EmailStr
    phone: str
    role: PortalRole
    dynamics_id: str          # ID used to fetch extra data from Dynamics


class OnboardedUser(BaseModel):
    id: PyObjectId = Field(..., alias="_id")
    name: str
    email: EmailStr
    phone: str
    role: str
    dynamics_id: str
    password_hash: str
    created_at: datetime
    onboarded_by: Optional[str] = None   # admin user_id

    class Config:
        json_encoders = {ObjectId: str, datetime: lambda dt: dt.isoformat()}
        validate_by_name = True


# ── Profile Update ───────────────────────────────────────────────────────────

class UpdateAddressRequest(BaseModel):
    line1:   Optional[str] = None
    line2:   Optional[str] = None
    city:    Optional[str] = None
    state:   Optional[str] = None
    pincode: Optional[str] = None
    country: Optional[str] = None


class UpdateBankInfoRequest(BaseModel):
    bank_name:      Optional[str] = None
    account_number: Optional[str] = None
    ifsc_code:      Optional[str] = None
    account_holder: Optional[str] = None
    account_type:   Optional[str] = None


class UpdateGstRequest(BaseModel):
    gstin:      Optional[str] = None
    pan:        Optional[str] = None
    trade_name: Optional[str] = None
    gst_status: Optional[str] = None


class UpdateUserProfileRequest(BaseModel):
    name:      Optional[str]                  = None
    email:     Optional[EmailStr]             = None
    phone:     Optional[str]                  = None
    address:   Optional[UpdateAddressRequest] = None
    bank_info: Optional[UpdateBankInfoRequest] = None
    gst:       Optional[UpdateGstRequest]      = None


# ── Content Management ────────────────────────────────────────────────────────

ContentType       = Literal["announcement", "news", "document"]
VisibilityTarget  = Literal["vendor", "client", "alumni", "advisor", "all"]


class CreateContentRequest(BaseModel):
    title:       str
    body:        str
    content_type: ContentType    = "announcement"
    visibility:  List[VisibilityTarget] = ["all"]   # which roles can see it
    is_published: bool = True
    scheduled_at: Optional[datetime] = None         # future publish time (UTC)
    attachment_url: Optional[str] = None


class UpdateContentRequest(BaseModel):
    title:        Optional[str]                     = None
    body:         Optional[str]                     = None
    content_type: Optional[ContentType]             = None
    visibility:   Optional[List[VisibilityTarget]]  = None
    is_published: Optional[bool]                    = None
    scheduled_at: Optional[datetime]                = None
    attachment_url: Optional[str]                   = None


# ── Notification Manager ──────────────────────────────────────────────────────

AlertChannel = Literal["in_app", "email", "both"]


class CreateAlertRequest(BaseModel):
    title:        str
    message:      str
    target_roles: List[VisibilityTarget]  = []      # role-based group targeting
    user_ids:     List[str]               = []      # specific individual user IDs
    channel:      AlertChannel            = "both"  # delivery method

    # At least one target must be supplied
    from pydantic import model_validator
    @model_validator(mode="after")
    def check_at_least_one_target(self):
        if not self.target_roles and not self.user_ids:
            raise ValueError("Provide at least one target_role or one user_id")
        return self


class UpdateEscalationStatusRequest(BaseModel):
    status: str

