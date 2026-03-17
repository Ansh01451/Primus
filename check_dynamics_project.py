
import asyncio
from dynamics.services import get_access_token, fetch_dynamics

async def check_project():
    token = await get_access_token()
    project_no = "PR00110"
    
    print(f"Checking project {project_no} in Dynamics...")
    filter_expr = f"no eq '{project_no}'"
    items = await fetch_dynamics("projectApiPage", token, filter_expr)
    
    if items:
        print(f"SUCCESS: Found project: {items[0].get('description')}")
    else:
        print(f"FAILED: Project {project_no} not found in Dynamics.")
        
        print("\nFetching first 5 available projects from Dynamics for reference:")
        all_projects = await fetch_dynamics("projectApiPage", token)
        if isinstance(all_projects, dict):
            all_projects = all_projects.get('value', [])
        
        for p in all_projects[:5]:
            print(f"- No: {p.get('no')}, Description: {p.get('description')}")

if __name__ == "__main__":
    asyncio.run(check_project())
