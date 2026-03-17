"""
MeetingService – wraps Microsoft Graph API calls for:
  1. Fetching free/busy schedules and computing free windows
  2. Creating Teams online meetings with optional availability checks
  3. Storing meeting records in MongoDB
"""

import httpx
from datetime import datetime, timedelta
from typing import List, Dict, Any
from fastapi import HTTPException

from config import settings
from .db import meetings_col
from .models import (
    FreeSlotRequest,
    MeetingCreateRequest,
    PersonFreeSlots,
    TimeSlot,
    MeetingRecord,
)

GRAPH_TOKEN_URL = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
GRAPH_BASE = "https://graph.microsoft.com/v1.0"

# Business-hours window (used to clip free-slot results)
BUSINESS_HOUR_START = 9   # 09:00
BUSINESS_HOUR_END = 18    # 18:00


class MeetingService:
    """Stateless helper methods – all class-level so they can be called directly."""

    # ── Token helper ──────────────────────────────────────────────────────────

    @staticmethod
    async def _get_app_token() -> str:
        """Acquire an app-only (client credentials) access token for Graph."""
        token_url = GRAPH_TOKEN_URL.format(tenant=settings.azure_tenant_id)
        data = {
            "grant_type": "client_credentials",
            "client_id": settings.azure_client_id,
            "client_secret": settings.azure_client_secret,
            "scope": "https://graph.microsoft.com/.default",
        }
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(token_url, data=data)

        if resp.status_code != 200:
            raise HTTPException(
                status_code=502,
                detail=f"Failed to obtain Graph token: {resp.status_code} {resp.text}",
            )

        access_token = resp.json().get("access_token")
        if not access_token:
            raise HTTPException(status_code=502, detail="No access_token in token response")
        return access_token

    @staticmethod
    def _resolve_user_id(user_id: str) -> str:
        """
        Ensures the user_id passed to Graph is a valid identifier (UPN/Email).
        If it looks like a Dynamics ID (e.g. C000001, V000001), fallback to service account.
        """
        if "@" not in user_id:
            return settings.onedrive_user_email
        return user_id

    # ── Free-slot computation ─────────────────────────────────────────────────

    @staticmethod
    def _compute_free_windows(
        schedule_items: List[Dict[str, Any]],
        range_start: datetime,
        range_end: datetime,
        interval_minutes: int,
    ) -> List[TimeSlot]:
        """
        Given busy/OOF items from Graph's getSchedule, subtract them from the
        requested range (clipped to business hours) and return the remaining
        free windows, each at least `interval_minutes` long.
        """
        # Collect busy intervals
        busy: List[tuple] = []
        for item in schedule_items:
            status = item.get("status", "")
            if status in ("busy", "oof", "tentative"):
                s = datetime.fromisoformat(item["start"]["dateTime"].replace("Z", "+00:00"))
                e = datetime.fromisoformat(item["end"]["dateTime"].replace("Z", "+00:00"))
                busy.append((s, e))

        # Sort busy intervals
        busy.sort(key=lambda x: x[0])

        # Walk day-by-day so we can clip to business hours per day
        free_slots: List[TimeSlot] = []
        current_day = range_start.date()
        end_day = range_end.date()

        while current_day <= end_day:
            # Skip weekends (Saturday=5, Sunday=6)
            if current_day.weekday() >= 5:
                current_day += timedelta(days=1)
                continue

            # Business-hours window for this day
            day_start = datetime(
                current_day.year, current_day.month, current_day.day,
                BUSINESS_HOUR_START, 0, 0,
                tzinfo=range_start.tzinfo,
            )
            day_end = datetime(
                current_day.year, current_day.month, current_day.day,
                BUSINESS_HOUR_END, 0, 0,
                tzinfo=range_start.tzinfo,
            )

            # Clip to requested range
            window_start = max(day_start, range_start)
            window_end = min(day_end, range_end)

            if window_start >= window_end:
                current_day += timedelta(days=1)
                continue

            # Subtract busy intervals from this window
            pointer = window_start
            for b_start, b_end in busy:
                if b_end <= pointer:
                    continue
                if b_start >= window_end:
                    break

                gap_end = min(b_start, window_end)
                if gap_end > pointer:
                    duration = (gap_end - pointer).total_seconds() / 60
                    if duration >= interval_minutes:
                        free_slots.append(TimeSlot(
                            start=pointer.isoformat(),
                            end=gap_end.isoformat(),
                        ))
                pointer = max(pointer, b_end)

            # Remaining gap after the last busy block
            if pointer < window_end:
                duration = (window_end - pointer).total_seconds() / 60
                if duration >= interval_minutes:
                    free_slots.append(TimeSlot(
                        start=pointer.isoformat(),
                        end=window_end.isoformat(),
                    ))

            current_day += timedelta(days=1)

        return free_slots

    # ── Public API methods ────────────────────────────────────────────────────

    # Microsoft timezone name → UTC offset mapping
    MS_TZ_OFFSETS = {
        "India Standard Time": timedelta(hours=5, minutes=30),
        "UTC": timedelta(0),
        "Pacific Standard Time": timedelta(hours=-8),
        "Eastern Standard Time": timedelta(hours=-5),
        "Central Standard Time": timedelta(hours=-6),
        "Mountain Standard Time": timedelta(hours=-7),
        "GMT Standard Time": timedelta(0),
    }

    @classmethod
    async def get_free_slots(cls, req: FreeSlotRequest) -> List[PersonFreeSlots]:
        """
        Call Graph getSchedule, then compute free windows for each person.
        Returns a list of PersonFreeSlots.
        """
        token = await cls._get_app_token()
        effective_user = cls._resolve_user_id(req.user_id)

        url = f"{GRAPH_BASE}/users/{effective_user}/calendar/getSchedule"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        body = {
            "schedules": req.schedules,
            "startTime": {
                "dateTime": req.startTime.dateTime,
                "timeZone": req.startTime.timeZone,
            },
            "endTime": {
                "dateTime": req.endTime.dateTime,
                "timeZone": req.endTime.timeZone,
            },
            "availabilityViewInterval": req.availabilityViewInterval,
        }

        print(f"--- FREE SLOTS DEBUG ---")
        print(f"URL: {url}")
        print(f"BODY: {body}")

        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(url, headers=headers, json=body)

        if resp.status_code != 200:
            raise HTTPException(
                status_code=resp.status_code,
                detail=f"Graph getSchedule failed: {resp.text}",
            )

        graph_data = resp.json()
        print(f"--- GRAPH RAW RESPONSE ---")
        print(f"{graph_data}")

        # ── Convert Graph UTC times to user's local timezone ──────────────
        utc_offset = cls.MS_TZ_OFFSETS.get(req.startTime.timeZone, timedelta(0))
        for schedule in graph_data.get("value", []):
            for item in schedule.get("scheduleItems", []):
                for key in ("start", "end"):
                    raw_dt = item[key]["dateTime"]
                    # Strip trailing fractional seconds (e.g. ".0000000")
                    if "." in raw_dt:
                        raw_dt = raw_dt[:raw_dt.index(".")]
                    utc_dt = datetime.fromisoformat(raw_dt)
                    local_dt = utc_dt + utc_offset
                    item[key]["dateTime"] = local_dt.isoformat()
                    item[key]["timeZone"] = req.startTime.timeZone

        range_start = datetime.fromisoformat(req.startTime.dateTime)
        range_end = datetime.fromisoformat(req.endTime.dateTime)

        results: List[PersonFreeSlots] = []
        for schedule in graph_data.get("value", []):
            schedule_id = schedule.get("scheduleId", "unknown")
            items = schedule.get("scheduleItems", [])
            availability_view = schedule.get("availabilityView", "")
            print(f"--- Schedule for {schedule_id} ---")
            print(f"  scheduleItems (local): {items}")
            print(f"  availabilityView: {availability_view}")
            free = cls._compute_free_windows(
                items, range_start, range_end, req.availabilityViewInterval,
            )
            results.append(PersonFreeSlots(
                scheduleId=schedule_id,
                freeSlots=free,
            ))

        return results

    @classmethod
    async def create_meeting(cls, req: MeetingCreateRequest) -> Dict[str, Any]:
        """
        Create a Teams online meeting via Graph API.
        If enforce_availability is True, check all attendees + organizer first.
        Stores the meeting record in MongoDB.
        """
        token = await cls._get_app_token()

        # ── Block weekends ────────────────────────────────────────────────────
        try:
            from dateutil import parser as dt_parser
            temp_start = dt_parser.parse(req.startDateTime)
            if temp_start.weekday() >= 5: # 5=Saturday, 6=Sunday
                raise HTTPException(
                    status_code=400,
                    detail="Meetings cannot be scheduled on weekends (Saturday or Sunday)."
                )
        except HTTPException:
            raise
        except Exception as e:
            print(f"Weekend check warning: {e}")

        # ── Debug: decode token to check permissions ──────────────────────────
        import base64, json as _json
        try:
            payload_part = token.split(".")[1]
            payload_part += "=" * (4 - len(payload_part) % 4)  # fix padding
            decoded = _json.loads(base64.urlsafe_b64decode(payload_part))
            print(f"--- TOKEN ROLES ---")
            print(f"  roles: {decoded.get('roles', [])}")
            print(f"  aud: {decoded.get('aud')}")
            print(f"  tid: {decoded.get('tid')}")
        except Exception as e:
            print(f"  Could not decode token: {e}")

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        # ── Optional availability check ──────────────────────────────────────
        effective_user = cls._resolve_user_id(req.user_id)

        # Graph onlineMeetings API is VERY sensitive to date formats. 
        # It strongly prefers UTC with 'Z' suffix.
        start_dt = req.startDateTime
        end_dt = req.endDateTime
        try:
            from dateutil import parser as dt_parser
            import pytz
            # Parse everything and convert to UTC Z
            parse_start = dt_parser.parse(start_dt)
            if parse_start.tzinfo is None:
                parse_start = pytz.timezone("Asia/Kolkata").localize(parse_start)
            start_dt = parse_start.astimezone(pytz.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

            parse_end = dt_parser.parse(end_dt)
            if parse_end.tzinfo is None:
                parse_end = pytz.timezone("Asia/Kolkata").localize(parse_end)
            end_dt = parse_end.astimezone(pytz.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        except Exception as e:
            print(f"!!! Date parsing failed: {e}")
            # fall back to string manipulation if parser fails
            if "+" in start_dt:
                start_dt = start_dt.split("+")[0] + "Z"
                end_dt = end_dt.split("+")[0] + "Z"

        if req.enforce_availability and req.attendees:
            users_to_check = req.attendees
            schedule_url = f"{GRAPH_BASE}/users/{effective_user}/calendar/getSchedule"
            schedule_body = {
                "schedules": users_to_check,
                "startTime": {"dateTime": start_dt, "timeZone": "UTC"},
                "endTime": {"dateTime": end_dt, "timeZone": "UTC"},
                "availabilityViewInterval": 30,
            }

            async with httpx.AsyncClient(timeout=20.0) as client:
                sched_resp = await client.post(
                    schedule_url, headers=headers, json=schedule_body,
                )

            if sched_resp.status_code == 200:
                import pytz
                from dateutil import parser as dt_parser
                
                # Parse our requested window into aware UTC datetimes
                req_start_dt = dt_parser.parse(start_dt)
                if req_start_dt.tzinfo is None:
                    req_start_dt = req_start_dt.replace(tzinfo=pytz.utc)
                
                req_end_dt = dt_parser.parse(end_dt)
                if req_end_dt.tzinfo is None:
                    req_end_dt = req_end_dt.replace(tzinfo=pytz.utc)

                busy_users = []
                for schedule in sched_resp.json().get("value", []):
                    for item in schedule.get("scheduleItems", []):
                        if item.get("status") in ("busy", "oof", "tentative"):
                            # Parse Graph's busy block into aware UTC datetimes
                            item_start = dt_parser.parse(item["start"]["dateTime"])
                            if item_start.tzinfo is None:
                                item_start = item_start.replace(tzinfo=pytz.utc)
                                
                            item_end = dt_parser.parse(item["end"]["dateTime"])
                            if item_end.tzinfo is None:
                                item_end = item_end.replace(tzinfo=pytz.utc)
                                
                            # Check for time overlap
                            # Overlap occurs if (StartA < EndB) and (EndA > StartB)
                            if req_start_dt < item_end and req_end_dt > item_start:
                                busy_users.append(schedule.get("scheduleId"))
                                break  # Move to next schedule if this one is busy
                if busy_users:
                    users_str = ", ".join(busy_users)
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            f"The following attendees are busy during this time slot: "
                            f"{users_str}. Please pick a free slot."
                        ),
                    )
            else:
                raise HTTPException(
                    status_code=sched_resp.status_code,
                    detail=f"Availability check failed: {sched_resp.text}",
                )

        # ── Create the meeting using Calendar Events API ─────────────────────
        # Using /events with isOnlineMeeting instead of /onlineMeetings
        # because it requires Calendars.ReadWrite (which we know works)
        meeting_body: Dict[str, Any] = {
            "subject": req.subject,
            "start": {
                "dateTime": start_dt.replace("Z", ""),
                "timeZone": "UTC",
            },
            "end": {
                "dateTime": end_dt.replace("Z", ""),
                "timeZone": "UTC",
            },
            "isOnlineMeeting": True,
            "onlineMeetingProvider": "teamsForBusiness",
        }

        if req.attendees:
            meeting_body["attendees"] = [
                {
                    "emailAddress": {"address": email, "name": email},
                    "type": "required",
                }
                for email in req.attendees
            ]

        create_url = f"{GRAPH_BASE}/users/{effective_user}/events"
        
        print(f"--- GRAPH DEBUG ATTEMPT ---")
        print(f"URL: {create_url}")
        print(f"BODY: {meeting_body}")
        
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(create_url, headers=headers, json=meeting_body)

        if resp.status_code not in (200, 201):
            print(f"!!! GRAPH FAILED: {resp.status_code} - {resp.text}")
            raise HTTPException(
                status_code=resp.status_code,
                detail=(
                    f"Graph create-meeting failed ({resp.status_code}). "
                    f"Ensure you are using a FUTURE date. Details: {resp.text}"
                ),
            )

        graph_meeting = resp.json()
        join_url = (
            graph_meeting.get("onlineMeeting", {}).get("joinUrl")
            or graph_meeting.get("onlineMeetingUrl")
            or ""
        )

        # ── Persist meeting record in MongoDB ─────────────────────────────────
        record = MeetingRecord(
            meeting_id=graph_meeting.get("id", ""),
            organizer_id=req.user_id,
            subject=req.subject,
            start=start_dt,
            end=end_dt,
            attendees=req.attendees or [],
            join_url=join_url,
        )
        await meetings_col.insert_one(record.model_dump())

        return graph_meeting

    @classmethod
    async def list_meetings(cls, organizer_id: str, email: str = "") -> List[Dict[str, Any]]:
        """List stored meeting records for an organizer from MongoDB."""
        
        # Query for either the user's object ID (sub) or their email address
        # because the create endpoint might have saved it under req.user_id (which is usually the email)
        query_conditions = [{"organizer_id": organizer_id}]
        if email:
            query_conditions.append({"organizer_id": email})
            
        cursor = meetings_col.find(
            {"$or": query_conditions},
            {"_id": 0},
        ).sort("created_at", -1)
        return await cursor.to_list(length=100)
