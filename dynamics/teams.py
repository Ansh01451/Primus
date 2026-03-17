import calendar
from zoneinfo import ZoneInfo
from fastapi import FastAPI, HTTPException
import jwt
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from azure.identity import ClientSecretCredential
from config import settings
import requests
import pytz
 
 
load_dotenv()
TENANT_ID = settings.azure_tenant_id
CLIENT_ID = settings.azure_client_id  
CLIENT_SECRET = settings.azure_client_secret
SCOPES = ["https://graph.microsoft.com/.default"]
# Initialize clients
credential = ClientSecretCredential(TENANT_ID, CLIENT_ID, CLIENT_SECRET)
 
# Decode without verifying signature (just to inspect claims)
 

def get_graph_token():
    token = credential.get_token(*SCOPES)
    return token.token


def fetch_user_meetings(user_email: str, scope: str = "week"):
    """
    Fetch Teams online meetings for the current week or month for a given user.
    """
    now = datetime.now()
    if scope == "day":
        # Start and end of today
        dt_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        dt_end = now.replace(hour=23, minute=59, second=59, microsecond=0)
    elif scope == "week":
        start_of_week = now - timedelta(days=now.weekday    ())
        end_of_week = start_of_week + timedelta(days=6, hours=23, minutes=59, seconds=59)
        dt_start, dt_end = start_of_week, end_of_week
    elif scope == "month":
        dt_start = now.replace(day=1)
        last_day = calendar.monthrange(now.year, now.month)[1]
        dt_end = now.replace(day=last_day, hour=23, minute=59, second=59)
    else:
        raise ValueError("Invalid scope. Use 'week' or 'month'.")
 
    token = get_graph_token()
    url = (
        f"https://graph.microsoft.com/v1.0/users/{user_email}/calendarView"
        f"?startDateTime={dt_start.isoformat()}Z&endDateTime={dt_end.isoformat()}Z"
    )
    headers = {"Authorization": f"Bearer {token}", "Prefer": 'outlook.timezone="India Standard Time"'}
 
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        raise Exception(f"Graph API error {resp.status_code}: {resp.text}")
    
    # print("Response:", resp.json())
 
    events = resp.json().get("value", [])
    meetings = []
 
    for e in events:
        if not e.get("isOnlineMeeting"):
            continue

        attendees = [
            {
                "email": a["emailAddress"]["address"],
                "name": a["emailAddress"].get("name"),
                "type": a.get("type"),  # required / optional / resource
                "status": a.get("status", {}).get("response")
            }
            for a in e.get("attendees", [])
        ]

        meeting = {
            "id": e["id"],
            "subject": e.get("subject"),
            "start": datetime.fromisoformat(e["start"]["dateTime"]),
            "end": datetime.fromisoformat(e["end"]["dateTime"]),
            "duration_minutes": (
                datetime.fromisoformat(e["end"]["dateTime"]) - datetime.fromisoformat(e["start"]["dateTime"])
            ).total_seconds() / 60,
            "joinUrl": e.get("onlineMeeting", {}).get("joinUrl"),
            "location": e.get("location", {}).get("displayName"),
            "attendees": attendees
        }

        # print("Meetind duration (mins):", meeting["duration_minutes"])
        meetings.append(meeting)
 
    return meetings
 

def schedule_meeting(
    organizer_email: str,
    client_emails: list[str],
    subject: str,
    description: str,
    start_time: datetime,
    end_time: datetime
):
    token = get_graph_token()
    url = f"https://graph.microsoft.com/v1.0/users/{organizer_email}/events"
 
    # 🔹 Ensure datetimes are timezone-aware (IST)
    ist = pytz.timezone("Asia/Kolkata")
    if start_time.tzinfo is None:
        start_time = ist.localize(start_time)
    else:
        start_time = start_time.astimezone(ist)
 
    if end_time.tzinfo is None:
        end_time = ist.localize(end_time)
    else:
        end_time = end_time.astimezone(ist)

    attendees = [
        {
            "emailAddress": {
                "address": email,
                "name": email.split("@")[0]
            },
            "type": "required"
        }
        for email in client_emails
    ]
 
    meeting_data = {
        "subject": subject,
        "body": {
            "contentType": "HTML",
            "content": description or f"Meeting scheduled with {', '.join(client_emails)}"
        },
        "start": {
            "dateTime": start_time.strftime("%Y-%m-%dT%H:%M:%S"),
            "timeZone": "India Standard Time"  # ✅ correct for MS Graph
        },
        "end": {
            "dateTime": end_time.strftime("%Y-%m-%dT%H:%M:%S"),
            "timeZone": "India Standard Time"
        },
        "location": {
            "displayName": "Microsoft Teams Meeting"
        },
        "attendees": attendees,
        "isOnlineMeeting": True,
        "onlineMeetingProvider": "teamsForBusiness"
    }
 
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
 
    print("➡️ Posting to:", url)
    print("➡️ Headers:", headers)
    print("➡️ Body:", meeting_data)
 
    resp = requests.post(url, headers=headers, json=meeting_data)
 
    print("⬅️ Response code:", resp.status_code)
    print("⬅️ Response body:", resp.text)
 
    if resp.status_code not in (200, 201):
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
 
    return resp.json()
 
 
def cancel_meeting(
    organizer_email: str,
    meeting_id: str,
    cancellation_message: str = "The meeting has been cancelled."
):
    """
    Cancel a scheduled Teams meeting.
    Sends a cancellation message to attendees.
    """
    token = get_graph_token()
    url = f"https://graph.microsoft.com/v1.0/users/{organizer_email}/events/{meeting_id}/cancel"
 
    body = {
        "comment": cancellation_message
    }
 
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
 
    print("➡️ Posting to:", url)
    print("➡️ Headers:", headers)
    print("➡️ Body:", body)
 
    resp = requests.post(url, headers=headers, json=body)
 
    print("⬅️ Response code:", resp.status_code)
    print("⬅️ Response body:", resp.text)
 
    if resp.status_code not in (202, 204):  # cancel returns 202 Accepted
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
 
    return {"status": "cancelled", "meetingId": meeting_id}