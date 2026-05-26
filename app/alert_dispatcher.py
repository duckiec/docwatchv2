import httpx
from tenacity import retry, stop_after_attempt, wait_exponential
from app.config import settings, logger

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True
)
async def dispatch_webhook(incident_data: dict):
    if not settings.WEBHOOK_URL:
        return
        
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                settings.WEBHOOK_URL,
                json=incident_data,
                timeout=10.0
            )
            response.raise_for_status()
            logger.info(f"Successfully dispatched webhook for incident on {incident_data.get('container_name')}")
    except Exception as e:
        logger.error(f"Failed to dispatch webhook: {e}")
        raise e
