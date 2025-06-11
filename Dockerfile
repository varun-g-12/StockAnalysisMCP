# ---- Builder Stage ----
# This stage installs Poetry and project dependencies.
FROM python:3.12-slim-bookworm AS builder

# Set environment variables for Python and Poetry
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    POETRY_VERSION=2.1.3 \
    POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_IN_PROJECT=true

# Add Poetry to the PATH
ENV PATH="$POETRY_HOME/bin:$PATH"

# Install Poetry using pip for better Docker integration
RUN pip install "poetry==$POETRY_VERSION"

# Set the working directory
WORKDIR /app

# Copy only the dependency definition files first
# This allows Docker to cache the dependency installation layer
COPY pyproject.toml poetry.lock* README.md ./

# Copy the source code and temp dir
COPY src/ ./src/

# Install project dependencies into a local .venv folder
# --no-dev: Installs only production dependencies.
# --no-interaction: Prevents interactive prompts.
# --no-ansi: Disables ANSI output for cleaner logs.
RUN poetry install --only main --no-interaction --no-ansi

# ---- Final Stage ----
# This stage creates the final, lean production image.
FROM python:3.12-slim-bookworm AS final

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

# Set the working directory
WORKDIR /app

# Copy the virtual environment (with dependencies) from the builder stage
COPY --from=builder /app/.venv ./.venv

# Copy the source code from the builder stage
COPY --from=builder /app/src ./src/

# Create a volume mount point for output
# VOLUME ["/app/tempDir"]

# Set the command to run the application
CMD ["python", "-m", "src.stock_analysis.main"]