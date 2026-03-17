import asyncio
import sys
import os
import json

sys.path.append(os.getcwd())

from dynamics.services import get_access_token, fetch_dynamics

async def debug_project_attachments():
    project_no = "123"
    try:
        token = await get_access_token()
        
        # Filter by both TableID (167 for Project) and No.
        filter_expr = f"tableID eq 167 and no eq '{project_no}'"
        print(f"Fetching project attachments with filter: {filter_expr}")
        
        attachments = await fetch_dynamics("documentAttachmentApiPage", token, filter_expr)
        print(f"Attachments found: {len(attachments)}")
        for a in attachments:
            print(json.dumps(a, indent=2))

        # Also check WITHOUT no filter but WITH tableID=167 to see what projects HAVE attachments
        print("\nChecking ALL project attachments (tableID=167)...")
        proj_attachments = await fetch_dynamics("documentAttachmentApiPage", token, "tableID eq 167")
        print(f"Total project attachments found: {len(proj_attachments)}")
        for a in proj_attachments[:10]:
            print(f"- Project No: {a.get('no')}, File: {a.get('fileName')}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(debug_project_attachments())
