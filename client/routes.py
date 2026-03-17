from io import BytesIO
import logging
from fastapi import APIRouter, Body, Depends, File, HTTPException, Query, UploadFile, Form, status
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

from pydantic import BaseModel, EmailStr
from .dashboard.services import fetch_client_projects_by_email, get_project_dashboard_details, TeamMemberOut, fetch_project_team_members, get_document_attachments_for_project, get_attachment_and_stream
from .escalations.services import EscalationService
from .escalations.models import EscalationIn, EscalationOut
from .dashboard.models import DashboardOverview, ProjectDetailsOut
from .feedback.models import FeedbackIn, FeedbackUpdate
from .feedback.enums import FeedbackCategory, AttachmentCategory
from .feedback.services import create_feedback, get_feedback_by_id, list_feedback, update_feedback_by_id
from .escalations.enums import EscalationType, Urgency
from auth.middleware import get_current_user, require_roles
from auth.roles import Role


logger = logging.getLogger("projects.router")
handler = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)


router = APIRouter(
    prefix="/client",
    tags=["Client"],
    dependencies=[Depends(require_roles(Role.CLIENT))]
)



############################# ESCALATIONS #############################


# Allowed MIME types for uploaded files
ALLOWED_FILE_TYPES = {
    "application/pdf",  # .pdf
    "application/msword",  # .doc (Microsoft Word 97-2003)
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # .docx (modern Word)
    "image/png",  # .png
    "image/jpeg"  # .jpg, .jpeg
}


FRONTEND_TO_BACKEND_TYPE_ESCALATION = {
    "Project Delay": "project_delay",
    "Quality Concern": "quality_concern",
    "Data / Access Issue": "data_access_issue",
    "Communication Gap": "communication_gap",
    "Billing & Payments": "billing_payments",
    "Technical Issue": "technical_issue",
    "Resource / Staffing Concern": "resource_staffing",
    "Change Request / Scope Issue": "change_scope_issue",
    "Compliance / Policy Concern": "compliance_policy",
    "Other": "other",
}


BACKEND_TO_FRONTEND_TYPE_ESCALATION = {v: k for k, v in FRONTEND_TO_BACKEND_TYPE_ESCALATION.items()}


FRONTEND_TO_BACKEND_TYPE_FEEDBACK = {
    "Delivery & Timelines": "delivery_&_timelines",
    "Communication": "communication",
    "Technical Expertise": "technical_expertise",
    "Support": "support",
    "Documentation": "documentation",
    "Team Professionalism": "team_professionalism",
    "Overall Experience": "overall_experience",
    "Other": "other",
    "Milestone Feedback": "milestone_feedback",
}


BACKEND_TO_FRONTEND_TYPE_FEEDBACK = {v: k for k, v in FRONTEND_TO_BACKEND_TYPE_FEEDBACK.items()}



@router.post(
    "/escalations",
    response_model=EscalationOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new escalation with file uploads",
    dependencies=[Depends(require_roles(Role.CLIENT))]
)
async def create_escalation(
    project_id: str = Form(...),
    type: str = Form(...),
    urgency: str = Form(...),
    subject: str = Form(...),
    description: str = Form(...),
    execution_date: Optional[datetime] = Form(None),
    files: List[UploadFile] = File([]),
    user: dict = Depends(get_current_user)
):
    print("User in escalation endpoint:", user)
    print("Files received at API:", files)

     # Convert frontend label -> backend enum value
    normalized_type = FRONTEND_TO_BACKEND_TYPE_ESCALATION.get(type)
    if not normalized_type:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported escalation type: {type}"
        )
    
    # Convert UploadFiles to (filename, BytesIO) tuples
    file_contents = []
    for file in files:
        # 🔐 Validate file type
        if file.content_type not in ALLOWED_FILE_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {file.content_type}. Allowed types are: {', '.join(ALLOWED_FILE_TYPES)}"
            )
        content = await file.read()
        file_contents.append((file.filename, BytesIO(content)))

    data = EscalationIn(
        project_id=project_id,
        type=EscalationType(normalized_type),
        urgency=Urgency(urgency),
        subject=subject,
        description=description,
        execution_date=execution_date
    )
    return await EscalationService.create_escalation(data, file_contents, user=user)


@router.get(
    "/escalations/{project_no}",
    response_model=List[EscalationOut],
    summary="List all escalations for the current client",
    dependencies=[Depends(require_roles(Role.CLIENT))]
)
async def list_client_escalations(
    project_no: str,
    user: dict = Depends(get_current_user)
):
    return await EscalationService.list_escalations_for_client(
        user, project_no, BACKEND_TO_FRONTEND_TYPE_ESCALATION
    )

@router.patch(
    "/escalations/{tracking_id}/reopen",
    response_model=EscalationOut,
    summary="Reopen escalation when client responds"
)
async def reopen_escalation(
    tracking_id: str, 
    user: dict = Depends(get_current_user)
):
    return await EscalationService.reopen_escalation(tracking_id, user)


############################# DASHBOARD & PROJECTS #############################


class ProjectKV(BaseModel):
    project_id: str
    project_name: str
    sector: str
    clientType: str
    status: str


class ProjectsSummaryResponse(BaseModel):
    client_id: str
    client_name: str
    total_projects: int
    ongoing_projects: int
    completed_projects: int
    totalOverallProjectValue: float
    projects: List[ProjectKV]


@router.post("/dashboard", response_model=ProjectsSummaryResponse)
async def get_projects_for_client(client_email: EmailStr = Body(..., embed=True)):
    """
    Route: Accepts client_email, returns project summary for that client.
    """
    # print("Hiiiiiii")
    result = await fetch_client_projects_by_email(client_email)
    # print("Result:", result)
    return result


@router.get("/{project_no}/dashboard", response_model=Dict[str, Any])
async def get_project_dashboard(project_no: str):
    """
    Get all dashboard details of a specific project.
    """
    project = await get_project_dashboard_details(project_no)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    return project


@router.get("/project/{project_no}/team-members", response_model=List[TeamMemberOut])
async def get_project_team_members_route(project_no: str):
    """
    Return team members for a project (project_no).
    """
    members = await fetch_project_team_members(project_no)
    return members



##############################  FEEDBACK  ##############################


@router.post("/feedback", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def post_feedback(
    client_email: Optional[str] = Form(None),
    project_no: str = Form(...),
    project_name: str = Form(...),
    category: str = Form(...),
    team_member_id: Optional[str] = Form(None),
    milestone_name: Optional[str] = Form(None),
    communication_quality: Optional[int] = Form(None),
    team_collaboration: Optional[int] = Form(None),
    solution_quality: Optional[int] = Form(None),
    overall_satisfaction: Optional[int] = Form(None),
    comments: Optional[str] = Form(None),
    feedback_attachments_experience_letter: List[UploadFile] = File([]),        # NEW
    feedback_attachments_appreciation_letter: List[UploadFile] = File([]),     # NEW
    feedback_attachments_completion_certificate: List[UploadFile] = File([]),  # NEW
    user: dict = Depends(get_current_user)    # keep for auth / deriving client email
):
    """
    Submit feedback.
    """
    print("Files received at API - counts:", {
    "experience": len(feedback_attachments_experience_letter),
    "appreciation": len(feedback_attachments_appreciation_letter),
    "completion": len(feedback_attachments_completion_certificate)
    })

    print("1")
    # Convert frontend label -> backend enum value
    normalized_type = FRONTEND_TO_BACKEND_TYPE_FEEDBACK.get(category)
    if not normalized_type:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported escalation type: {type}"
        )

    # Convert UploadFiles to (filename, BytesIO, AttachmentCategory) tuples and validate
    file_contents: List[Tuple[str, BytesIO, AttachmentCategory]] = []


    # helper to process a list and attach enum
    async def _read_and_validate(list_of_files: List[UploadFile], enum_type: AttachmentCategory):
        for f in list_of_files:
            if f.content_type not in ALLOWED_FILE_TYPES:
                raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {f.content_type}. Allowed types are: {', '.join(ALLOWED_FILE_TYPES)}"
            )
            content = await f.read()
            file_contents.append((f.filename, BytesIO(content), enum_type))


    # Process each category's files
    await _read_and_validate(feedback_attachments_experience_letter, AttachmentCategory.EXPERIENCE_LETTER)
    await _read_and_validate(feedback_attachments_appreciation_letter, AttachmentCategory.APPRECIATION_LETTER)
    await _read_and_validate(feedback_attachments_completion_certificate, AttachmentCategory.COMPLETION_CERTIFICATE)
    
    # ✅ Include milestone_name only if milestone feedback
    milestone_name_value = milestone_name if normalized_type == FeedbackCategory.MILESTONE_FEEDBACK.value else None

    print("3")  
    # construct FeedbackIn (same fields as your Pydantic model)
    feedback_payload = FeedbackIn(
        client_email=client_email,
        project_no=project_no,
        project_name=project_name,
        category=FeedbackCategory(normalized_type),
        team_member_id=team_member_id,
        communication_quality=communication_quality,
        team_collaboration=team_collaboration,
        solution_quality=solution_quality,
        overall_satisfaction=overall_satisfaction,
        comments=comments,
        milestone_name=milestone_name_value,
    )
    print("4")  
    print("Payload received at API:", feedback_payload)
    created = await create_feedback(feedback_payload, file_contents)
    return created


class FeedbackFilter(BaseModel):
    client_email: Optional[EmailStr] = None
    project_no: Optional[str] = None


@router.post("/get-feedback", response_model=Dict[str, Any])
async def get_feedbacks(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=200),
    filters: FeedbackFilter = Body(...)
):
    return await list_feedback(skip=skip, limit=limit, project_no=filters.project_no, client_email=filters.client_email)


@router.get("/feedback/{feedback_id}", response_model=Dict[str, Any])
async def get_feedback(feedback_id: str):
    doc = await get_feedback_by_id(feedback_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feedback not found")
    return doc



@router.patch("/feedback/{feedback_id}", response_model=Dict[str, Any])
async def patch_feedback(feedback_id: str, payload: FeedbackUpdate):
    """
    Partially update a feedback record. Only fields present in the payload will be updated.
    """
    updated = await update_feedback_by_id(feedback_id, payload)
    return updated


###########################   ONEDRIVE SETUP   ###########################


@router.get("/project/{project_no}/document-attachments", response_model=List[Dict[str, Any]])
async def list_project_document_attachments(project_no: str):
    """
    List document attachments for a project, with constructed file_name.
    """
    rows = await get_document_attachments_for_project(project_no)
    # return only useful fields
    out: List[Dict[str, Any]] = []
    for r in rows:
        out.append({
            "id": r.get("id"),
            "no": r.get("no"),
            "document_type": r.get("documentType"),
            "file_name": r.get("file_name"),
            "fileType": r.get("fileType"),
            "fileExtension": r.get("fileExtension"),
            "createdDate": r.get("systemCreatedAt"),
            "modifiedDate": r.get("systemModifiedAt"),
            "oneDriveLink": r.get("oneDriveLink"),
        })
    return out


class FileRequest(BaseModel):
    file_name: str


@router.post("/project/{project_no}/document-attachments/content")
async def download_project_attachment_content(payload: FileRequest):
    """
    Stream the attachment content back to the client.
    """
    return await get_attachment_and_stream(payload.file_name)



# @router.get(
#     "/projects",
#     response_model=DashboardOverview,
#     summary="Get all projects for current client (dropdown + counts)",
#     dependencies=[Depends(require_roles(Role.CLIENT))],
# )
# async def api_get_projects_for_client(user: dict = Depends(get_current_user)):
#     """
#     Returns:
#       - list of {project_id, project_name} (for dropdown)
#       - total_projects (len)
#       - ongoing_projects (status == 'Open')
#     """
#     try:
#         client_email = user.get("user_email") or user.get("email")
#         if not client_email:
#             logger.warning("Missing user email in request state")
#             raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing user email")

#         logger.info("Fetching projects for client_email=%s", client_email)
#         overview = await get_projects_for_client(client_email)
#         return overview

#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.exception("Unhandled error in api_get_projects_for_client: %s", e)
#         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch projects")


# @router.get(
#     "/projects/{project_no}",
#     response_model=ProjectDetailsOut,
#     summary="Get full project details for selected project",
#     dependencies=[Depends(require_roles(Role.CLIENT))],
# )
# async def api_get_project_details(project_no: str, user: dict = Depends(get_current_user)):
    # """
    # Returns detailed information for a selected project:
    #   - assigned to (project manager), start date, status
    #   - team members (pulled from Dynamics)
    #   - phases and tasks (from project doc, if available)
    # """
    # try:
    #     client_email = user.get("user_email") or user.get("email")
    #     if not client_email:
    #         logger.warning("Missing user email in request state")
    #         raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing user email")

    #     logger.info("Fetching project details for project_no=%s and client_email=%s", project_no, client_email)
    #     details = await get_project_details(client_email, project_no)
    #     return details

    # except HTTPException:
    #     raise
    # except Exception as e:
    #     logger.exception("Unhandled error in api_get_project_details: %s", e)
    #     raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch project details")