# syntax=docker/dockerfile:1
FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential gcc libsqlite3-dev && \
    rm -rf /var/lib/apt/lists/*

# Install Poetry
ENV POETRY_VERSION=1.8.2
RUN pip install "poetry==$POETRY_VERSION"

# Set work directory
WORKDIR /app

# Copy only requirements first for caching
COPY pyproject.toml poetry.lock ./

# Install dependencies
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi

# Copy the rest of the code
COPY src/ ./src/
COPY README.md ./

# Expose port (if your MCP server listens on 8000, adjust as needed)
EXPOSE 8000

# Default command to run the MCP server
CMD ["python", "src/stock_analysis/main.py"]
