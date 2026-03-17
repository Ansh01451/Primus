from datetime import datetime
from io import BytesIO
from typing import Optional
import uuid
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from auth.middleware import get_current_user, require_roles
from auth.roles import Role
from admin.models import OnboardUserRequest, UpdateUserProfileRequest, CreateContentRequest, UpdateContentRequest, CreateAlertRequest, UpdateEscalationStatusRequest
from admin.services import AdminService, ContentService, AlertService, SupportService

from utils.blob_utils import upload_blob_from_file

router = APIRouter(prefix="/admin", tags=["Admin"],
                   dependencies=[Depends(require_roles(Role.ADMIN))])


@router.post(
    "/fetch-unregistered-clients",
    status_code=status.HTTP_201_CREATED,
    summary="Fetch & save unregistered clients from Dynamics",
    dependencies=[Depends(require_roles(Role.ADMIN))]
)
async def fetch_unregistered(since: Optional[str] = Query(None, description="ISO datetime")):
    dt = datetime.fromisoformat(since) if since else None
    raw = await AdminService.fetch_dynamics_clients(dt)
    count = AdminService.save_unregistered(raw)
    return {"inserted": count}

@router.get(
    "/list-unregistered-clients",
    summary="List unregistered clients",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_roles(Role.ADMIN))]
)
def get_unregistered(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    client_id: Optional[str] = Query(None),
    client_email: Optional[str] = Query(None),
):
    skip = (page - 1) * size
    data = AdminService.list_unregistered(skip, size, client_id, client_email)
    return data


@router.post(
    "/{client_id}/register",
    status_code=status.HTTP_201_CREATED,
    summary="Register one unregistered client",
    dependencies=[Depends(require_roles(Role.ADMIN))]
)
async def verify_and_register(client_id: str):
    reg = await AdminService.register_client(client_id)
    return {"message": "Registered", "client": reg}


@router.get(
    "/list-registered-clients",
    summary="List registered clients",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_roles(Role.ADMIN))]
)
def get_registered_clients(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    client_id: Optional[str] = Query(None),
    client_email: Optional[str] = Query(None),
):
    skip = (page - 1) * size
    data = AdminService.list_registered(skip, size, client_id, client_email)
    return data


# ── Onboarding endpoints ──────────────────────────────────────────────────────

@router.post(
    "/onboard-user",
    status_code=status.HTTP_201_CREATED,
    summary="Onboard a new user (vendor / client / alumni / advisor)",
)
async def onboard_user(
    payload: OnboardUserRequest,
    request: Request,
    user=Depends(get_current_user),
):
    admin_id = getattr(request.state, "user_id", None)
    result = await AdminService.onboard_user(payload, admin_id=admin_id)
    return {"message": "User onboarded successfully", "user": result}


@router.get(
    "/onboarded-users",
    summary="List all onboarded users",
    status_code=status.HTTP_200_OK,
)
def list_onboarded_users(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    role: Optional[str] = Query(None, description="Filter by role: vendor | client | alumni | advisor"),
    search: Optional[str] = Query(None, description="Search by name, email or dynamics_id"),
):
    skip = (page - 1) * size
    return AdminService.list_onboarded(skip, size, role=role, search=search)


@router.get(
    "/onboarded-users/{user_id}",
    summary="Get a single onboarded user across collections",
    status_code=status.HTTP_200_OK,
)
async def get_onboarded_user(user_id: str):
    return AdminService.get_onboarded_user(user_id)



@router.patch(
    "/onboarded-users/{user_id}/toggle-status",
    summary="Activate or deactivate an onboarded user",
    status_code=status.HTTP_200_OK,
)
def toggle_user_status(user_id: str):
    """
    Flips the is_active field for the given user.
    Returns { user_id, is_active: true|false }.
    """
    return AdminService.toggle_user_status(user_id)


@router.post(
    "/onboarded-users/{user_id}/reset-password",
    summary="Reset a user's password and email the new one to them",
    status_code=status.HTTP_200_OK,
)
async def reset_user_password(user_id: str):
    """
    Generates a new random password, updates the hash in DB,
    and sends the plain-text password to the user's email.
    """
    return await AdminService.reset_user_password(user_id)


@router.get(
    "/onboarded-users/{user_id}/profile",
    summary="Get user profile with Dynamics data merged in",
    status_code=status.HTTP_200_OK,
)
async def get_user_profile(user_id: str):
    return await AdminService.get_user_profile(user_id)


@router.patch(
    "/onboarded-users/{user_id}/profile",
    summary="Update a user's profile in MongoDB and Dynamics",
    status_code=status.HTTP_200_OK,
)
async def update_user_profile(user_id: str, data: UpdateUserProfileRequest):
    return await AdminService.update_user_profile(user_id, data)


# ── Content Management ────────────────────────────────────────────────────────

@router.post("/content", summary="Create a content item", status_code=status.HTTP_201_CREATED)
def create_content(payload: CreateContentRequest, request: Request):
    admin_email = getattr(request.state, "user_email", "admin")
    return ContentService.create_content(payload, admin_email)


@router.get("/content", summary="List content (paginated)", status_code=status.HTTP_200_OK)
def list_content(
    page:           int = Query(1, ge=1),
    size:           int = Query(20, ge=1, le=100),
    role:           str = Query(""),
    content_type:   str = Query(""),
    published_only: bool = Query(False),
    search:         str = Query(""),
):
    return ContentService.list_content(page, size, role, content_type, published_only, search)


@router.get("/content/{content_id}", summary="Get single content item", status_code=status.HTTP_200_OK)
def get_content(content_id: str):
    return ContentService.get_content(content_id)


@router.patch("/content/{content_id}", summary="Update a content item", status_code=status.HTTP_200_OK)
def update_content(content_id: str, payload: UpdateContentRequest):
    return ContentService.update_content(content_id, payload)


@router.delete("/content/{content_id}", summary="Delete a content item", status_code=status.HTTP_200_OK)
def delete_content(content_id: str):
    return ContentService.delete_content(content_id)


# ── Attachment upload ─────────────────────────────────────────────────────────

ALLOWED_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "text/plain",
    "image/jpeg",
    "image/png",
    "image/webp",
}
MAX_SIZE_MB = 20


@router.post("/content/upload-attachment", summary="Upload a file attachment for content", status_code=status.HTTP_200_OK)
async def upload_attachment(file: UploadFile = File(...)):
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{file.content_type}'. Allowed: PDF, Word, Excel, PowerPoint, TXT, images."
        )

    content = await file.read()
    size_mb = len(content) / (1024 * 1024)
    if size_mb > MAX_SIZE_MB:
        raise HTTPException(status_code=413, detail=f"File too large ({size_mb:.1f} MB). Max allowed is {MAX_SIZE_MB} MB.")

    # Build a unique blob path so filenames never collide
    safe_name = file.filename.replace(" ", "_")
    blob_name = f"admin-content/{uuid.uuid4().hex}/{safe_name}"

    url = upload_blob_from_file(blob_name, BytesIO(content))
    return {"url": url, "filename": file.filename, "size_mb": round(size_mb, 2)}


# ── Notification Manager ─────────────────────────────────────────────────────

@router.post("/alerts/send", summary="Send a direct alert to selected user groups", status_code=status.HTTP_200_OK)
async def send_alert(
    payload: CreateAlertRequest,
    request: Request,
    _=Depends(get_current_user),
):
    admin_email = getattr(request.state, "user_email", "admin")
    return await AlertService.send_alert(payload, admin_email)


@router.get("/alerts/logs", summary="List all sent alert logs", status_code=status.HTTP_200_OK)
def list_alert_logs(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    _=Depends(get_current_user),
):
    return AlertService.list_alert_logs(page=page, size=size)


@router.delete("/alerts/logs/{log_id}", summary="Delete a sent alert log", status_code=status.HTTP_200_OK)
def delete_alert_log(
    log_id: str,
    _=Depends(get_current_user),
):
    return AlertService.delete_log(log_id)


# ── Support Management (Escalations & Feedback) ──────────────────────────────

@router.get("/escalations", summary="List all escalations (vendor & client)", status_code=status.HTTP_200_OK)
def list_escalations(
    page:   int = Query(1, ge=1),
    size:   int = Query(20, ge=1, le=100),
    role:   Optional[str] = Query(None, description="Filter by role: vendor | client"),
    search: Optional[str] = Query(None, description="Search by subject or tracking_id"),
):
    return SupportService.list_escalations(page, size, role, search)


@router.get("/escalations/{role}/{escalation_id}", summary="Get single escalation details", status_code=status.HTTP_200_OK)
def get_escalation(role: str, escalation_id: str):
    if role not in ("vendor", "client"):
        raise HTTPException(status_code=400, detail="Invalid role")
    return SupportService.get_escalation(role, escalation_id)


@router.patch("/escalations/{role}/{escalation_id}/status", summary="Update escalation status", status_code=status.HTTP_200_OK)
def update_escalation_status(role: str, escalation_id: str, payload: UpdateEscalationStatusRequest):
    if role not in ("vendor", "client"):
        raise HTTPException(status_code=400, detail="Invalid role")
    return SupportService.update_escalation_status(role, escalation_id, payload.status)



@router.get("/feedback", summary="List all feedback (vendor & client)", status_code=status.HTTP_200_OK)
def list_feedback(
    page:   int = Query(1, ge=1),
    size:   int = Query(20, ge=1, le=100),
    role:   Optional[str] = Query(None, description="Filter by role: vendor | client"),
    search: Optional[str] = Query(None, description="Search by comments or tracking_id"),
):
    return SupportService.list_feedback(page, size, role, search)


@router.get("/feedback/{role}/{feedback_id}", summary="Get single feedback details", status_code=status.HTTP_200_OK)
def get_feedback(role: str, feedback_id: str):
    if role not in ("vendor", "client"):
        raise HTTPException(status_code=400, detail="Invalid role")
    return SupportService.get_feedback(role, feedback_id)

