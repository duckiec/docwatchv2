# DocWatch V2 - AI-Driven Docker Telemetry & Autonomous Remediation

DocWatch V2 is a "Mission Control" backend application that continuously monitors your Docker container fleet for crashes. When a container failure is detected, it automatically intercepts the event, gathers diagnostic telemetry (recent logs, state, and environment variables), and leverages an AI client (OpenAI) to accurately classify the root cause and even suggest or execute autonomous remediation.

## Key Features

* **Real-time Event Interception:** Uses `aiodocker` to stream the Docker engine event bus asynchronously.
* **AI Diagnostics Engine:** Automatically packages pre-crash logs and environment context to request a natural language diagnosis from OpenAI.
* **Autonomous Remediation:** Executes safe, whitelisted Docker recovery commands to attempt to auto-heal crashing containers.
* **2026 UI Standards:** A stunning, fully overhauled HTMX and Tailwind CSS dashboard featuring dark zinc themes, glassmorphism, and live Server-Sent Events (SSE) stats updates.
* **Security & Stability:**
  * **Environment Variable Masking:** Automatically redacts sensitive secrets (like `PASSWORD`, `SECRET`, `TOKEN`) before sending data to the AI.
  * **Safe Remediation Execution:** Strict whitelist-based command execution that explicitly blocks dangerous Docker flags (like `-v`, `--privileged`).
  * **Resilience:** Implements Write-Ahead Logging (WAL) for SQLite, aggressive client-disconnect detection for SSE, and robust exception handling.
  * **Memory Safe Tasks:** Utilizes a strong-reference task registry to prevent background asyncio tasks from dying silently.

## Tech Stack

* **Backend:** Python 3.12, FastAPI, SQLAlchemy (Async), aiosqlite, aiodocker.
* **Frontend:** Jinja2 Templates, HTMX, Tailwind CSS (Standalone CLI).
* **AI:** OpenAI API Client.
* **Infrastructure:** Docker Compose.

## Getting Started

### Prerequisites

* Docker and Docker Compose installed.
* An OpenAI API Key.

### Running Locally with Docker Compose

1. Clone the repository.
2. Create a `.env` file in the root directory (or ensure the environment variables are set):
   ```env
   OPENAI_API_KEY=your_openai_api_key_here
   ```
3. Build and run the containers:
   ```bash
   docker compose build
   docker compose up -d
   ```
4. Access the Mission Control dashboard at `http://localhost:8000`.

### Running Tests

The test suite requires `pytest` and `pytest-asyncio`. Run them natively using the appropriate Python version:

```bash
python3.12 -m pytest
```

*(Note: The test suite creates its own in-memory SQLite instances and mocks the OpenAI client, making it safe to run locally without infrastructure setup).*

## Architecture Details

* **`app/main.py`**: The FastAPI application entrypoint. Configures routes, middleware (SecurityHeadersMiddleware), and the lifecycle events.
* **`app/docker_events.py`**: Contains the core logic for subscribing to the Docker event stream, gathering pre-crash context, truncating large logs to prevent AI token limits, and dispatching events to the AI client and the UI.
* **`app/ai_client.py`**: Handles communication with the OpenAI API.
* **`app/remediation.py`**: Safely executes whitelisted Docker commands (like restarting containers).
* **`app/security.py`**: Centralized logic for sanitizing and masking sensitive environment variables.
* **`app/tasks.py`**: Manages the lifecycle of long-running asynchronous background tasks, preventing garbage collection issues.
* **`app/db.py`**: Configures the asynchronous SQLAlchemy engine with SQLite WAL pragmas for high concurrency performance.