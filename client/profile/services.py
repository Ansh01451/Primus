from auth.db import collection_map
from .models import ClientProfileResponse, ClientProfileUpdate
from fastapi import HTTPException

def get_client_profile_service(email: str) -> ClientProfileResponse:
    client_col = collection_map.get("client")
    if client_col is None:
        raise HTTPException(status_code=500, detail="Database collection not found")
        
    client_data = client_col.find_one({"client_email": email})
    if not client_data:
        # Fallback to general email field just in case
        client_data = client_col.find_one({"email": email})
        if not client_data:
            raise HTTPException(status_code=404, detail="Client profile not found")
            
    # Map _id to client_id (string)
    client_data["client_id"] = str(client_data.get("_id", ""))
    
    # Ensure default fields exist to prevent Pydantic validation errors
    default_fields = {
        "address": "", "city": "", "phone": "", "state": "", 
        "zip_code": "", "company_name": "", "country": "", 
        "designation": "", "first_name": "", "last_name": "", 
        "middle_name": "", "gst_no": "", "project_id": [], "roles": []
    }
    
    for key, value in default_fields.items():
        if key not in client_data or client_data[key] is None:
            client_data[key] = value
            
    return ClientProfileResponse(**client_data)

def update_client_profile_service(email: str, update_data: ClientProfileUpdate) -> ClientProfileResponse:
    client_col = collection_map.get("client")
    if client_col is None:
        raise HTTPException(status_code=500, detail="Database collection not found")
        
    # Find existing user to ensure they exist
    client_data = client_col.find_one({"client_email": email}) or client_col.find_one({"email": email})
    if not client_data:
        raise HTTPException(status_code=404, detail="Client profile not found")

    # Filter out empty fields from update payload
    update_dict = {k: v for k, v in update_data.model_dump(exclude_unset=True).items() if v is not None}
    
    if update_dict:
        client_col.update_one(
            {"_id": client_data["_id"]},
            {"$set": update_dict}
        )
        
    # Return updated profile
    return get_client_profile_service(email)

