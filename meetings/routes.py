"""
Meeting routes – accessible by any authenticated user.
Endpoints:
  POST /meetings/free-slots   → view PM free slots before scheduling
  POST /meetings/schedule      → create a Teams meeting (with optional availability check)
  GET  /meetings/my-meetings   → list meetings created by the current user
"""

from fastapi import APIRouter, Depends, Query
from auth.middleware import get_current_user
from .models import FreeSlotRequest, FreeSlotResponse, MeetingCreateRequest
from .services import MeetingService

router = APIRouter(prefix="/meetings", tags=["Meetings"])


@router.post(
    "/free-slots",
    response_model=FreeSlotResponse,
    summary="Get free slots of project managers",
    description=(
        "Pass one or more project-manager emails and a date range. "
        "Returns computed free time windows (within business hours 9 AM – 6 PM) "
        "for each person so the caller can pick an available slot."
    ),
)
async def get_free_slots(
    req: FreeSlotRequest,
    _user=Depends(get_current_user),
):
    results = await MeetingService.get_free_slots(req)
    return FreeSlotResponse(results=results)


@router.post(
    "/schedule",
    summary="Schedule a new Teams meeting",
    description=(
        "Creates a Teams online meeting for the specified organizer. "
        "Set `enforce_availability` to true to block scheduling when any "
        "attendee is busy during the requested time slot."
    ),
)
async def schedule_meeting(
    req: MeetingCreateRequest,
    _user=Depends(get_current_user),
):
    meeting = await MeetingService.create_meeting(req)
    return meeting


@router.get(
    "/my-meetings",
    summary="List meetings created by the current user",
    description="Returns meeting records stored in the database for the authenticated user.",
)
async def list_my_meetings(
    user=Depends(get_current_user),
    limit: int = Query(50, ge=1, le=200),
):
    organizer_id = user.get("sub") or user.get("user_id", "")
    email = user.get("email") or user.get("unique_name") or user.get("upn", "")
    
    meetings = await MeetingService.list_meetings(organizer_id, email)
    return {"meetings": meetings[:limit]}
