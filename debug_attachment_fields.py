import asyncio
import sys
import os
import json

sys.path.append(os.getcwd())

from dynamics.services import get_access_token, fetch_dynamics

async def debug_attachment_fields():
    try:
        token = await get_access_token()
        
        print("Fetching first 3 attachments with full details...")
        # fetch_dynamics returns a list of results
        all_attachments = await fetch_dynamics("documentAttachmentApiPage", token)
        
        if all_attachments:
            for idx, a in enumerate(all_attachments[:3]):
                print(f"\nAttachment {idx+1}:")
                print(json.dumps(a, indent=2))
        else:
            print("No attachments found at all.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(debug_attachment_fields())
