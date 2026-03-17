import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from auth.middleware import JWTMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi.middleware.cors import CORSMiddleware
from auth.routes import router as auth_router
from dynamics.routes import router as dyn_router
from admin.routes import router as admin_router
from client.routes import router as client_router
from vendor.routes import router as vendor_router
from publications.routes import router as primus_router
from publications.services import load_data  # for scheduler prewarm/refresh
from notifications.routes import router as notifications_router
from meetings.routes import router as meetings_router

from admin.routes import AdminService

scheduler = AsyncIOScheduler()


async def _cron_fetch_unregistered():
    """
    Runs at midnight to sync unregistered clients from Dynamics.
    """
    # You could store last run timestamp in DB or cache
    # For now, fetch *all* new since yesterday midnight
    since = datetime.combine(datetime.now().date(), datetime.min.time())
    raw = await AdminService.fetch_dynamics_clients(since)
    AdminService.save_unregistered(raw)
    print(f"[Cron] Fetched and saved {len(raw)} unregistered clients")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Schedule your cron job at 00:00 UTC
    scheduler.add_job(
        lambda: asyncio.create_task(_cron_fetch_unregistered()),
        trigger="cron", hour=0, minute=0
    )

    # NEW: refresh Primus In-News cache every 30 minutes
    scheduler.add_job(
        lambda: asyncio.create_task(load_data(force=True)),
        trigger="interval", minutes=30
    )
 
    # Optional: prewarm cache at startup to avoid cold start on first request
    try:
        await load_data(force=True)
        print("[Startup] Primus In-News cache warmed")
    except Exception as e:
        print(f"[Startup] Primus In-News prewarm failed: {e}")

    scheduler.start()
    print("[Lifespan] Scheduler started")

    yield  # <-- App runs during this period

    scheduler.shutdown()
    print("[Lifespan] Scheduler shut down")

app = FastAPI(lifespan=lifespan)

def custom_openapi():
    print("--- [DEBUG] custom_openapi is being called! ---")
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="Primus Partners Portal API",
        version="1.0.0",
        description="Core API for Dynamics-linked portal",
        routes=app.routes,
    )
    # Patch for Swagger UI 5.x picker compatibility (FastAPI 0.129+)
    # It replaces 'contentMediaType: application/octet-stream' with 'format: binary'
    
    def patch_schema(s):
        if not isinstance(s, dict):
            return
        if s.get("type") == "string" and s.get("contentMediaType") == "application/octet-stream":
            s.pop("contentMediaType", None)
            s["format"] = "binary"
        elif s.get("type") == "array":
            items = s.get("items", {})
            if items.get("type") == "string" and items.get("contentMediaType") == "application/octet-stream":
                items.pop("contentMediaType", None)
                items["format"] = "binary"
        
        # Recurse into properties if object
        if s.get("type") == "object":
            for prop in s.get("properties", {}).values():
                patch_schema(prop)
        
    # Patch components/schemas
    for schema in openapi_schema.get("components", {}).get("schemas", {}).values():
        patch_schema(schema)

    # Patch paths
    for path in openapi_schema.get("paths", {}).values():
        for method_data in path.values():
            content = method_data.get("requestBody", {}).get("content", {})
            for media_type in content.values():
                schema = media_type.get("schema", {})
                patch_schema(schema)

    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi


# ✅ Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # your Vite/React frontend
        "http://localhost:5174",  # your Vite/React frontend
        "https://nkqlvm7w-8000.inc1.devtunnels.ms",  # backend tunnel (if frontend calls this)
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.add_middleware(JWTMiddleware)
app.include_router(auth_router)
app.include_router(dyn_router)
app.include_router(admin_router)
app.include_router(client_router)
app.include_router(vendor_router)
app.include_router(primus_router)
app.include_router(notifications_router)
app.include_router(meetings_router)
# app.include_router(alumni_router)