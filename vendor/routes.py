from datetime import datetime
from io import BytesIO
from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, EmailStr
from typing import Dict, Any, List, Optional
from .dashboard.services import (
    summarize_vendor_pos, 
    fetch_vendor_invoices_by_email, 
    get_invoice_items_and_aggregates,
    create_submitted_invoice,
    list_vendor_submitted_invoices
)
from .dashboard.models import VendorInvoiceCreate, VendorInvoiceSubmitted
from admin.services import AdminService

from auth.middleware import get_current_user, require_roles
from .escalations.enums import EscalationType, Urgency
from .escalations.services import EscalationService
from .escalations.models import EscalationOut, EscalationIn
from .feedback.services import create_feedback
from .feedback.models import FeedbackIn
from .feedback.enums import FeedbackCategory
from admin.models import OnboardUserRequest, UpdateUserProfileRequest, CreateContentRequest, UpdateContentRequest, CreateAlertRequest, UpdateEscalationStatusRequest
from auth.roles import Role


router = APIRouter(
    prefix="/vendor",
    tags=["Vendor"],
    dependencies=[Depends(require_roles(Role.VENDOR))]
)


# Allowed MIME types for uploaded files
ALLOWED_FILE_TYPES = {
    "application/pdf",  # .pdf
    "application/msword",  # .doc (Microsoft Word 97-2003)
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # .docx (modern Word)
    "image/png",  # .png
    "image/jpeg"  # .jpg, .jpeg
}


##############################  DASHBOARD  ##############################


@router.post(
    "/purchase-orders-dashboard",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_roles(Role.VENDOR))],
    
)
async def vendor_purchase_orders(vendor_email: EmailStr = Body(..., embed=True), user: dict = Depends(get_current_user)):
    """
    Accepts vendor_email (JSON body) — returns vendor purchase orders summary for dashboard.
    """
    email = (user.get("email") or "").lower()
    vendor_email_lower = (vendor_email or "").lower()
    
    print(f"Auth check: user_email='{email}', body_vendor_email='{vendor_email_lower}'")

    if email != vendor_email_lower:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User not Authorised. Token email: {email}, Body email: {vendor_email_lower}"
        )
    # print(f"vendor_email: {vendor_email}")
    result = await summarize_vendor_pos(vendor_email)
    return result


@router.post(
    "/invoice-orders-dashboard",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_roles(Role.VENDOR))]
)
async def vendor_invoices(vendor_email: EmailStr = Body(..., embed=True), user: dict = Depends(get_current_user)):
    """
    Returns per-invoice list and aggregates for the given vendor_email.
    Body: { "vendor_email": "vendor@example.com" }
    """
    email = (user.get("email") or "").lower()
    vendor_email_lower = (vendor_email or "").lower()
    
    print(f"Auth check: user_email='{email}', body_vendor_email='{vendor_email_lower}'")

    if email != vendor_email_lower:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User not Authorised. Token email: {email}, Body email: {vendor_email_lower}"
        )
    result = await fetch_vendor_invoices_by_email(vendor_email)
    return result


class InvoiceItemsRequest(BaseModel):
    document_no: str
    vendor_email: Optional[str] = None   # optional; service will lookup vendor if provided


@router.post(
    "/invoice-line-orders-dashboard",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_roles(Role.VENDOR))]
)
async def invoice_items_endpoint(payload: InvoiceItemsRequest = Body(...)):
    """
    Request body:
      { "document_no": "108204", "vendor_email": "vendor@x.com" }

    Returns per-line invoice items and aggregates.
    """
    return await get_invoice_items_and_aggregates(payload.document_no, vendor_email=payload.vendor_email)


@router.get(
    "/profile",
    summary="Get vendor profile with Dynamics data merged in",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_roles(Role.VENDOR))]
)
async def get_vendor_profile(user: dict = Depends(get_current_user)):
    """
    Fetch the profile of the currently logged-in vendor.
    """
    user_id = user.get("id") or user.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User ID not found in token"
        )
    return await AdminService.get_user_profile(user_id)


@router.patch(
    "/profile",
    summary="Update vendor profile in MongoDB and Dynamics",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_roles(Role.VENDOR))]
)
async def update_vendor_profile(data: UpdateUserProfileRequest, user: dict = Depends(get_current_user)):
    """
    Update the profile of the currently logged-in vendor.
    """
    user_id = user.get("id") or user.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User ID not found in token"
        )
    return await AdminService.update_user_profile(user_id, data)


##############################  FEEDBACK  ##############################



FRONTEND_TO_BACKEND_TYPE_FEEDBACK = {
    "Procurement Process": "procurement_process",
    "Payment & Finance": "payment_finance",
    "Communication & Support": "communication_support",
    "Meeting & Coordination": "meeting_coordination",
    "System Experience (Portal / D365)": "system_experience",
    "Policy & Compliance": "policy_compliance",
    "Overall Experience": "overall_experience",
    "Suggestions for Improvement": "suggestions_improvement",
    "Other": "other"
}


BACKEND_TO_FRONTEND_TYPE_FEEDBACK = {v: k for k, v in FRONTEND_TO_BACKEND_TYPE_FEEDBACK.items()}


@router.post("/feedback", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def post_feedback(
    vendor_email: Optional[str] = Form(None),
    category: str = Form(...),
    communication_quality: Optional[int] = Form(None),
    team_collaboration: Optional[int] = Form(None),
    overall_satisfaction: Optional[int] = Form(None),
    comments: Optional[str] = Form(None),
    files: List[UploadFile] = File([]),
    user: dict = Depends(get_current_user)    # keep for auth / deriving vendor email
):
    """
    Submit feedback.
    """
    print("Files received at API:", files)
    print("1")
    # Convert frontend label -> backend enum value
    normalized_type = FRONTEND_TO_BACKEND_TYPE_FEEDBACK.get(category)
    if not normalized_type:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported escalation type: {type}"
        )

    print("2")
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

    print("3")  
    # construct FeedbackIn (same fields as your Pydantic model)
    feedback_payload = FeedbackIn(
        vendor_email=vendor_email,
        category=FeedbackCategory(normalized_type),
        communication_quality=communication_quality,
        team_collaboration=team_collaboration,
        overall_satisfaction=overall_satisfaction,
        comments=comments
    )
    print("4")  
    print("Payload received at API:", feedback_payload)
    created = await create_feedback(feedback_payload, file_contents)
    return created


##############################  ESCALATION  ##############################


FRONTEND_TO_BACKEND_TYPE_ESCALATION = {
    "Payment Delay / Discrepancy": "payment_delay_discrepancy",
    "Purchase Order Issue": "purchase_order_issue",
    "Invoice Rejection / Clarification": "invoice_rejection_clarification",
    "Meeting / Communication Delay": "meeting_communication_delay",
    "Contract / Compliance Concern": "contract_compliance_concern",
    "Urgent Support Request": "urgent_support_request",
    "Policy / Approval Escalation": "policy_approval_escalation",
    "Payment Followup": "payment_followup",
    "Other": "other"
}


BACKEND_TO_FRONTEND_TYPE_ESCALATION = {v: k for k, v in FRONTEND_TO_BACKEND_TYPE_ESCALATION.items()}


@router.post(
    "/escalations",
    response_model=EscalationOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new escalation with file uploads",
    dependencies=[Depends(require_roles(Role.VENDOR))]
)
async def create_escalation(
    type: str = Form(...),
    urgency: str = Form(...),
    subject: str = Form(...),
    description: str = Form(...),
    execution_date: Optional[datetime] = Form(None),
    files: List[UploadFile] = File([]),
    user: dict = Depends(get_current_user)
):
    print("User in escalation endpoint:", user)

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
        type=EscalationType(normalized_type),
        urgency=Urgency(urgency),
        subject=subject,
        description=description,
        execution_date=execution_date
    )
    return await EscalationService.create_escalation(data, file_contents, user=user)


@router.get(
    "/escalations",
    response_model=List[EscalationOut],
    summary="List all escalations for the current vendor",
    dependencies=[Depends(require_roles(Role.VENDOR))]
)
async def list_vendor_escalations(
    user: dict = Depends(get_current_user)
):
    return await EscalationService.list_escalations_for_vendor(
        user, BACKEND_TO_FRONTEND_TYPE_ESCALATION
    )











##############################  INVOICE SUBMISSION  ##############################

@router.post("/submit-invoice", status_code=status.HTTP_201_CREATED)
async def submit_invoice(
    vendor_email: EmailStr = Form(...),
    vendor_name: str = Form(...),
    invoice_id: str = Form(...),
    product_or_service: str = Form(...),
    quantity: float = Form(...),
    due_date: str = Form(...),
    unit_price: float = Form(...),
    discount: float = Form(0.0),
    amount: float = Form(...),
    inc_tax: float = Form(0.0),
    proposal: Optional[str] = Form(None),
    invoice_pdf: UploadFile = File(...),
    user: dict = Depends(get_current_user)
):
    """
    Vendor submits a new invoice with a PDF file.
    """
    # 🔐 Auth check
    email = (user.get("email") or "").lower()
    if email != vendor_email.lower():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only submit invoices for your own account."
        )

    # Validate file type
    if invoice_pdf.content_type != "application/pdf":
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are allowed for invoice submission."
        )

    content = await invoice_pdf.read()
    
    data = VendorInvoiceCreate(
        vendor_email=vendor_email,
        vendor_name=vendor_name,
        invoice_id=invoice_id,
        product_or_service=product_or_service,
        quantity=quantity,
        due_date=due_date,
        unit_price=unit_price,
        discount=discount,
        amount=amount,
        inc_tax=inc_tax,
        proposal_interest_statement=proposal
    )

    return await create_submitted_invoice(data, BytesIO(content), invoice_pdf.filename)


@router.get("/submitted-invoices", response_model=List[Dict[str, Any]])
async def get_submitted_invoices(user: dict = Depends(get_current_user)):
    """
    Get all invoices submitted manually by the current vendor.
    """
    email = (user.get("email") or "").lower()
    return await list_vendor_submitted_invoices(email)
