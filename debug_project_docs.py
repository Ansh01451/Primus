import asyncio
import sys
import os

sys.path.append(os.getcwd())

from dynamics.services import get_access_token, fetch_dynamics

async def debug_project_docs():
    project_no = "123"
    try:
        print(f"Checking if project '{project_no}' exists...")
        token = await get_access_token()
        
        # 1. Check project
        p_filter = f"no eq '{project_no}'"
        projects = await fetch_dynamics("projectApiPage", token, p_filter)
        print(f"Projects found: {len(projects)}")
        if projects:
            print(f"Project details: {projects[0]}")
        
        # 2. Check attachments
        a_filter = f"no eq '{project_no}'"
        print(f"Fetching attachments with filter: {a_filter}")
        attachments = await fetch_dynamics("documentAttachmentApiPage", token, a_filter)
        print(f"Attachments found: {len(attachments)}")
        for a in attachments:
            print(f"- {a.get('fileName')}.{a.get('fileExtension')} (ID: {a.get('id')})")

        # 3. Check ALL attachments (limit) to see if 'no' is the right field
        print("\nFetching first 5 attachments regardless of project...")
        all_attachments = await fetch_dynamics("documentAttachmentApiPage", token)
        for a in all_attachments[:5]:
             print(f"- No: {a.get('no')}, Name: {a.get('fileName')}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(debug_project_docs())
