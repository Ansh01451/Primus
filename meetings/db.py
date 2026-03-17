from motor.motor_asyncio import AsyncIOMotorClient
from config import settings

# Reuse the same MongoDB connection as other modules
_async_client = AsyncIOMotorClient(settings.mongodb_uri)
_async_db = _async_client[settings.mongodb_db_name]

# Collection to store meeting records
meetings_col = _async_db.get_collection("meetings")
