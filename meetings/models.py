from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


# ── Request models ────────────────────────────────────────────────────────────

class DateTimeWithZone(BaseModel):
    """ISO-8601 datetime with timezone identifier."""
    dateTime: str           # e.g. "2026-03-12T09:00:00"
    timeZone: str = "India Standard Time"


class FreeSlotRequest(BaseModel):
    """
    Request body for fetching free slots of project managers.
    - user_id: the caller's Graph user ID or UPN (used as context for getSchedule)
    - schedules: list of project-manager emails/UPNs whose calendars to check
    - startTime / endTime: the date-range window to search
    - availabilityViewInterval: granularity in minutes (default 30)
    """
    user_id: str
    schedules: List[str]
    startTime: DateTimeWithZone
    endTime: DateTimeWithZone
    availabilityViewInterval: int = Field(default=30, ge=5, le=120)


class MeetingCreateRequest(BaseModel):
    """
    Request body to schedule a new Teams meeting.
    - user_id: organizer's Graph user ID or UPN
    - subject: meeting title
    - startDateTime / endDateTime: ISO-8601 strings
    - attendees: list of attendee email addresses (optional)
    - enforce_availability: if True, the backend checks all attendees are free
      before creating the meeting; returns 409 if anyone is busy
    """
    user_id: str
    subject: str
    startDateTime: str          # e.g. "2026-03-12T10:00:00Z"
    endDateTime: str            # e.g. "2026-03-12T11:00:00Z"
    attendees: Optional[List[str]] = None
    enforce_availability: bool = False


# ── Response models ───────────────────────────────────────────────────────────

class TimeSlot(BaseModel):
    """A single free window."""
    start: str
    end: str


class PersonFreeSlots(BaseModel):
    """Free slots for one person."""
    scheduleId: str
    freeSlots: List[TimeSlot]


class FreeSlotResponse(BaseModel):
    """Aggregated response containing free slots per person."""
    results: List[PersonFreeSlots]


# ── MongoDB document schema ──────────────────────────────────────────────────

class MeetingRecord(BaseModel):
    """Stored in MongoDB after a meeting is successfully created."""
    meeting_id: str                         # Graph meeting ID
    organizer_id: str                       # who created it
    subject: str
    start: str
    end: str
    attendees: List[str] = []
    join_url: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
