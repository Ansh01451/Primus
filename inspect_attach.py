import asyncio
import sys
import os
import json

sys.path.append(os.getcwd())

from dynamics.services import get_access_token, fetch_dynamics

async def inspect_attachment_fields():
    try:
        token = await get_access_token()
        # Fetch one attachment to see fields
        res = await fetch_dynamics("documentAttachmentApiPage", token)
        if res:
            print(json.dumps(res[0], indent=2))
        else:
            print("No attachments found.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(inspect_attachment_fields())
