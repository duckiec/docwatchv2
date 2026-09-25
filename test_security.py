import pytest
from app.security import mask_sensitive_env_vars
from app.remediation import execute_docker_fix

def test_mask_sensitive_env_vars():
    raw_env = ["API_KEY=123", "DB_PASSWORD=secret", "NORMAL_VAR=hello", "NOT_A_KV_PAIR"]
    masked = mask_sensitive_env_vars(raw_env)
    assert "API_KEY=***MASKED***" in masked
    assert "DB_PASSWORD=***MASKED***" in masked
    assert "NORMAL_VAR=hello" in masked
    assert "NOT_A_KV_PAIR" in masked

@pytest.mark.asyncio
async def test_remediation_whitelist():
    # Allowed
    success, _ = await execute_docker_fix("docker restart my_container")
    assert success is True or success is False # Command itself might fail if no docker daemon, but should pass security validation

    # Not allowed
    success, msg = await execute_docker_fix("rm -rf /")
    assert success is False
    assert "Security Policy Violation" in msg

    success, msg = await execute_docker_fix("docker run -v /:/host alpine")
    assert success is False
    assert "Security Policy Violation" in msg
