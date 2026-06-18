# Code Review Copilot — webhook server container
FROM python:3.12-slim

WORKDIR /app

# Install deps first for layer caching
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir .

# Cloud hosts inject $PORT; default to 8000 for local runs.
ENV PORT=8000
EXPOSE 8000

# Honour the platform-provided PORT (App Runner / Railway / Fly / Render all set it).
CMD ["sh", "-c", "uvicorn copilot.webhook:app --host 0.0.0.0 --port ${PORT}"]
