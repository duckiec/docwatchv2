import pytest
from unittest.mock import MagicMock, patch
import json
from app.ai_client import classify_crash

@pytest.mark.asyncio
@patch('app.ai_client.client.chat.completions.create')
async def test_classify_crash_success(mock_create):
    # Mocking OpenAI response correctly for modern python / openai library
    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = json.dumps({
        "root_cause": "Test simulated OOM",
        "suggested_fix": "docker restart test"
    })
    mock_response.choices = [mock_choice]

    # We must make the mocked create method return a coroutine that yields the mock response
    async def _mock_create(*args, **kwargs):
        return mock_response

    mock_create.side_effect = _mock_create

    result, latency = await classify_crash(
        container_name="test",
        image_hash="sha256:test",
        logs="error oom",
        env_snapshot="{}"
    )

    assert result["root_cause"] == "Test simulated OOM"
    assert result["suggested_fix"] == "docker restart test"
    assert latency >= 0

@pytest.mark.asyncio
@patch('app.ai_client.client.chat.completions.create')
async def test_classify_crash_malformed(mock_create):
    # Mocking OpenAI returning bad JSON structure but it doesn't fail parsing, just lacks keys
    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = json.dumps({
        "not_the_right_key": "Oops"
    })
    mock_response.choices = [mock_choice]

    async def _mock_create(*args, **kwargs):
        return mock_response

    mock_create.side_effect = _mock_create

    result, latency = await classify_crash(
        container_name="test",
        image_hash="sha256:test",
        logs="error",
        env_snapshot="{}"
    )

    # Should break loop and return defaults because keys are missing
    assert result["root_cause"] == "Unknown root cause"
    assert result["suggested_fix"] == "No fix suggested"
