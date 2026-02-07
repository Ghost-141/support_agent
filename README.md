# Support Agent

A WhatsApp-style customer support agent that answers product questions using a PostgreSQL-backed catalog and a tool-augmented LLM graph.

## Highlights
- Tool-augmented chat flow built with LangGraph and LangChain.
- PostgreSQL product catalog with search, category browsing, and review lookup.
- Local development loop with conversation memory persisted in Postgres.
- Rolling summary memory to keep recent turns plus a condensed history.
- Chroma-backed tool retrieval to bind only relevant tools per message.
- OLLAMA-based model configuration with environment-driven settings.

## How It Works
- The agent runs a LangGraph state machine with preprocess, tool retrieval, optional summarization, assistant, and tool nodes.
- The assistant uses a system prompt in `prompts.py` to decide when to call tools.
- Tools in `tools/qa.py` query the database through `db.py`.
- Conversation state is stored in Postgres using the LangGraph Postgres checkpointer.
- Tool retrieval uses a Chroma vector store built from tool descriptions in `tools/vectorize_tools.py`.
- Summarization keeps recent turns and rolls older context into a stored summary.

## Project Structure
- `api/app.py` configures the FastAPI app and registers routers.
- `api/routers/` contains WhatsApp, Telegram, and WebSocket endpoints.
- `api/services/` contains messaging helpers and the WebSocket manager.
- `agent.py` runs the agent logic and manages conversation memory.
- `graph_builder.py` wires the LLM, tools, and graph routing.
- `prompts.py` contains the system prompt and tool usage rules.
- `tools/qa.py` exposes database-backed tools to the LLM.
- `tools/vectorize_tools.py` builds the Chroma tool-retrieval index.
- `db.py` provides database access and helper functions.
- `schemas.py` defines typed response models.
- `data/products.json` is the seed dataset.
- `data/load_data.py` loads or updates data into the database.
- `frontend/` contains the React UI for local WebSocket testing.

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

3. Build the tool-retrieval index for Chroma.

```bash
uv run -m tools.vectorize_tools
```

## Configuration
These environment variables are used by the agent and loader.

- `OLLAMA_MODEL`
- `OLLAMA_EMBEDDING_MODEL`
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
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_WEBHOOK_SECRET` (optional but recommended)
- `MAX_MESSAGE_LENGTH` (shared limit for inbound messages)
- `SUMMARY_TRIGGER_TURNS` (turns before summarization)
- `SUMMARY_KEEP_TURNS` (recent turns to keep verbatim)
- `SUMMARY_MAX_CHARS` (summary character cap)
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

## Run The API Server
Start FastAPI for webhooks and WebSocket connections:

```bash
python main.py
```

The default port is `80` (see `main.py`). Update it if you want a different port.

## Local Testing
You have two local testing options.

1. CLI testing

```bash
python agent.py
```

2. WebSocket testing

- Backend endpoint: `ws://localhost:80/ws/{client_id}`
- Send plain text or JSON:

```json
{"text": "Hello", "stream": true}
```

The WebSocket server streams responses as JSON messages:

```json
{"type": "chunk", "text": "partial"}
{"type": "done"}
```

## Frontend (Local UI)
The `frontend/` React app connects to the WebSocket endpoint for local testing.

1. Install dependencies:

```bash
cd frontend
npm install
```

2. Run the dev server:

```bash
npm run dev
```

3. Open the URL shown by Vite and set the Server URL to match your API port.

## Integrations

### Telegram
Use Telegram to send user messages to the agent via webhook.

1. Create a bot with BotFather and copy the token.
2. Set the env vars in `.env`:

```bash
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_WEBHOOK_SECRET=your_secret_value
MAX_MESSAGE_LENGTH=1000
```

3. Run the FastAPI server:

```bash
python main.py
```

4. Expose your server over HTTPS (Telegram requires a public HTTPS URL).
5. Register the webhook URL (replace with your public domain):

```bash
curl -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/setWebhook" \
  -H "Content-Type: application/json" \
  -d "{\"url\":\"https://YOUR_DOMAIN/telegram/webhook\",\"secret_token\":\"$TELEGRAM_WEBHOOK_SECRET\"}"
```

6. Verify the webhook:

```bash
curl "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/getWebhookInfo"
```

The webhook handler is in `api/routers/telegram.py` and calls `run_agent()` to generate responses.

### WhatsApp
Upcoming.

### Messenger
Upcoming.

## WebSocket (Optional)
For local testing, you can connect via WebSocket and send messages directly to the agent.

WebSocket endpoint:
```bash
ws://localhost:8000/ws/{client_id}
```

Any message you send is passed to `run_agent()` and the response is returned over the socket.

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
- If tool retrieval returns no tools, rebuild the index with `uv run -m tools.vectorize_tools`.

## License
See `LICENSE`.
