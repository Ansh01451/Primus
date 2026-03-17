import asyncio
import sys
import os

sys.path.append(os.getcwd())

from dynamics.services import get_access_token, fetch_dynamics
from client.dashboard.services import get_projects

async def check_client_projects():
    client_ids = ["CL1001", "CL1002", "CL1003", "CL1011", "CL1015", "C000001"]
    
    try:
        token = await get_access_token()
        
        for cid in client_ids:
            print(f"\nChecking projects for Client ID: {cid}")
            filter_expr = f"billToCustomerNo eq '{cid}'"
            projects = await get_projects(token=token, filter_expr=filter_expr)
            print(f"Total projects found: {len(projects)}")
            for p in projects:
                p_no = p.get('no')
                print(f"- Project No: {p_no}, Name: {p.get('description')}")
                
                # If this is PR-000072, specifically check it
                if p_no == "PR-000072":
                    print("  !!! Found PR-000072 linked to this client !!!")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(check_client_projects())
