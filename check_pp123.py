import asyncio
import sys
import os

sys.path.append(os.getcwd())

from dynamics.services import get_access_token, fetch_dynamics

async def check_pp123_attachments():
    project_no = "PP-123"
    try:
        token = await get_access_token()
        
        print(f"Checking attachments for project '{project_no}'...")
        filter_expr = f"no eq '{project_no}'"
        attachments = await fetch_dynamics("documentAttachmentApiPage", token, filter_expr)
        
        print(f"Attachments found: {len(attachments)}")
        for a in attachments:
            print(f"- File: {a.get('fileName')}, TableID: {a.get('tableID')}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(check_pp123_attachments())
