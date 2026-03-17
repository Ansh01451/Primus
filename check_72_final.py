import asyncio
import sys
import os

sys.path.append(os.getcwd())

from dynamics.services import get_access_token, fetch_dynamics

async def check_72_attachments():
    try:
        token = await get_access_token()
        for pid in ["PR-000072", "PP-72", "PR00072"]:
            print(f"Checking ID: '{pid}'")
            res = await fetch_dynamics("documentAttachmentApiPage", token, f"no eq '{pid}'")
            print(f"  Attachments found: {len(res)}")
            if res:
                print(f"  First file: {res[0].get('fileName')}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(check_72_attachments())
