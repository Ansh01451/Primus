# admin/db.py (or wherever you create your Motor vendor)
from motor.motor_asyncio import AsyncIOMotorClient
from config import settings
from fastapi import HTTPException, status
from pydantic import GetCoreSchemaHandler
from bson import ObjectId
from pydantic_core import core_schema

vendor = AsyncIOMotorClient(settings.mongodb_uri)
db = vendor[settings.mongodb_db_name]

# existing collections
registered_vendor_col = db.get_collection("registered_vendors")

# new
feedback_col = db.get_collection("vendor_feedback")


class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        try:
            return ObjectId(str(v))
        except Exception:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid ID")



