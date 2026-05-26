import asyncio
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response

from app.config import settings, logger
from app.db import init_db, get_recent_incidents
from app.docker_events import listen_to_docker_events
from app.events import register_sse_client, unregister_sse_client

# Background task reference to prevent garbage collection
_bg_tasks = set()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Initializing database...")
    await init_db()
    
    logger.info("Starting Docker event listener task...")
    task = asyncio.create_task(listen_to_docker_events())
    _bg_tasks.add(task)
    task.add_done_callback(_bg_tasks.discard)
    
    yield
    
    # Shutdown
    logger.info("Shutting down DocWatch V2...")
    task.cancel()

app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)

# Setup Templates and Static
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    incidents = await get_recent_incidents(limit=20)
    return templates.TemplateResponse(request=request, name="index.html", context={"incidents": incidents})


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
                # If client disconnects, request.is_disconnected() might be true, but it's checked slowly.
                # Wait for an incident
                incident = await q.get()
                
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
