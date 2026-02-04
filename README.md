# Support Agent

A WhatsApp-style customer support agent that answers product questions using a PostgreSQL-backed catalog and a tool-augmented LLM graph.

## Highlights
- Tool-augmented chat flow built with LangGraph and LangChain.
- PostgreSQL product catalog with search, category browsing, and review lookup.
- Local development loop with conversation memory persisted in Postgres.
- OLLAMA-based model configuration with environment-driven settings.

## How It Works
- The agent runs a LangGraph state machine with an assistant node and a tool node.
- The assistant uses a system prompt in `prompts.py` to decide when to call tools.
- Tools in `tools/qa.py` query the database through `db.py`.
- Conversation state is stored in Postgres using the LangGraph Postgres checkpointer.

## Project Structure
- `agent.py` runs the interactive chat loop and manages memory.
- `graph_builder.py` wires the LLM, tools, and graph routing.
- `prompts.py` contains the system prompt and tool usage rules.
- `tools/qa.py` exposes database-backed tools to the LLM.
- `db.py` provides database access and helper functions.
- `schemas.py` defines typed response models.
- `data/products.json` is the seed dataset.
- `data/load_data.py` loads or updates data into the database.

## Requirements
- Python 3.11+
- A running PostgreSQL instance (Supabase or local)
- OLLAMA running locally or remotely

## Setup
1. Create a virtual environment and install dependencies.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r <(python - <<'PY'
import tomllib
from pathlib import Path
pyproject = tomllib.loads(Path('pyproject.toml').read_text())
print('\n'.join(pyproject['project']['dependencies']))
PY
)
```

If you use `uv`:

```bash
uv venv
source .venv/bin/activate
uv pip install -r <(python - <<'PY'
import tomllib
from pathlib import Path
pyproject = tomllib.loads(Path('pyproject.toml').read_text())
print('\n'.join(pyproject['project']['dependencies']))
PY
)
```

2. Copy `.env.example` to `.env` and update values.

```bash
cp .env.example .env
```

## Configuration
These environment variables are used by the agent and loader.

- `OLLAMA_MODEL`
- `OLLAMA_BASE_URL`
- `OLLAMA_TEMPERATURE`
- `OLLAMA_NUM_PREDICT`
- `OLLAMA_NUM_CTX`
- `SUPASEBASE_DB_URL` or all of:
- `SUPASEBASE_DB_HOST`
- `SUPASEBASE_DB_NAME`
- `SUPASEBASE_DB_USER`
- `SUPASEBASE_DB_PASSWORD`
- `SUPASEBASE_DB_PORT`
- `LANGCHAIN_API_KEY` (optional for tracing)
- `LANGCHAIN_ENDPOINT` (optional for tracing)
- `CREATE_TABLES` (used by `data/load_data.py`)

Note: The code expects the `SUPASEBASE_` prefix exactly as shown.

## Database Setup
You have two ways to create and seed the database.

Option 1: Use `db.py` helpers.

```bash
python db.py
```

This runs `init_db()` and `seed_db()`. `seed_db()` expects a `products.json` file in the current working directory, so run it from a directory that contains `products.json` or place a copy at the repo root.

Option 2: Use the data loader.

```bash
cd data
python load_data.py
```

Set `CREATE_TABLES=1` in your environment to create tables automatically.

## Run The Agent
Start the local interactive loop:

```bash
python agent.py
```

- You can type `/clear` to remove conversation history for the current user.
- Use `quit`, `exit`, or `q` to leave the session.

## Available Tools
These are exposed to the LLM via LangChain tools in `tools/qa.py`.

- `search_products` uses hybrid keyword search.
- `get_product_by_name` fetches exact title matches.
- `get_product_reviews` returns recent reviews by product ID.
- `get_tag_categories` lists categories.
- `get_products_in_category` lists products by category.

## Prompt Rules
The assistant behavior is governed by `prompts.py`.

- The first message begins with a fixed greeting.
- Tool usage is constrained by an explicit protocol.
- The prompt enforces a single tool call per response.

## Troubleshooting
- If the agent returns empty results, verify the database is seeded.
- If tools fail, confirm `SUPASEBASE_DB_URL` or the split `SUPASEBASE_DB_*` variables.
- If the model fails to respond, check that OLLAMA is running and `OLLAMA_BASE_URL` is correct.

## License
See `LICENSE`.
