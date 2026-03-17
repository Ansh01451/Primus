import httpx
from fastapi import HTTPException, status
from config import settings



async def verify_captcha(token: str) -> None:
    url = "https://www.google.com/recaptcha/api/siteverify"
    data = {
        "secret": settings.captcha_secret_key,
        "response": token,
    }
    async with httpx.AsyncClient() as client:
        r = await client.post(url, data=data, timeout=5.0)
    payload = r.json()
    print("reCAPTCHA payload:", payload)       # 🔍 inspect this in your logs

    if not payload.get("success"):
        # Show the specific error codes
        errs = payload.get("error-codes", [])
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Captcha verification failed: {errs}"
        )


    