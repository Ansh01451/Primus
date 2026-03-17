import asyncio
import sys
import os
import json

sys.path.append(os.getcwd())

from client.dashboard.services import get_document_attachments_for_project
from dynamics.services import get_access_token

async def test_service_id():
    # Use the exact ID I found earlier
    test_id = "PR-000072"
    print(f"Calling get_document_attachments_for_project('{test_id}')...")
    
    try:
        token = await get_access_token()
        results = await get_document_attachments_for_project(test_id, token=token)
        
        print(f"Results count: {len(results)}")
        if results:
            print("First item file_name:", results[0].get("file_name"))
            # Print the raw 'no' field from the first result
            print("Raw 'no' from Dynamics:", results[0].get("no"))
        else:
            print("No results returned for this ID.")
            
        # Try without the hyphen just in case
        alt_id = "PR00072"
        print(f"\nCalling get_document_attachments_for_project('{alt_id}')...")
        results_alt = await get_document_attachments_for_project(alt_id, token=token)
        print(f"Results count: {len(results_alt)}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_service_id())
