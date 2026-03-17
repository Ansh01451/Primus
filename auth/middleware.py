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
        try:
            creds: HTTPAuthorizationCredentials = await bearer(request)
            if creds:
                try:
                    payload = jwt_service.verify_access_token(creds.credentials)
                    request.state.user_id = payload.get("sub")
                    request.state.roles = payload.get("roles", [])
                    request.state.user_type = payload.get("type")
                    request.state.user_email = payload.get("email")
                    logger.debug(f"Authenticated request from user_id={request.state.user_id}")
                except FastAPIHTTPException as e:
                    # Let HTTPExceptions pass through untouched
                    logger.warning(f"Token verification failed: {e.detail}")
                    return JSONResponse(status_code=e.status_code, content={"detail": e.detail})
                except Exception as e:
                    logger.error(f"Unexpected token error: {e}")
                    return JSONResponse(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        content={"detail": "Error verifying access token"}
                    )
            return await call_next(request)
        except Exception as e:
            logger.critical(f"Unhandled middleware exception: {e}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Internal server error in authentication middleware"}
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
            # Normalize user roles to lowercase strings
            user_roles: List[str] = [str(r).lower() for r in payload.get("roles", [])]
            # Normalize allowed roles to lowercase strings
            allowed_roles_str = [(r.value if hasattr(r, 'value') else str(r)).lower() for r in allowed_roles]
            
            if not any(r in user_roles for r in allowed_roles_str):
                logger.warning(f"User {payload.get('email')} lacks required roles: {allowed_roles_str}, has roles: {user_roles}")
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient privileges")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error checking roles: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Role verification failed")
    return dependency
