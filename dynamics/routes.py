from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List

from pydantic import BaseModel
# from dynamics.services import fetch_filtered_data
from .teams import fetch_user_meetings, schedule_meeting, cancel_meeting
from auth.middleware import get_current_user, require_roles
from auth.roles import Role


router = APIRouter(
    prefix="/dynamics", 
    tags=["Dynamics"],
    dependencies=[Depends(require_roles(Role.CLIENT, Role.ADMIN, Role.VENDOR, Role.ALUMNI, Role.ADVISOR))])


class MeetingListRequest(BaseModel):
    user_email: str
    scope: str = "week"  # can be 'week' or 'month'

class ScheduleMeetingRequest(BaseModel):
    organizer_email: str
    client_emails: List[str]
    subject: str
    description: str
    start_time: datetime
    end_time: datetime

class CancelMeetingRequest(BaseModel):
    organizer_email: str
    meeting_id: str
    message: str = "The meeting has been cancelled."


# @router.get("/projectPlanningLineApiPage")
# async def project_planning_lines():
#     fields: List[str] = [
#         "jobNo", "jobTaskNo", "description", "type", "quantity",
#         "directUnitCostLCY", "unitPriceLCY", "totalPriceLCY",
#         "planningDate", "plannedDeliveryDate", "unitOfMeasureCode",
#         "locationCode", "lineType", "status",
#         "systemCreatedAt", "systemModifiedAt"
#     ]
#     return await fetch_filtered_data("projectPlanningLineApiPage", fields)


# @router.get("/projectApiPage")
# async def projects():
#     fields = [
#         "no", "description", "searchDescription", "billToCustomerNo",
#         "creationDate", "startingDate", "endingDate", "status",
#         "projectCategory", "bidManager", "overallProjectValue",
#         "projectDirector", "relationshipDirector", "projectManagerPrimus",
#         "projectBrief", "functions", "sector", "projectExecution",
#         "clientType", "sellToCustomerName", "billToName",
#         "officeLocation", "systemCreatedAt", "systemModifiedAt"
#     ]
#     return await fetch_filtered_data("projectApiPage", fields)


# @router.get("/documentAttachmentApiPage")
# async def document_attachments():
#     fields = [
#         "no", "documentType", "attachedDate", "fileName", "fileType",
#         "fileExtension", "attachedBy", "user", "oneDriveLink",
#         "systemCreatedAt", "systemModifiedAt"
#     ]
#     return await fetch_filtered_data("documentAttachmentApiPage", fields)


# @router.get("/projectTaskApiPage")
# async def project_tasks():
#     fields = [
#         "jobNo", "jobTaskNo", "description", "jobTaskType",
#         "scheduleTotalCost", "scheduleTotalPrice", "contractTotalPrice",
#         "startDate", "endDate", "projectCategory",
#         "actualBillingAmount", "remainingAmount",
#         "systemCreatedAt", "systemModifiedAt"
#     ]
#     return await fetch_filtered_data("projectTaskApiPage", fields)



@router.post("/meetings")
def list_and_save_weekly_meetings(payload: MeetingListRequest, user: dict = Depends(get_current_user)):
    """
    API route to return user's Teams meetings for this week or month.
    """
    # Authorization check
    email = (user.get("email") or "").lower()
    req_email = (payload.user_email or "").lower()
    
    print(f"Dynamics Meeting Auth check: user_email='{email}', payload_user_email='{req_email}'")

    if email != req_email and "admin" not in user.get("roles", []):
         raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User not Authorised to access meetings for {req_email}"
        )

    try:
        meetings = fetch_user_meetings(user_email=payload.user_email, scope=payload.scope)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
 
    return {
        "email": payload.user_email,
        "scope": payload.scope,
        "count": len(meetings),
        "meetings": meetings,
    }
 
 
@router.post("/schedule-meeting")
def schedule_user_meeting(payload: ScheduleMeetingRequest, user: dict = Depends(get_current_user)):
    """
    API route to schedule a Teams meeting with a client.
    """
    email = (user.get("email") or "").lower()
    req_email = (payload.organizer_email or "").lower()
    
    print(f"Dynamics Schedule Auth check: user_email='{email}', payload_organizer_email='{req_email}'")

    if email != req_email and "admin" not in user.get("roles", []):
         raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User not Authorised to schedule meetings for {req_email}"
        )

    try:
        meeting = schedule_meeting(
            payload.organizer_email,
            payload.client_emails,
            payload.subject,
            payload.description,
            payload.start_time,
            payload.end_time,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
  
    return {
        "organizer": payload.organizer_email,
        "client": payload.client_emails,
        "subject": payload.subject,
        "start": payload.start_time,
        "end": payload.end_time,
        "joinUrl": meeting.get("onlineMeeting", {}).get("joinUrl"),
        "meetingId": meeting.get("id"),
    }
 
 
@router.post("/cancel-meeting")
def cancel_user_meeting(payload: CancelMeetingRequest, user: dict = Depends(get_current_user)):
    """
    API route to cancel a scheduled Teams meeting.
    """
    email = (user.get("email") or "").lower()
    req_email = (payload.organizer_email or "").lower()
    
    print(f"Dynamics Cancel Auth check: user_email='{email}', payload_organizer_email='{req_email}'")

    if email != req_email and "admin" not in user.get("roles", []):
         raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User not Authorised to cancel meetings for {req_email}"
        )

    try:
        result = cancel_meeting(payload.organizer_email, payload.meeting_id, payload.message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
  
    return result
