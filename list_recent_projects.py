import asyncio
import sys
import os

sys.path.append(os.getcwd())

from dynamics.services import get_access_token, fetch_dynamics

async def list_recent_projects():
    try:
        token = await get_access_token()
        
        print("Fetching most recent 10 projects...")
        # Order by systemCreatedAt desc
        projects = await fetch_dynamics("projectApiPage", token)
        # Sort manually since fetch_dynamics might not support orderby efficiently
        sorted_projects = sorted(projects, key=lambda x: x.get('systemCreatedAt', ''), reverse=True)
        
        for p in sorted_projects[:10]:
            print(f"- No: {p.get('no')}, Name: {p.get('description')}, Created: {p.get('systemCreatedAt')}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(list_recent_projects())
