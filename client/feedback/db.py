# admin/db.py (or wherever you create your Motor client)
from motor.motor_asyncio import AsyncIOMotorClient
from config import settings
from fastapi import HTTPException, status
from pydantic import GetCoreSchemaHandler
from bson import ObjectId
from pydantic_core import core_schema

client = AsyncIOMotorClient(settings.mongodb_uri)
db = client[settings.mongodb_db_name]

# existing collections
reg_col   = db.get_collection("registered_clients")

# new
feedback_col = db.get_collection("client_feedback")


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



