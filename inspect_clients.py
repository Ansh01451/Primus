
import pymongo
from config import settings

client = pymongo.MongoClient(settings.mongodb_uri)
db = client[settings.mongodb_db_name]
registered_clients_col = db.get_collection("registered_clients")

print("--- REGISTERED CLIENTS ---")
for doc in registered_clients_col.find():
    print(doc)
print("--------------------------")
