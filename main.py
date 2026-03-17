# graph_teams.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import httpx
import os
import base64
import json
from typing import List, Optional
from config import settings

app = FastAPI(title="Graph Teams helper")

# ---------- CONFIG (you can also pass these in each request)
# set these as env vars or replace with values (not recommended for prod)
CLIENT_ID = settings.azure_client_id
CLIENT_SECRET = settings.azure_client_secret
TENANT_ID = settings.azure_tenant_id

GRAPH_TOKEN_URL = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
GRAPH_BASE = "https://graph.microsoft.com/v1.0"

# --------- Helpers

async def get_app_token(client_id: str, client_secret: str, tenant_id: str) -> dict:
    """
    Client credentials flow -> returns token response JSON.
    """
    token_url = GRAPH_TOKEN_URL.format(tenant=tenant_id)
    data = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
        # use .default to request all app permissions you've configured (and admin consented)
        "scope": "https://graph.microsoft.com/.default"
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.post(token_url, data=data)
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail=f"token request failed: {r.status_code} {r.text}")
    return r.json()

def decode_jwt_claims(token: str) -> dict:
    """
    Lightweight JWT payload decode (no verification) to inspect claims.
    Useful to check 'roles' (app permissions) or 'scp' (delegated scopes).
    """
    try:
        payload_b64 = token.split('.')[1]
        # add padding if needed
        rem = len(payload_b64) % 4
        if rem:
            payload_b64 += '=' * (4 - rem)
        payload_bytes = base64.urlsafe_b64decode(payload_b64.encode('utf-8'))
        return json.loads(payload_bytes)
    except Exception:
        return {}

# --------- Pydantic models

class MeetingCreate(BaseModel):
    user_id: str                    # object id or userPrincipalName (UPN) of organizer
    subject: str
    startDateTime: str              # ISO-8601, e.g. "2025-09-23T10:00:00Z"
    endDateTime: str                # ISO-8601
    attendees: Optional[List[str]] = None  # list of email addresses (optional)

# --------- Routes

@app.get("/token_info")
async def token_info():
    """
    Return token claims (roles/scp) so you can inspect whether the app token has application permissions.
    By default reads env vars; you can pass them in query params for quick testing.
    """
    client_id = CLIENT_ID
    client_secret = CLIENT_SECRET
    tenant_id = TENANT_ID
    if not (client_id and client_secret and tenant_id):
        raise HTTPException(status_code=400, detail="client_id, client_secret and tenant_id required (env or params)")
    token_resp = await get_app_token(client_id, client_secret, tenant_id)
    access_token = token_resp.get("access_token")
    if not access_token:
        raise HTTPException(status_code=502, detail="no access_token in token response")
    claims = decode_jwt_claims(access_token)
    # app-only tokens usually have 'roles' claim (list of app permissions). Delegated tokens have 'scp'.
    roles = claims.get("roles") or []
    scp = claims.get("scp")
    return {
        "access_token_claims_preview": claims,
        "roles": roles,
        "scp": scp,
        "note": "If 'roles' contains OnlineMeetings.ReadWrite.All then the app token has that application permission. Delegated scopes appear in 'scp'."
    }

@app.get("/meetings/{user_id}")
async def list_online_meetings(user_id: str,
                               top: int = 50):
    """
    List online (Teams) meetings from the user's calendar events.
    This endpoint uses app-only token (client credentials). For app-only token to read user calendars,
    you need Calendar permissions (e.g. Calendars.Read, Calendars.ReadWrite as app permissions) and admin consent.
    Alternatively use delegated token (not shown here) if you want user-level access.
    """
    client_id = CLIENT_ID
    client_secret = CLIENT_SECRET
    tenant_id = TENANT_ID
    if not (client_id and client_secret and tenant_id):
        raise HTTPException(status_code=400, detail="client_id, client_secret and tenant_id required (env or params)")

    token_resp = await get_app_token(client_id, client_secret, tenant_id)
    token = token_resp["access_token"]

    # Use events endpoint and filter online meetings (calendar-backed). You can also use /users/{id}/onlineMeetings to read meetings created via the OnlineMeeting API.
    url = f"{GRAPH_BASE}/users/{user_id}/events"
    params = {
        "$filter": "isOnlineMeeting eq true",
        "$top": str(top),
        "$orderby": "start/dateTime desc"
    }

    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.get(url, headers=headers, params=params)
    if r.status_code != 200:
        raise HTTPException(status_code=r.status_code, detail=f"graph error: {r.text}")
    return r.json()

@app.post("/meetings/create")
async def create_online_meeting(req: MeetingCreate):
    """
    Create a Teams online meeting for the specified user.
    If you call POST /users/{userId}/onlineMeetings using an app-only token, your app must have OnlineMeetings.ReadWrite.All
    and tenant admin must configure an application access policy if needed. If you instead call /me/onlineMeetings you must
    use a delegated token (not shown).
    """
    client_id = CLIENT_ID
    client_secret = CLIENT_SECRET
    tenant_id = TENANT_ID
    if not (client_id and client_secret and tenant_id):
        raise HTTPException(status_code=400, detail="client_id, client_secret and tenant_id required (env or params)")

    token_resp = await get_app_token(client_id, client_secret, tenant_id)
    token = token_resp["access_token"]

    # Build request body
    body = {
        "startDateTime": req.startDateTime,
        "endDateTime": req.endDateTime,
        "subject": req.subject
    }

    # If attendees provided, add to participants
    if req.attendees:
        participants = {"attendees": []}
        for email in req.attendees:
            participants["attendees"].append({
                "identity": {
                    "user": {
                        "id": None,
                        "displayName": None,
                        "userPrincipalName": email
                    }
                },
                "upn": email,
                "role": "attendee"
            })
        # OnlineMeeting expects participants.organizer/attendees structure; put attendees under "participants".
        body["participants"] = participants

    url = f"{GRAPH_BASE}/users/{req.user_id}/onlineMeetings"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.post(url, headers=headers, json=body)

    if r.status_code not in (200, 201):
        # 403 likely means permission or application access policy not configured
        raise HTTPException(status_code=r.status_code, detail=f"graph error: {r.text}")

    return r.json()
