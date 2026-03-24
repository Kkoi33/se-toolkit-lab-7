# Bot Dockerfile
# Uses uv for dependency management (not pip/requirements.txt)

FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim

WORKDIR /app

# Copy root workspace files for uv sync
COPY pyproject.toml uv.lock ./

# Copy bot-specific files
COPY bot/pyproject.toml ./bot/

# Install dependencies using uv (workspace-aware)
RUN uv sync --frozen --no-dev

# Copy bot source code
COPY bot/ ./bot/

# Set working directory to bot
WORKDIR /app/bot

# Run the bot
CMD ["uv", "run", "bot.py"]
