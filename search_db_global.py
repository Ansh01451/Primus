
import pymongo
import sys
import os

# Add current directory to sys.path
sys.path.append(os.getcwd())
from config import settings

def search_vinay():
    client = pymongo.MongoClient(settings.mongodb_uri)
    db = client[settings.mongodb_db_name]
    email = "vinay.saraswat@onmeridian.com"
    
    print(f"Searching for {email} in database: {settings.mongodb_db_name}")
    
    collections = db.list_collection_names()
    for coll_name in collections:
        coll = db[coll_name]
        try:
            # Search in common email fields
            query = {
                "$or": [
                    {"email": email},
                    {"client_email": email},
                    {"vendor_email": email},
                    {"advisor_email": email},
                    {"admin_email": email},
                    {"alumni_email": email},
                    {"user_email": email}
                ]
            }
            results = list(coll.find(query))
            if results:
                print(f"\n--- Found in collection: {coll_name} ---")
                for r in results:
                    # Clean up ObjectId and other bson types for printing
                    r_str = {k: str(v) for k, v in r.items()}
                    print(r_str)
        except Exception as e:
            # Some collections might not support this or have indexing issues
            pass

if __name__ == "__main__":
    search_vinay()
