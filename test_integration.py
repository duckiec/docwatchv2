import asyncio
import aiodocker
import pytest
import httpx
from bs4 import BeautifulSoup
from app.config import settings

@pytest.mark.asyncio
async def test_dummy_container_failure():
    async with aiodocker.Docker() as docker:
        print("Starting failing dummy container...")

        # Remove if exists
        try:
            old_container = await docker.containers.get("dummy-failing-container")
            await old_container.delete(force=True)
        except Exception:
            pass

        try:
            container = await docker.containers.run(
                config={
                    "Image": "alpine:latest",
                    "Cmd": ["sh", "-c", "echo 'failing now' && sleep 1 && /bin/false"]
                },
                name="dummy-failing-container"
            )
            await container.wait()
        except Exception as e:
            pytest.fail(f"Failed to run dummy container: {e}")

        print("Container crashed, waiting for DocWatch to process...")
        await asyncio.sleep(5)

        # Test AI integration by querying the endpoint directly.
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:8000/")
            assert response.status_code == 200

            # The HTML should contain the dummy container name
            html = response.text
            assert "dummy-failing-container" in html, "The failing container was not found on the dashboard"

            # Parse HTML to find the incident details
            soup = BeautifulSoup(html, "html.parser")

            # Find the card with this container name
            found = False
            for card in soup.find_all("div", class_="bg-gray-900"):
                title = card.find("h3")
                if title and "dummy-failing-container" in title.text:
                    found = True
                    text = card.text
                    assert "Unknown root cause" not in text
                    assert "No fix suggested" not in text
            assert found, "Could not find root cause or suggested fix in the UI for the failing container"
