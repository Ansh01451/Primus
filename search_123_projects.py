import asyncio
import sys
import os

sys.path.append(os.getcwd())

from dynamics.services import get_access_token, fetch_dynamics

async def search_for_123_projects():
    try:
        token = await get_access_token()
        
        print("Searching for projects where 'no' contains '123'...")
        # contains(no, '123')
        filter_expr = "contains(no, '123')"
        projects = await fetch_dynamics("projectApiPage", token, filter_expr)
        
        print(f"Projects found: {len(projects)}")
        for p in projects:
            print(f"- No: {p.get('no')}, Name: {p.get('description')}")
            
        print("\nSearching for projects where 'description' contains '123'...")
        filter_expr2 = "contains(description, '123')"
        projects2 = await fetch_dynamics("projectApiPage", token, filter_expr2)
        for p in projects2:
            print(f"- No: {p.get('no')}, Name: {p.get('description')}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(search_for_123_projects())
