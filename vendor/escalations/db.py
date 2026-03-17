import os
from pydantic import GetCoreSchemaHandler
import pymongo
from bson import ObjectId
from fastapi import HTTPException, status
from config import settings
from pydantic_core import core_schema


vendor = pymongo.MongoClient(settings.mongodb_uri)
db = vendor[settings.mongodb_db_name]

escalations_col = db.get_collection("vendor_escalations")
registered_vendor_col = db.get_collection("registered_vendors")


class PyObjectId(ObjectId):
    @classmethod
    def __get_pydantic_core_schema__(cls, _source_type, _handler: GetCoreSchemaHandler):
        return core_schema.no_info_after_validator_function(cls.validate, core_schema.str_schema())

    @classmethod
    def validate(cls, v):
        try:
            return ObjectId(str(v))
        except Exception:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid ID")
    


