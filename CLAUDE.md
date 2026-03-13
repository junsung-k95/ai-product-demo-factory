# CLAUDE.md — AI Product Demo Factory

This file provides guidance for AI assistants (Claude Code, Copilot, etc.) working in this repository.

---

## Project Overview

**ai-product-demo-factory** is a service that accepts customer RFPs and requirements and automatically generates:
- Flashy, fully-functional UIs
- Minimal-yet-working backends
- AI Agent features powered by **Claude** (Anthropic), **OpenAI GPT**, **Google Gemini**, and other AI services

The goal is rapid demo generation: given a prompt/spec, produce a deployable, impressive demo in minutes.

---

## Repository State

This repository is in its **initial/scaffolding phase** — only `.gitignore` and `README.md` exist. No application code has been committed yet. When building out the project, follow the conventions in this document.

---

## Intended Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.11+ |
| Package manager | `uv` (preferred) or `pip` with `pyproject.toml` |
| Backend framework | FastAPI (recommended) or Flask |
| AI SDKs | `anthropic`, `openai`, `google-generativeai` |
| Frontend generation | Jinja2 templates, or generated HTML/JS/CSS strings |
| Testing | `pytest` |
| Linting / formatting | `ruff` |
| Type checking | `mypy` |

---

## Directory Structure (Planned)

When source code is added, follow this layout:

```
ai-product-demo-factory/
├── CLAUDE.md                  # This file
├── README.md
├── .gitignore
├── pyproject.toml             # Project metadata & dependencies
├── uv.lock                    # Lock file (commit this)
│
├── src/
│   └── demo_factory/
│       ├── __init__.py
│       ├── main.py            # FastAPI app entry point
│       ├── config.py          # Settings / env var loading (pydantic-settings)
│       │
│       ├── api/               # HTTP route handlers
│       │   ├── __init__.py
│       │   └── routes.py
│       │
│       ├── agents/            # AI agent implementations
│       │   ├── __init__.py
│       │   ├── claude_agent.py
│       │   ├── openai_agent.py
│       │   └── gemini_agent.py
│       │
│       ├── generator/         # Core demo generation logic
│       │   ├── __init__.py
│       │   ├── ui_generator.py
│       │   ├── backend_generator.py
│       │   └── rfp_parser.py
│       │
│       └── templates/         # Base HTML/CSS/JS templates for generated demos
│           └── base.html
│
├── tests/
│   ├── conftest.py
│   ├── test_agents/
│   └── test_generator/
│
├── demos/                     # Output directory for generated demos (gitignored)
├── examples/                  # Example RFP inputs and sample outputs
└── docs/                      # Extended documentation
```

---

## Development Conventions

### Python Style

- Target **Python 3.11+**; use modern syntax (`match`, `|` union types, `tomllib`, etc.)
- Use **type annotations** on all function signatures
- Format and lint with **`ruff`** — do not manually fix what ruff can auto-fix
- Run `ruff check --fix .` and `ruff format .` before committing
- Use **`mypy --strict`** for type checking on core modules

### Dependency Management

- Use `uv` as the primary package manager:
  ```bash
  uv add anthropic openai google-generativeai fastapi uvicorn
  uv add --dev pytest ruff mypy pytest-asyncio httpx
  ```
- Commit `uv.lock` to the repository for reproducible installs
- Pin AI SDK versions explicitly — breaking changes are common

### Environment Variables

Store secrets in `.env` (never commit). Provide `.env.example` with all required keys:

```
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
GOOGLE_API_KEY=
ENVIRONMENT=development   # development | production
LOG_LEVEL=INFO
```

Load settings using `pydantic-settings`:
```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    anthropic_api_key: str
    openai_api_key: str
    google_api_key: str
    environment: str = "development"

    class Config:
        env_file = ".env"
```

---

## AI API Conventions

### Claude (Anthropic)

Use the **`anthropic` Python SDK**. Default to the latest capable model:

```python
import anthropic

client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env

message = client.messages.create(
    model="claude-sonnet-4-6",   # default model for most tasks
    max_tokens=8096,
    messages=[{"role": "user", "content": prompt}]
)
```

- Use `claude-opus-4-6` for complex reasoning / architecture planning
- Use `claude-sonnet-4-6` for balanced performance (default)
- Use `claude-haiku-4-5-20251001` for fast, cheap, high-volume calls
- Always set explicit `max_tokens`; never rely on defaults
- Use **streaming** (`client.messages.stream(...)`) for long-running generation tasks to show progress

### OpenAI

```python
from openai import OpenAI

client = OpenAI()  # reads OPENAI_API_KEY from env
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": prompt}]
)
```

### Google Gemini

```python
import google.generativeai as genai

genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
model = genai.GenerativeModel("gemini-1.5-pro")
response = model.generate_content(prompt)
```

### Multi-Provider Pattern

Abstract provider calls behind a common interface so the demo factory can route to any AI provider:

```python
from abc import ABC, abstractmethod

class AIProvider(ABC):
    @abstractmethod
    async def generate(self, prompt: str, **kwargs) -> str: ...
```

---

## Testing

- Use **`pytest`** with **`pytest-asyncio`** for async tests
- Test files live in `tests/` mirroring the `src/demo_factory/` structure
- Use `httpx.AsyncClient` for FastAPI endpoint tests
- Mock all external AI API calls in unit tests (use `pytest-mock` or `unittest.mock`)
- Run tests:
  ```bash
  pytest -v
  pytest --cov=demo_factory tests/   # with coverage
  ```

### Key test patterns

```python
# Mock AI calls to avoid real API costs in tests
from unittest.mock import patch, AsyncMock

@patch("demo_factory.agents.claude_agent.anthropic.Anthropic")
def test_generate_ui(mock_client):
    mock_client.return_value.messages.create.return_value.content = [...]
    ...
```

---

## Common Development Tasks

### Run the development server

```bash
uv run uvicorn demo_factory.main:app --reload --port 8000
```

### Run linting and formatting

```bash
uv run ruff check --fix .
uv run ruff format .
```

### Run type checking

```bash
uv run mypy src/
```

### Run all tests

```bash
uv run pytest -v
```

### Generate a demo (CLI)

```bash
uv run python -m demo_factory.cli generate --rfp examples/sample_rfp.txt --output demos/
```

---

## Git Conventions

- Branch naming: `feature/<description>`, `fix/<description>`, `claude/<description>-<id>`
- Commit messages: imperative mood, present tense — e.g., `Add Claude streaming support`, `Fix RFP parser for multi-page PDFs`
- Never commit `.env`, API keys, or generated demo output files
- Keep PRs focused; one logical change per PR

---

## Security

- **Never hardcode API keys** — always use environment variables
- **Never log API keys** — scrub secrets from all log output
- Sanitize all user-supplied RFP content before inserting into prompts (prompt injection risk)
- Rate-limit API endpoints to prevent abuse of AI API quotas
- Generated demo code should be sandboxed before execution

---

## Key Architectural Decisions

1. **Multi-provider AI routing**: Support Claude, OpenAI, and Gemini behind a unified interface so demos can showcase any provider or compare outputs side-by-side.

2. **Demo isolation**: Each generated demo runs in its own namespace/directory. Demos are stateless and self-contained (single HTML file + optional data file).

3. **Streaming-first**: Use streaming responses from AI APIs to give real-time feedback during generation — demos can take 30–120s to generate.

4. **Template-driven generation**: Maintain a library of base templates (e-commerce, dashboard, landing page, chatbot UI, etc.) that the AI fills in rather than generating from scratch every time.

5. **RFP parsing pipeline**: Structured extraction of requirements from free-text RFPs before handing off to generators — improves output quality and allows validation.
