import asyncio
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse

from app.config import settings, logger
from app.db import init_db, get_recent_incidents, get_incident_by_id
from app.docker_events import listen_to_docker_events
from app.events import register_sse_client, unregister_sse_client
from app.remediation import execute_docker_fix
from app.tasks import create_background_task, cancel_all_tasks

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Initializing database...")
    await init_db()
    
    logger.info("Starting Docker event listener task...")
    create_background_task(listen_to_docker_events(), name="docker_event_listener")
    
    yield
    
    # Shutdown
    logger.info("Shutting down DocWatch V2...")
    cancel_all_tasks()

app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)

# Global Error Handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception during {request.method} {request.url.path}: {str(exc)}")
    # Log the traceback in development, hide it in production. Here we just return a generic error.
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error"}
    )

# Security Headers Middleware
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

app.add_middleware(SecurityHeadersMiddleware)

# Setup Templates and Static
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    incidents = await get_recent_incidents(limit=20)
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"incidents": incidents}
    )


@app.get("/metrics")
async def metrics():
    data = generate_latest()
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)


@app.get("/stream")
async def stream_incidents(request: Request):
    """
    SSE Endpoint for real-time dashboard updates via HTMX.
    """
    async def event_generator():
        q = register_sse_client()
        try:
            while True:
                if await request.is_disconnected():
                    break

                try:
                    # Wait for an incident with a short timeout to periodically check disconnect status
                    incident = await asyncio.wait_for(q.get(), timeout=2.0)
                except asyncio.TimeoutError:
                    continue
                
                # Render the incident row using Jinja2
                html = templates.get_template("components/incident_card.html").render(
                    {"incident": incident}
                )
                
                # Yield SSE format
                # We use HTMX SSE swap, so we just yield data
                # Replace newlines in html to avoid SSE parsing issues, or just send it raw as data block
                yield f"event: new_incident\ndata: {html.replace(chr(10), '')}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            unregister_sse_client(q)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/api/incidents/{incident_id}/execute-fix", response_class=HTMLResponse)
async def execute_fix_endpoint(incident_id: int):
    incident = await get_incident_by_id(incident_id)
    if not incident or not incident.suggested_fix:
        return "<span class='px-2 py-1 bg-red-500/10 text-red-400 border border-red-500/20 rounded text-xs'>❌ No fix found</span>"

    success, msg = await execute_docker_fix(incident.suggested_fix)
    
    if success:
        return f"<span class='px-2 py-1 bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 rounded text-xs flex items-center space-x-1'><svg class='w-3.5 h-3.5' fill='none' stroke='currentColor' viewBox='0 0 24 24'><path stroke-linecap='round' stroke-linejoin='round' stroke-width='2' d='M5 13l4 4L19 7'></path></svg><span>Fix Applied</span></span>"
    else:
        # truncate msg
        short_msg = msg[:40] + "..." if len(msg) > 40 else msg
        return f"<span class='px-2 py-1 bg-red-500/10 text-red-400 border border-red-500/20 rounded text-xs flex items-center space-x-1' title='{msg}'><svg class='w-3.5 h-3.5' fill='none' stroke='currentColor' viewBox='0 0 24 24'><path stroke-linecap='round' stroke-linejoin='round' stroke-width='2' d='M6 18L18 6M6 6l12 12'></path></svg><span>Failed: {short_msg}</span></span>"
