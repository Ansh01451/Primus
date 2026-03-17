"""
Notification routes — accessible to ALL authenticated portal users (vendor, client, alumni, advisor).
The admin creates notifications by publishing content; users fetch/mark-read here.
"""
from datetime import datetime
from typing import Optional
from bson import ObjectId as BsonObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from auth.middleware import get_current_user
from admin.db import notifications_col_sync, content_col_sync

router = APIRouter(prefix="/notifications", tags=["Notifications"])


def _s(doc: dict) -> dict:
    doc["_id"] = str(doc["_id"])
    if "created_at" in doc and doc["created_at"]:
        doc["created_at"] = doc["created_at"].isoformat()
    return doc


# ── GET  /notifications  ─────────────────────────────────────────────────────
@router.get("", summary="List notifications for the current user", status_code=status.HTTP_200_OK)
def list_notifications(
    request: Request,
    _=Depends(get_current_user),
    unread_only: bool = Query(False),
    page: int = Query(1, ge=1),
    size: int = Query(30, ge=1, le=100),
):
    user_id = str(request.state.user_id)
    query: dict = {"user_id": user_id}
    if unread_only:
        query["is_read"] = False

    skip  = (page - 1) * size
    total = notifications_col_sync.count_documents(query)
    unread_count = notifications_col_sync.count_documents({"user_id": user_id, "is_read": False})

    cursor = notifications_col_sync.find(query).sort("created_at", -1).skip(skip).limit(size)
    items  = [_s(d) for d in cursor]
    return {"total": total, "unread_count": unread_count, "page": page, "items": items}


# ── PATCH /notifications/{id}/read  ─────────────────────────────────────────
@router.patch("/{notification_id}/read", summary="Mark a notification as read", status_code=status.HTTP_200_OK)
def mark_read(
    notification_id: str,
    request: Request,
    _=Depends(get_current_user),
):
    user_id = str(request.state.user_id)
    try:
        oid = BsonObjectId(notification_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid notification ID")

    result = notifications_col_sync.update_one(
        {"_id": oid, "user_id": user_id},
        {"$set": {"is_read": True}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"notification_id": notification_id, "is_read": True}


# ── PATCH /notifications/read-all  ──────────────────────────────────────────
@router.patch("/read-all", summary="Mark ALL notifications as read", status_code=status.HTTP_200_OK)
def mark_all_read(
    request: Request,
    _=Depends(get_current_user),
):
    user_id = str(request.state.user_id)
    notifications_col_sync.update_many(
        {"user_id": user_id, "is_read": False},
        {"$set": {"is_read": True}}
    )
    return {"message": "All notifications marked as read"}


# ── GET /notifications/content/{content_id}  ─────────────────────────────────
@router.get("/content/{content_id}", summary="View a content item (for notification click)", status_code=status.HTTP_200_OK)
def view_content(
    content_id: str,
    request: Request,
    _=Depends(get_current_user),
):
    """Allows portal users to read the content attached to a notification."""
    user_id = str(request.state.user_id)
    roles   = getattr(request.state, "roles", [])

    try:
        oid = BsonObjectId(content_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid content ID")

    doc = content_col_sync.find_one({"_id": oid, "is_published": True})
    if not doc:
        raise HTTPException(status_code=404, detail="Content not found")

    # Check visibility — if it targets specific roles, ensure user has one of them
    visibility = doc.get("visibility", ["all"])
    if "all" not in visibility:
        if not any(r in visibility for r in roles):
            raise HTTPException(status_code=403, detail="You do not have permission to view this content")

    # Auto mark the notification for this content as read for this user
    notifications_col_sync.update_many(
        {"user_id": user_id, "content_id": content_id, "is_read": False},
        {"$set": {"is_read": True}}
    )

    doc["_id"] = str(doc["_id"])
    if "created_at" in doc and doc["created_at"]:
        doc["created_at"] = doc["created_at"].isoformat()
    if "scheduled_at" in doc and doc["scheduled_at"]:
        doc["scheduled_at"] = doc["scheduled_at"].isoformat()
    return doc
