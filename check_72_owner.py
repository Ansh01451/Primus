import asyncio
import sys
import os

sys.path.append(os.getcwd())

from dynamics.services import get_access_token, fetch_dynamics

async def check_72_owner():
    try:
        token = await get_access_token()
        res = await fetch_dynamics("projectApiPage", token, "no eq 'PR-000072'")
        if res:
            p = res[0]
            print(f"Project: {p.get('no')}")
            print(f"Description: {p.get('description')}")
            print(f"Bill-to Customer No: {p.get('billToCustomerNo')}")
        else:
            print("Project PR-000072 not found in projectApiPage")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(check_72_owner())
