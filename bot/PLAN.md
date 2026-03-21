# SE Toolkit Bot - Development Plan

## Overview

This document describes the implementation plan for the Telegram bot that interfaces with the LMS backend. The bot provides students with access to their lab work, scores, and other academic information through a conversational interface.

## Architecture

### Handler Pattern (Separation of Concerns)

The bot uses a **handler pattern** where command logic is separated from the Telegram transport layer. Each handler is a pure function that:
- Takes simple input parameters (or none)
- Returns a string response
- Has no dependency on Telegram APIs

This architecture enables:
1. **Testability**: Handlers can be tested via `--test` mode without Telegram
2. **Reusability**: Same handlers work in tests, CLI mode, and Telegram
3. **Maintainability**: Clear separation makes debugging easier

### Directory Structure

```
bot/
├── bot.py              # Entry point with --test mode and Telegram startup
├── config.py           # Environment variable loading
├── handlers/
│   ├── __init__.py
│   ├── commands.py     # /start, /help, /health, /labs, /scores
│   └── intents.py      # Task 3: LLM-based intent routing
├── services/
│   ├── __init__.py
│   ├── api_client.py   # Task 2: LMS API client with Bearer auth
│   └── llm_client.py   # Task 3: LLM client for intent recognition
├── pyproject.toml      # Dependencies
└── PLAN.md             # This file
```

## Task Breakdown

### Task 1: Scaffold (Current)

**Goal**: Create project structure with testable handlers.

**Deliverables**:
- `bot.py` with `--test` mode support
- Handler modules in `handlers/` directory
- `config.py` for environment loading
- `pyproject.toml` with dependencies
- `PLAN.md` (this document)

**Testing**: `uv run bot.py --test "/start"` returns welcome message.

### Task 2: Backend Integration

**Goal**: Connect handlers to the LMS backend API.

**Implementation**:
1. Create `services/api_client.py` with:
   - `LMSClient` class
   - Bearer token authentication
   - Methods: `get_health()`, `get_labs()`, `get_scores(lab_name)`
2. Update handlers to use the API client
3. Handle API errors gracefully (timeouts, 401, 500)

**Testing**: 
- `uv run bot.py --test "/health"` shows real backend status
- `/labs` returns actual lab list from API
- `/scores lab-04` returns real scores

### Task 3: LLM Intent Routing

**Goal**: Enable natural language queries using LLM.

**Implementation**:
1. Create `services/llm_client.py`:
   - Tool definitions for each command
   - LLM client that calls the tool API
2. Create `handlers/intents.py`:
   - Parse user message with LLM
   - Route to appropriate handler based on tool call
3. Update `bot.py` to handle plain text messages

**Key Insight**: The LLM decides which tool to call based on descriptions. Quality of tool descriptions matters more than prompt engineering.

**Testing**:
- `uv run bot.py --test "what labs can I submit?"` → routes to /labs
- `uv run bot.py --test "show my score for lab 2"` → routes to /scores

### Task 4: Docker Deployment

**Goal**: Containerize the bot for production deployment.

**Implementation**:
1. Create `bot/Dockerfile`:
   - Multi-stage build with uv
   - Non-root user for security
2. Update `docker-compose.yml`:
   - Add bot service
   - Network configuration (use service names, not localhost)
   - Volume mounts for environment files
3. Document deployment process

**Testing**:
- `docker compose up --build` starts all services
- Bot responds in Telegram
- Health checks pass

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `BOT_TOKEN` | Telegram bot token | Yes (production) |
| `LMS_API_BASE_URL` | Backend API URL | Yes |
| `LMS_API_KEY` | Backend API key | Yes |
| `LLM_API_KEY` | LLM provider API key | Task 3 |
| `LLM_MODEL` | LLM model name | Task 3 |

## Testing Strategy

1. **Unit Tests**: Test handlers in isolation (pytest)
2. **Test Mode**: `--test` flag for manual testing
3. **Integration Tests**: API client with mocked backend
4. **E2E Tests**: Deploy to VM and test in Telegram

## Future Improvements

- Add inline keyboard buttons for common actions
- Implement conversation state for multi-turn dialogs
- Add logging and monitoring
- Rate limiting for API calls
- Caching for frequently accessed data
