import os
import pymongo
from bson import ObjectId
from fastapi import HTTPException, status
from config import settings


# MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
client = pymongo.MongoClient(settings.mongodb_uri)
db = client[settings.mongodb_db_name]

collection_map = {
    "admin": db.get_collection("admins"),
    "advisor": db.get_collection("registered_advisors"),
    "alumni": db.get_collection("registered_alumnis"),
    "vendor": db.get_collection("registered_vendors"),
    "client": db.get_collection("registered_clients")
}

email_field_map = {
    "admin": "admin_email",
    "advisor": "advisor_email",
    "alumni": "alumni_email",
    "vendor": "vendor_email",
    "client": "client_email",
}

name_field_map = {
    "admin": "admin_name",
    "advisor": "advisor_name",
    "alumni": "alumni_name",
    "vendor": "vendor_name",
    "client": "client_name",
}

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





