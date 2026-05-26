# Stage 1: Build Tailwind CSS using Standalone CLI
FROM alpine:3.19 AS tailwind-build
WORKDIR /app
# Download standalone CLI for Linux x64
RUN wget -qO tailwindcss https://github.com/tailwindlabs/tailwindcss/releases/latest/download/tailwindcss-linux-x64 \
    && chmod +x tailwindcss

# Copy templates and input css
COPY ./app/templates ./app/templates
COPY ./app/static/css/input.css ./app/static/css/input.css

# Run tailwind build
RUN ./tailwindcss -i ./app/static/css/input.css -o ./app/static/css/style.css --minify

# Stage 2: Build Python environment
FROM python:3.11-slim AS python-build
WORKDIR /app
COPY requirements.txt .
# Install wheel and dependencies
RUN pip install --user --no-cache-dir -r requirements.txt

# Stage 3: Final runtime
FROM python:3.11-slim
WORKDIR /app

# Ensure local pip bin is in PATH
ENV PATH=/root/.local/bin:$PATH

# Copy dependencies from python-build
COPY --from=python-build /root/.local /root/.local

# Copy application code
COPY ./app ./app

# Copy compiled CSS from tailwind-build
COPY --from=tailwind-build /app/app/static/css/style.css ./app/static/css/style.css

# Set python path
ENV PYTHONPATH=/app

EXPOSE 8000

# Start Uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
