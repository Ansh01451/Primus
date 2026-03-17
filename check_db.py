
import sys
import os

# Add the current directory to sys.path to import config
sys.path.append(os.getcwd())

from config import settings
import pymongo

def check():
    print(f"Connecting to: {settings.mongodb_uri}")
    print(f"Database: {settings.mongodb_db_name}")
    
    client = pymongo.MongoClient(settings.mongodb_uri)
    db = client[settings.mongodb_db_name]
    coll = db.get_collection("client_escalations")
    
    email = "vinay.saraswat@onmeridian.com"
    query = {"client_email": {"$regex": f"^{email}$", "$options": "i"}}
    
    print(f"Query: {query}")
    results = list(coll.find(query))
    print(f"Results found: {len(results)}")
    for r in results:
        print(f" - {r.get('short_id')}: {r.get('subject')} (Project: {r.get('project_id')})")

    # Also check without regex just in case
    print("\nChecking exact match:")
    query_exact = {"client_email": email}
    results_exact = list(coll.find(query_exact))
    print(f"Results found (exact): {len(results_exact)}")

if __name__ == "__main__":
    check()
