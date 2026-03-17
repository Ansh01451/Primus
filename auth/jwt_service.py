import time
from typing import List, Any, Dict
import jwt
from jwt import PyJWTError
from fastapi import HTTPException, status
from config import settings


class JWTService:
    def create_access_token(self, subject: str, roles: List[str], user_type: str, email: str) -> str:
        now = int(time.time())
        payload: Dict[str, Any] = {
            "sub": subject, 
            "roles": roles,
            "type": user_type,
            "email": email,
            "iat": now, 
            "exp": now + settings.access_token_expires}
        return jwt.encode(payload, settings.secret_key, algorithm="HS256")


    def create_refresh_token(self, subject: str, roles: List[str], user_type: str) -> str:
        now = int(time.time())
        payload: Dict[str, Any] = {
            "sub": subject, 
            "roles": roles,
            "type": user_type,
            "iat": now, 
            "exp": now + settings.refresh_token_expires}
        return jwt.encode(payload, settings.secret_key, algorithm="HS256")


    def verify_refresh_token(self, token: str) -> Dict[str, Any]:
        try:
            return jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        except PyJWTError:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")


    def verify_access_token(self, token: str) -> Dict[str, Any]:
        try:
            return jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        except PyJWTError:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token")






