import asyncio
import sys
import os
import json

sys.path.append(os.getcwd())

from dynamics.services import get_access_token, fetch_dynamics

async def debug_task_attachments():
    project_no = "123"
    try:
        token = await get_access_token()
        
        print(f"Searching for ALL attachments in Table 1001 (Project Task)...")
        task_attachments = await fetch_dynamics("documentAttachmentApiPage", token, "tableID eq 1001")
        print(f"Total task attachments found: {len(task_attachments)}")
        
        for a in task_attachments:
            print(f"- No: {a.get('no')}, File: {a.get('fileName')}")
            if project_no in a.get('no', ''):
                print(f"  *** MATCH FOUND for project {project_no}! ***")

        print(f"\nSearching for attachments where 'no' starts with '{project_no}' in ANY table...")
        all_matches = await fetch_dynamics("documentAttachmentApiPage", token, f"startswith(no, '{project_no}')")
        for m in all_matches:
            print(f"- No: {m.get('no')}, Table: {m.get('tableID')}, File: {m.get('fileName')}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(debug_task_attachments())
