from datetime import datetime
from utils.log import logger
from typing import Dict, List
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from jwt import ExpiredSignatureError, InvalidTokenError
from .jwt_service import JWTService
from fastapi.exceptions import HTTPException as FastAPIHTTPException

bearer = HTTPBearer(auto_error=False)
jwt_service = JWTService()


class JWTMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        print(f"--- [DEBUG] JWTMiddleware processing {request.method} {request.url.path} ---")
        try:
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                try:
                    token = auth_header.split(" ")[1]
                    payload = jwt_service.verify_access_token(token)
                    request.state.user_id = payload.get("sub")
                    request.state.roles = payload.get("roles", [])
                    request.state.user_type = payload.get("type")
                    logger.debug(f"Authenticated request from user_id={request.state.user_id}")
                except FastAPIHTTPException as e:
                    logger.warning(f"Token verification failed: {e.detail}")
                    return JSONResponse(status_code=e.status_code, content={"detail": e.detail})
                except Exception as e:
                    logger.error(f"Unexpected token error: {e}")
                    return JSONResponse(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        content={"detail": "Error verifying access token"}
                    )
        except Exception as e:
            import traceback
            logger.critical(f"Auth Logic Exception: {e}\n{traceback.format_exc()}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Internal error in authentication logic"}
            )

        # Now call next outside the auth catch-all
        try:
            return await call_next(request)
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            print(f"!!! ROUTE CRASH DETECTED !!!\n{tb}")
            logger.critical(f"ROUTE CRASH: {e}\n{tb}")
            # Also write to a file for easy retrieval
            try:
                with open("crash_traceback.log", "a") as f:
                    f.write(f"\n--- CRASH AT {datetime.now()} ---\n{tb}\n")
            except Exception as log_err:
                print(f"Failed to write to crash_traceback.log: {log_err}")

            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Internal Server Error (Captured by Middleware)"}
            )


async def get_current_user(req: Request, creds=Depends(bearer)) -> Dict:
    if not creds:
        logger.info("Missing authentication credentials")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = jwt_service.verify_access_token(creds.credentials)
        req.state.user_id = payload.get("sub")
        req.state.roles = payload.get("roles", [])
        req.state.user_type = payload.get("type")
        req.state.user_email = payload.get("email")

        logger.debug(f"User authenticated: {req.state.user_id}")
        return payload
    except ExpiredSignatureError:
        logger.warning("Token expired during get_current_user")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except InvalidTokenError:
        logger.warning("Invalid token during get_current_user")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except Exception as e:
        logger.error(f"Token validation failed: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Token validation failed")


def require_roles(*allowed_roles: str):
    def dependency(payload=Depends(get_current_user)):
        try:
            roles: List[str] = payload.get("roles", [])
            if not any(r in roles for r in allowed_roles):
                logger.warning(f"User lacks required roles: {allowed_roles}, has roles: {roles}")
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient privileges")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error checking roles: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Role verification failed")
    return dependency
