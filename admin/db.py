import os
from pydantic import GetCoreSchemaHandler
import pymongo
from bson import ObjectId
from fastapi import HTTPException, status
from config import settings
from pydantic_core import core_schema
from motor.motor_asyncio import AsyncIOMotorClient


# ── Async Motor client (for async route handlers) ────────────────────────────
async_client    = AsyncIOMotorClient(settings.mongodb_uri)
async_db        = async_client[settings.mongodb_db_name]

# Role-specific async collections
advisor_col     = async_db.get_collection("registered_advisors")
alumni_col      = async_db.get_collection("registered_alumnis")
vendor_col      = async_db.get_collection("registered_vendors")
client_col_async = async_db.get_collection("registered_clients")

collection_map_async = {
    "advisor": advisor_col,
    "alumni": alumni_col,
    "vendor": vendor_col,
    "client": client_col_async
}

# Escalation collections (async)
vendor_escalations_col_async = async_db.get_collection("vendor_escalations")
client_escalations_col_async = async_db.get_collection("client_escalations")

# Feedback collections (async)
vendor_feedback_col_async = async_db.get_collection("vendor_feedback")
client_feedback_col_async = async_db.get_collection("client_feedback")


onboarded_col   = async_db.get_collection("onboarded_users")   # legacy/deprecated
client          = async_client                                   # kept for back-compat


# ── Sync pymongo client (for sync def route handlers) ───────────────────────
sync_client     = pymongo.MongoClient(settings.mongodb_uri)
sync_db         = sync_client[settings.mongodb_db_name]

# Role-specific sync collections
advisor_col_sync = sync_db.get_collection("registered_advisors")
alumni_col_sync  = sync_db.get_collection("registered_alumnis")
vendor_col_sync  = sync_db.get_collection("registered_vendors")
client_col_sync  = sync_db.get_collection("registered_clients")

collection_map_sync = {
    "advisor": advisor_col_sync,
    "alumni": alumni_col_sync,
    "vendor": vendor_col_sync,
    "client": client_col_sync
}

unreg_col          = sync_db.get_collection("unregistered_clients")   # sync
reg_col            = sync_db.get_collection("registered_clients")      # sync
onboarded_col_sync = sync_db.get_collection("onboarded_users")         # legacy/deprecated
content_col_sync   = sync_db.get_collection("admin_content")           # sync
notifications_col_sync = sync_db.get_collection("admin_notifications")  # sync
alert_logs_col_sync    = sync_db.get_collection("admin_alert_logs")      # sync
surveys_col_sync       = sync_db.get_collection("admin_surveys")           # sync
survey_responses_col_sync = sync_db.get_collection("admin_survey_responses") # sync

content_col        = async_db.get_collection("admin_content")          # async
notifications_col  = async_db.get_collection("admin_notifications")    # async
activity_logs_col  = async_db.get_collection("activity_logs")          # async
surveys_col        = async_db.get_collection("admin_surveys")           # async
survey_responses_col = async_db.get_collection("admin_survey_responses") # async

# Escalation collections (sync)
vendor_escalations_col_sync = sync_db.get_collection("vendor_escalations")
client_escalations_col_sync = sync_db.get_collection("client_escalations")

# Feedback collections (sync)
vendor_feedback_col_sync = sync_db.get_collection("vendor_feedback")
client_feedback_col_sync = sync_db.get_collection("client_feedback")
activity_logs_col_sync = sync_db.get_collection("activity_logs")       # sync
surveys_col_sync        = sync_db.get_collection("admin_surveys")           # sync
survey_responses_col_sync = sync_db.get_collection("admin_survey_responses") # sync



class PyObjectId(ObjectId):
    @classmethod
    def __get_pydantic_core_schema__(cls, _source_type, _handler: GetCoreSchemaHandler):
        return core_schema.no_info_after_validator_function(cls.validate, core_schema.str_schema())

    @classmethod
    def validate(cls, v):
        if not v:
            return None
        try:
            return str(ObjectId(str(v)))
        except Exception:
            raise ValueError("Invalid ObjectId")

