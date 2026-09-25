from fastapi.templating import Jinja2Templates
import os
from datetime import datetime

templates = Jinja2Templates(directory="app/templates")

class MockIncident:
    def __init__(self):
        self.id = 1
        self.container_name = "test_container_xyz"
        self.image_hash = "sha256:1234567890abcdef"
        self.timestamp = datetime.now()
        self.root_cause = "Out of memory gracefully."
        self.suggested_fix = "docker start dummy"
        self.logs_context = "Log output"
        self.env_snapshot = '{"ENV": "test"}'

def test_render():
    incident = MockIncident()
    try:
        html = templates.get_template("components/incident_card.html").render({"incident": incident})
        assert html is not None
        assert "test_container_xyz" in html
        print("Template rendered successfully")
    except Exception as e:
        print(f"Error rendering: {e}")

test_render()
