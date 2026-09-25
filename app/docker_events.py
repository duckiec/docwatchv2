import asyncio
import json
import time
from typing import Dict, Any
import aiodocker

from app.config import settings, logger
from app.db import Incident, save_incident
from app.ai_client import classify_crash
from app.security import mask_sensitive_env_vars
from app.alert_dispatcher import dispatch_webhook
from app.metrics import CRASH_COUNT, AI_LATENCY, MONITORED_CONTAINERS

# Dictionary to track last crash time for debouncing
# Format: { "container_name": last_crash_timestamp_float }
_crash_debouncer: Dict[str, float] = {}

async def handle_crash_event(container_id: str, docker: aiodocker.Docker):
    """
    Handle a container crash event asynchronously.
    """
    try:
        container = await docker.containers.get(container_id)
        container_info = await container.show()
        
        container_name = container_info.get("Name", "").lstrip("/")
        if not container_name:
            container_name = container_id[:12]
            
        # Ignore DocWatch itself if it somehow crashes (though we wouldn't be here)
        if container_name == settings.APP_NAME.lower().replace(" ", ""):
            return

        # Debounce logic
        now = time.time()
        last_crash = _crash_debouncer.get(container_name, 0)
        if now - last_crash < settings.DEBOUNCE_SECONDS:
            logger.info(f"Ignoring rapid crash for {container_name} (debounced)")
            return
            
        _crash_debouncer[container_name] = now
        logger.info(f"Processing crash for container {container_name}")

        image_hash = container_info.get("Image", "unknown")
        
        # Env snapshot
        raw_env_vars = container_info.get("Config", {}).get("Env", [])
        # Mask sensitive environment variables
        safe_env_vars = mask_sensitive_env_vars(raw_env_vars)
        env_snapshot = json.dumps(safe_env_vars)

        # Truncate env snapshot to prevent token limit errors
        if len(env_snapshot) > 3000:
            env_snapshot = env_snapshot[:3000] + "... [TRUNCATED DUE TO SIZE]"

        # Get logs from the last 5 minutes (300 seconds)
        since_time = int(now - 300)
        logs = ""
        try:
            # We request logs using aiodocker
            raw_logs = await container.log(stdout=True, stderr=True, since=since_time, tail=200)
            if isinstance(raw_logs, list):
                logs = "".join(raw_logs)
            else:
                logs = raw_logs
        except Exception as e:
            logger.warning(f"Failed to fetch logs for {container_name}: {e}")
            logs = "Logs unavailable."

        # Truncate logs to prevent token limit errors
        if len(logs) > 6000:
            # Keep the last 6000 characters as they are usually the most relevant for crashes
            logs = "[TRUNCATED] ... " + logs[-6000:]

        # Pass to AI
        logger.info(f"Classifying crash for {container_name} via AI...")
        classification, latency_ms = await classify_crash(
            container_name=container_name,
            image_hash=image_hash,
            logs=logs,
            env_snapshot=env_snapshot
        )

        # Save to DB
        incident = Incident(
            container_name=container_name,
            image_hash=image_hash,
            logs_context=logs,
            env_snapshot=env_snapshot,
            root_cause=classification["root_cause"],
            suggested_fix=classification["suggested_fix"],
            ai_latency_ms=latency_ms
        )
        saved_incident = await save_incident(incident)
        
        # Update Metrics
        CRASH_COUNT.inc()
        AI_LATENCY.observe(latency_ms / 1000.0)
        
        # Notify SSE clients (we'll use a global queue/event in main.py or just a pub/sub mechanism)
        # For simplicity, we can have a callback or just let the main.py poll or use a queue.
        # We will import a queue from a shared module if needed, or dispatch to webhooks.
        
        # Dispatch webhook
        webhook_payload = {
            "incident_id": saved_incident.id,
            "container_name": container_name,
            "root_cause": classification["root_cause"],
            "suggested_fix": classification["suggested_fix"],
            "timestamp": saved_incident.timestamp.isoformat()
        }
        from app.tasks import create_background_task
        create_background_task(dispatch_webhook(webhook_payload), name=f"webhook_{saved_incident.id}")
        
        from app.events import publish_incident
        publish_incident(saved_incident)

    except Exception as e:
        logger.error(f"Error handling crash event for {container_id}: {e}")

async def listen_to_docker_events():
    """
    Background task to listen to Docker socket events.
    Includes a retry loop to recover if the Docker daemon restarts or the socket drops.
    """
    logger.info("Starting Docker event listener...")
    from app.tasks import create_background_task

    while True:
        try:
            async with aiodocker.Docker() as docker:
                # Test connection
                await docker.system.info()
                logger.info("Successfully connected to Docker socket.")

                # We use events stream
                subscriber = docker.events.subscribe()
                while True:
                    event = await subscriber.get()
                    if event is None:
                        # Stream closed
                        logger.warning("Docker event stream closed unexpectedly.")
                        break

                    # We care about container 'die' events with non-zero exit status
                    if event.get("Type") == "container" and event.get("Action") == "die":
                        attrs = event.get("Actor", {}).get("Attributes", {})
                        exit_code = attrs.get("exitCode", "0")
                        if exit_code != "0":
                            container_id = event.get("Actor", {}).get("ID")
                            # Create background task for crash handling
                            create_background_task(
                                handle_crash_event(container_id, docker),
                                name=f"handle_crash_{container_id}"
                            )
        except asyncio.CancelledError:
            logger.info("Docker event listener task cancelled.")
            break
        except Exception as e:
            logger.error(f"Docker event listener encountered an error: {e}. Retrying in 5 seconds...")
            await asyncio.sleep(5)
