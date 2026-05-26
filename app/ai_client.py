import json
import time
from typing import Tuple, Dict, Any
import openai
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings, logger

# Initialize async client
client = openai.AsyncOpenAI(
    api_key=settings.AI_API_KEY if settings.AI_API_KEY else "dummy",
    base_url=settings.AI_BASE_URL
)

PROMPT_TEMPLATE = """
You are an expert site reliability engineer. A Docker container has crashed.
Here are the pre-crash logs and environment details.
Your task is to classify the root cause of the crash and provide a concrete, actionable suggested fix.

Container Name: {container_name}
Image Hash: {image_hash}

Environment Variables Snapshot:
{env_snapshot}

Pre-Crash Logs (last 5 minutes):
{logs}

Please respond strictly with a JSON object in this exact format, with no markdown code blocks wrapping it:
{{
    "root_cause": "brief explanation of why the container crashed",
    "suggested_fix": "a concrete fix (e.g. command, env var change, or docker-compose edit)"
}}
"""

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True
)
async def classify_crash(
    container_name: str,
    image_hash: str,
    logs: str,
    env_snapshot: str
) -> Tuple[Dict[str, str], int]:
    """
    Classify the crash using AI.
    Returns a tuple of (parsed_json_dict, latency_ms).
    """
    start_time = time.time()
    
    prompt = PROMPT_TEMPLATE.format(
        container_name=container_name,
        image_hash=image_hash,
        env_snapshot=env_snapshot,
        logs=logs
    )
    
    try:
        response = await client.chat.completions.create(
            model=settings.AI_MODEL,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that outputs JSON."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
            max_tokens=500
        )
        
        latency_ms = int((time.time() - start_time) * 1000)
        
        raw_content = response.choices[0].message.content
        if not raw_content:
            raise ValueError("Empty response from AI")
            
        parsed = json.loads(raw_content)
        
        # Ensure keys exist
        root_cause = parsed.get("root_cause", "Unknown root cause")
        suggested_fix = parsed.get("suggested_fix", "No fix suggested")
        
        return {"root_cause": root_cause, "suggested_fix": suggested_fix}, latency_ms

    except Exception as e:
        logger.error(f"Failed to classify crash for {container_name}: {e}")
        raise e
