import asyncio
import shlex
from typing import Tuple
from app.config import logger

async def execute_docker_fix(command: str) -> Tuple[bool, str]:
    """
    Executes a suggested fix command securely.
    Ensures that the command is strictly a Docker command.
    Returns (success_boolean, output_or_error_message).
    """
    if not command or not command.strip():
        return False, "Empty command."

    try:
        args = shlex.split(command)
    except Exception as e:
        return False, f"Failed to parse command: {e}"

    if not args:
        return False, "Empty command after parsing."

    # Security Validation
    # Allow `docker`, `docker compose`, `docker-compose`
    base_cmd = args[0]
    is_valid = False
    
    if base_cmd == "docker":
        is_valid = True
    elif base_cmd == "docker-compose":
        is_valid = True
    elif base_cmd == "docker" and len(args) > 1 and args[1] == "compose":
        is_valid = True

    if not is_valid:
        logger.warning(f"Rejected unsafe command execution: {command}")
        return False, "Security Policy Violation: Only 'docker' or 'docker compose' commands are allowed."

    logger.info(f"Executing remediation command: {args}")
    try:
        process = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        
        output = stdout.decode().strip()
        err_output = stderr.decode().strip()
        
        if process.returncode == 0:
            return True, output if output else "Command executed successfully."
        else:
            return False, err_output if err_output else "Command failed with unknown error."
            
    except Exception as e:
        logger.error(f"Execution error: {e}")
        return False, f"Execution failed: {e}"
