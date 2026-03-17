import asyncio
import sys
import os
from collections import Counter

sys.path.append(os.getcwd())

from dynamics.services import get_access_token, fetch_dynamics

async def debug_all_project_attachments():
    try:
        token = await get_access_token()
        
        print("Fetching ALL attachments for Table 167 (Projects)...")
        attachments = await fetch_dynamics("documentAttachmentApiPage", token, "tableID eq 167")
        print(f"Total attachments found: {len(attachments)}")
        
        project_ids = [a.get('no') for a in attachments if a.get('no')]
        counts = Counter(project_ids)
        
        print("\nProjects with attachments (ID: Count):")
        for pid, count in counts.items():
            print(f"- '{pid}': {count}")
            
        print("\nChecking if any record contains '123' in any field...")
        for a in attachments:
            if any("123" in str(v) for v in a.values()):
                print(f"Match found in attachment: {a.get('fileName')} (No: {a.get('no')})")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(debug_all_project_attachments())
