import asyncio
import sys
import os

sys.path.append(os.getcwd())

from dynamics.services import get_access_token, fetch_dynamics

async def search_72():
    try:
        token = await get_access_token()
        print("Searching for projects where 'no' contains '72'...")
        filter_expr = "contains(no, '72')"
        projects = await fetch_dynamics("projectApiPage", token, filter_expr)
        
        for p in projects:
            print(f"- No: {p.get('no')}, Name: {p.get('description')}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(search_72())
