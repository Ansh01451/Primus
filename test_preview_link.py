import asyncio
import sys
import os

# Add current directory to path so we can import dynamics.services
sys.path.append(os.getcwd())

from dynamics.services import get_onedrive_preview_url, get_onedrive_access_token
from config import settings

async def test_preview_link():
    file_name = "test.pdf" # Change to a real file name if known
    user_email = settings.onedrive_user_email
    
    try:
        print(f"Fetching preview link for '{file_name}' for user '{user_email}'...")
        token = await get_onedrive_access_token()
        url = await get_onedrive_preview_url(user_email, file_name, graph_token=token)
        print(f"Success! Preview URL: {url}")
    except Exception as e:
        print(f"Failed! {type(e).__name__}: {e}")
        # If it's a 404, it means the code worked but the file wasn't there
        if "404" in str(e):
             print("Note: 404 is expected if 'test.pdf' does not exist, but it confirms the Graph API search was called.")

if __name__ == "__main__":
    asyncio.run(test_preview_link())
