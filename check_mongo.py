import asyncio
import sys
import os
from motor.motor_asyncio import AsyncIOMotorClient

# Mock settings/config
sys.path.append(os.getcwd())
from config import settings

async def check_mongo_client():
    client = AsyncIOMotorClient(settings.mongodb_uri)
    db = client[settings.mongodb_db_name]
    coll = db["registered_clients"]
    
    print(f"Connecting to MongoDB: {settings.mongodb_uri}")
    print(f"Database: {settings.mongodb_db_name}")
    
    # Let's find all clients to see who we are dealing with
    async for doc in coll.find({}):
        print(f"Client: {doc.get('client_name')}, Email: {doc.get('client_email')}, ID: {doc.get('client_id')}")

if __name__ == "__main__":
    asyncio.run(check_mongo_client())
