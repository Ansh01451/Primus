import asyncio
import sys
import os

# Add current directory to path so we can import dynamics.services
sys.path.append(os.getcwd())

from dynamics.services import get_access_token

async def test_real_function():
    try:
        print("Calling get_access_token()...")
        token = await get_access_token()
        print(f"Success! Token starts with: {token[:20]}...")
    except Exception as e:
        print(f"Failed! {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_real_function())
