
import pymongo
from bson import ObjectId
import sys
import os

# Add the current directory to sys.path to import config
sys.path.append(os.getcwd())
from config import settings

def search():
    client = pymongo.MongoClient(settings.mongodb_uri)
    db = client[settings.mongodb_db_name]
    
    email = "vinay.saraswat@onmeridian.com"
    uid = "68ca986cefa4d83183ad817e"
    
    print(f"Searching for Email: {email}")
    print(f"Searching for ID: {uid}")
    
    collections = db.list_collection_names()
    for coll_name in collections:
        coll = db[coll_name]
        # Search by email
        res_email = list(coll.find({
            "$or": [
                {"email": {"$regex": f"^{email}$", "$options": "i"}},
                {"client_email": {"$regex": f"^{email}$", "$options": "i"}},
                {"vendor_email": {"$regex": f"^{email}$", "$options": "i"}}
            ]
        }))
        
        # Search by ID
        res_id = None
        try:
            res_id = coll.find_one({"_id": ObjectId(uid)})
        except:
            pass
            
        if res_email or res_id:
            print(f"\n--- MATCH IN COLLECTION: {coll_name} ---")
            if res_email:
                print(f"  Found by Email: {len(res_email)} docs")
            if res_id:
                print(f"  Found by ID: True")
                print(f"  Doc: {res_id}")
            elif res_email:
                for r in res_email:
                    print(f"  Doc: {r}")

if __name__ == "__main__":
    search()
