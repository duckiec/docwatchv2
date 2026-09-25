import json
import time
from typing import Tuple, Dict, Any, List
import openai
from tenacity import retry, stop_after_attempt, wait_exponential
import aiodocker

from app.config import settings, logger

client = openai.AsyncOpenAI(
    api_key=settings.AI_API_KEY if settings.AI_API_KEY else "dummy",
    base_url=settings.AI_BASE_URL,
    timeout=15.0  # Prevent hanging indefinitely on AI calls
)

SYSTEM_PROMPT = """
You are an expert site reliability engineer resolving a Docker container crash.
You are now an active agent in a ReAct (Reasoning + Acting) loop.

You will be provided with the initial pre-crash logs and environment details.

If you have enough information to diagnose the issue and provide a fix, respond strictly with this JSON format:
{
    "root_cause": "brief explanation of why the container crashed",
    "suggested_fix": "a concrete docker command to fix it (e.g. docker restart xyz, docker network disconnect...)"
}

If you need more context before deciding on a fix, you can request it by returning one of these JSON actions:
{
    "action": "inspect_container",
    "container_id": "the container id or name"
}
OR
{
    "action": "get_stats",
    "container_id": "the container id or name"
}

Do not wrap your JSON in markdown code blocks. Output ONLY valid JSON.
"""

async def execute_action(action: str, container_id: str) -> str:
    """Helper to execute diagnostic actions via aiodocker"""
    try:
        async with aiodocker.Docker() as docker:
            container = await docker.containers.get(container_id)
            if action == "inspect_container":
                info = await container.show()
                # Truncate to avoid massive tokens
                return json.dumps(info)[:3000]
            elif action == "get_stats":
                stats = await container.stats(stream=False)
                return json.dumps(stats[0] if stats else {})[:3000]
            else:
                return f"Unknown action: {action}"
    except Exception as e:
        return f"Action {action} failed: {e}"

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
    
    start_time = time.time()
    
    initial_user_prompt = f"""
Container Name: {container_name}
Image Hash: {image_hash}

Environment Variables Snapshot:
{env_snapshot}

Pre-Crash Logs (last 5 minutes):
{logs}
"""

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": initial_user_prompt}
    ]
    
    max_iterations = 3
    root_cause = "Unknown root cause"
    suggested_fix = "No fix suggested"
    
    for i in range(max_iterations):
        logger.info(f"Agentic loop iteration {i+1}/{max_iterations} for {container_name}")
        try:
            response = await client.chat.completions.create(
                model=settings.AI_MODEL,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.2,
                max_tokens=500
            )
            
            raw_content = response.choices[0].message.content
            if not raw_content:
                raise ValueError("Empty response from AI")
                
            parsed = json.loads(raw_content)
            
            # Did the AI output a final fix?
            if "root_cause" in parsed and "suggested_fix" in parsed:
                root_cause = parsed["root_cause"]
                suggested_fix = parsed["suggested_fix"]
                break
                
            # Did the AI ask for an action?
            elif "action" in parsed and "container_id" in parsed:
                action = parsed["action"]
                cid = parsed["container_id"]
                logger.info(f"AI requested action: {action} on {cid}")
                
                # Execute action
                action_result = await execute_action(action, cid)
                
                # Append to messages for next iteration
                messages.append({"role": "assistant", "content": raw_content})
                messages.append({
                    "role": "user", 
                    "content": f"Result of {action}:\n{action_result}\nPlease proceed with diagnosis."
                })
            else:
                # Malformed output, just break
                logger.warning(f"Malformed AI response: {parsed}")
                break
                
        except Exception as e:
            logger.error(f"Failed to communicate with AI for {container_name}: {e}")
            raise e

    # If loop exhausted without a fix, we just return the defaults or last parsed
    latency_ms = int((time.time() - start_time) * 1000)
    return {"root_cause": root_cause, "suggested_fix": suggested_fix}, latency_ms
