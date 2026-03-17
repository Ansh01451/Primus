import asyncio
import sys
import os
import json

sys.path.append(os.getcwd())

from dynamics.services import get_access_token, fetch_dynamics

async def debug_related_attachments():
    project_no = "123"
    try:
        token = await get_access_token()
        
        # 1. Check for attachments where No. starts with 123 (e.g., 123-Task01)
        print(f"Searching for attachments with No containing '{project_no}'...")
        filter_expr = f"contains(no, '{project_no}')"
        attachments = await fetch_dynamics("documentAttachmentApiPage", token, filter_expr)
        print(f"Attachments found: {len(attachments)}")
        for a in attachments:
            print(f"- TableID: {a.get('tableID')}, No: {a.get('no')}, File: {a.get('fileName')}")

        # 2. Check Job Tasks for project 123
        print(f"\nChecking Job Tasks for project '{project_no}'...")
        task_filter = f"jobNo eq '{project_no}'"
        tasks = await fetch_dynamics("projectTaskApiPage", token, task_filter)
        print(f"Tasks found: {len(tasks)}")
        for t in tasks:
            task_no = t.get('jobTaskNo')
            print(f"- Task No: {task_no}, Description: {t.get('description')}")
            # Check for attachments for this task (Table 1001)
            at_filter = f"tableID eq 1001 and no eq '{project_no}' and lineNo eq 0" # LineNo might be task no?
            # Actually, standard BC attachments for tasks might be tricky.
            # Usually Table 167 (Job) is used.

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(debug_related_attachments())
