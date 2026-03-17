
import asyncio
from datetime import datetime, timedelta
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from meetings.services import MeetingService
from meetings.models import FreeSlotRequest, TimeSlot, MeetingCreateRequest

async def test_free_slots_weekend():
    print("Testing free slots weekend skip...")
    # Mock data
    range_start = datetime(2026, 3, 14, 9, 0, 0) # Saturday
    range_end = datetime(2026, 3, 15, 18, 0, 0) # Sunday
    interval = 30
    
    # _compute_free_windows is static
    free = MeetingService._compute_free_windows([], range_start, range_end, interval)
    print(f"Free slots found: {len(free)}")
    if len(free) == 0:
        print("SUCCESS: No free slots found on weekend.")
    else:
        print("FAILURE: Free slots found on weekend.")

async def test_create_meeting_weekend():
    print("\nTesting create meeting weekend block...")
    # Mock request for a Saturday
    req = MeetingCreateRequest(
        user_id="test@example.com",
        subject="Weekend Test",
        startDateTime="2026-03-14T10:00:00",
        endDateTime="2026-03-14T11:00:00",
        attendees=["user@example.com"]
    )
    
    try:
        # We don't need real token for the first check
        # But create_meeting calls _get_app_token() first.
        # I'll wrap the call to catch the HTTPException if it reaches the check.
        await MeetingService.create_meeting(req)
    except Exception as e:
        if "weekend" in str(e).lower():
            print(f"SUCCESS: Caught weekend error: {e}")
        else:
            print(f"FAILED to catch correct error: {e}")

if __name__ == "__main__":
    import sys
    import os
    # Add parent dir to path for imports if needed
    sys.path.append(os.getcwd())
    
    # Mock settings before importing services if necessary
    # But services imports config which imports settings.
    # I'll just run it and see.
    try:
        asyncio.run(test_free_slots_weekend())
        # create_meeting requires actual settings/token, let's just test the logic part
        asyncio.run(test_create_meeting_weekend())
    except Exception as e:
        print(f"Error during test: {e}")
            
