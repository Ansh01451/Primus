from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from admin.services import LogService
from admin.models import ActivityLog
import time

class ActivityLoggerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        method = request.method
        
        # We process the response first to get the status code
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as e:
            # If an unhandled exception occurs, log it as 500
            status_code = 500
            # Re-raise so FastAPI handles it
            raise e
        finally:
            # Logic to log activity
            if path.startswith(("/api", "/admin", "/surveys", "/notifications", "/auth")):
                if not any(x in path for x in ["/docs", "/openapi.json", "/redoc", "/captcha-test"]):
                    
                    user_id = getattr(request.state, "user_id", None)
                    user_email = getattr(request.state, "user_email", None)
                    user_role = getattr(request.state, "user_type", None)
                    
                    # Determine "module" from path
                    module = path.split("/")[1] if len(path.split("/")) > 1 else "root"
                    
                    # Map path/method to human-readable action
                    action = LogService.get_action_description(method, path)
                    
                    # Add error indicator if needed
                    if status_code >= 400:
                        action = f"FAILED: {action}"

                    log_entry = ActivityLog(
                        user_id=str(user_id) if user_id else None,
                        user_email=user_email,
                        user_role=user_role,
                        action=action,
                        method=method,
                        path=path,
                        module=module.capitalize(),
                        status_code=status_code,
                        ip_address=request.client.host if request.client else None,
                        user_agent=request.headers.get("user-agent")
                    )
                    
                    # Background logging
                    try:
                        import asyncio
                        asyncio.create_task(LogService.create_log(log_entry))
                    except Exception as e:
                        print(f"Failed to log activity: {e}")
                        
        return response
