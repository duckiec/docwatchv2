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
    # Allow strict whitelist of docker commands
    base_cmd = args[0]
    is_valid = False
    
    # Whitelist of allowed subcommands
    ALLOWED_SUBCOMMANDS = {"restart", "start", "stop", "logs", "network", "compose"}

    # Block potentially dangerous flags
    DANGEROUS_FLAGS = {"-v", "--volume", "--privileged", "--pid", "--network=host"}

    if base_cmd == "docker":
        if len(args) > 1 and args[1] in ALLOWED_SUBCOMMANDS:
            is_valid = True
    elif base_cmd == "docker-compose":
        if len(args) > 1 and args[1] in {"up", "down", "restart", "start", "stop", "logs"}:
            is_valid = True

    # Check for dangerous flags anywhere in the command
    has_dangerous_flag = any(flag in args for flag in DANGEROUS_FLAGS)

    if not is_valid or has_dangerous_flag:
        logger.warning(f"Rejected unsafe command execution: {command}")
        return False, "Security Policy Violation: Command is either not in whitelist or contains dangerous flags."

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
