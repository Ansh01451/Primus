from config import settings
import httpx
import asyncio

async def test_auth():
    url = f"https://login.microsoftonline.com/{settings.tenant_id}/oauth2/v2.0/token"
    print(f"Testing URL: {url}")
    print(f"Tenant ID: '{settings.tenant_id}'")
    
    payload = {
        "grant_type": "client_credentials",
        "client_id": settings.client_id,
        "client_secret": settings.client_secret,
        "scope": settings.scope
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            print("Sending request...")
            resp = await client.post(url, data=payload, headers=headers)
            print(f"Status Code: {resp.status_code}")
            print(f"Response: {resp.text[:100]}")
    except Exception as e:
        print(f"Caught exception: {type(e).__name__}: {e}")

if __name__ == "__main__":
    asyncio.run(test_auth())
