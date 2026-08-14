# Sales Intelligence Agent

> Production-ready conversational sales analysis agent. Enables natural language queries on enterprise sales datasets, eliminating the dependency on SQL or BI dashboards for non-technical users.

## 🏗️ Architecture

```
User
  │ POST /chat
  ▼
┌─────────────────┐
│   FastAPI       │  ← JWT Auth, 6 endpoints
│   (main.py)     │
└────────┬────────┘
         │
    ┌────┴────┐
    ▼         ▼
In-Session  Persistent
Memory      Memory (JSON / Cosmos DB)
    │
    ▼
┌─────────────────┐
│  LangGraph      │  ← State graph
│  Agent          │     LLM → Tools → LLM
└────────┬────────┘
         │
    ┌────┴────┐
    ▼         ▼
  Gemini     9 Tools
(3.1 Flash   (Pandas)
 Lite)
```

## 📦 Tech Stack

| Layer | Technology |
|---|---|
| **Orchestration** | LangGraph, LangChain |
| **LLM** | Google Gemini 3.1 Flash Lite (via `langchain-google-genai`) |
| **API** | FastAPI, Uvicorn, Pydantic |
| **Auth** | JWT (python-jose), Passlib/bcrypt, OAuth2PasswordBearer |
| **Data Analysis** | Pandas |
| **Memory** | In-Session (RAM), Persistent (JSON), Cosmos DB (Azure) |
| **Infrastructure** | Docker |
| **CI/CD** | GitHub Actions (tests + Docker build) |
| **Testing** | Pytest, standalone LangSmith trace script |
| **Observability** | LangSmith tracing |

## 🗂️ Project Structure

```
sales-intelligence-agent/
├── app/
│   ├── main.py              # FastAPI - HTTP endpoints + JWT Auth
│   ├── agent_langgraph.py   # LangGraph agent (state graph, Gemini)
│   ├── tools.py             # 9 data analysis functions (Pandas)
│   ├── memory.py            # InSessionMemory + PersistentMemory (JSON)
│   ├── cosmos_memory.py     # CosmosMemory (Azure Cosmos DB NoSQL)
│   └── auth.py              # JWT Authentication
├── data/
│   ├── ventas.csv           # Sales dataset (~15K transactions)
│   └── memory.json          # Local persistent memory
├── tests/
│   ├── test_tools.py        # Unit tests for the 9 tools
│   ├── test_api.py          # API integration tests
│   └── test_memoria.py      # Truncated memory test
├── test_langsmith.py        # Standalone smoke test w/ LangSmith tracing (no FastAPI needed)
├── .github/workflows/
│   └── ci-cd.yml            # CI/CD: Tests → Docker Build
├── Dockerfile
├── requirements.txt
└── README.md
```

## 🚀 Endpoints

| Method | Route | Description | Auth |
|---|---|---|---|
| GET | `/` | Health check | Public |
| POST | `/auth/token` | Obtain JWT token | Public |
| GET | `/ventas/resumen` | General sales summary | Bearer |
| POST | `/chat` | Conversation with in-session memory | Bearer |
| POST | `/chat/persistent` | Conversation with persistent memory | Bearer |
| GET | `/memory/{session_id}` | View conversation history | Bearer |
| DELETE | `/memory/{session_id}` | Clear conversation history | Bearer |

### Usage Example

```bash
# 1. Get token
curl -X POST http://localhost:8000/auth/token -d "username=admin&password=admin123"

# 2. Query the agent
curl -X POST http://localhost:8000/chat \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"session_id": "user-123", "question": "Who is the top seller?"}'
```

## 🧠 LangGraph Agent

The agent is modeled as a **state graph** with three nodes:

1. **`node_llm`** — The LLM interprets the question and decides whether to call a tool.
2. **`should_continue`** — Conditional: if `tool_calls` exist, go to Tools node; otherwise, end.
3. **`node_tools`** — Executes the selected tools and returns results to the LLM.

### Agent Features

- **9 decoupled tools** in `tools.py`: sales by seller, category, region, month, seller by month, product by region, product list, top product, general summary.
- **Full decoupling** between orchestration (LangGraph) and business logic (Pandas). Tools are agnostic to the data source.
- **Question enrichment** with conversation history context to handle pronouns and implicit references.
- **History truncation** to the last 10 messages to control token consumption in long conversations.

## 💾 Memory (3 Backends)

| Backend | Persistence | Scalable | Use Case |
|---|---|---|---|
| `InSessionMemory` | RAM (lost on restart) | No | Development / demo |
| `PersistentMemory` | Local JSON (`data/memory.json`) | No | Single-instance |
| `CosmosMemory` | Azure Cosmos DB NoSQL | **Yes** | Production multi-replica |

Backend selection via environment variable:
```bash
MEMORY_BACKEND=json    # default
MEMORY_BACKEND=cosmos  # requires COSMOS_ENDPOINT, COSMOS_KEY
```

All classes share the same public interface (`add_message`, `get_history`, `clear`), allowing backend swaps without modifying `main.py`.

## 🔐 JWT Authentication

- Tokens signed with `HS256`, configurable expiration (default 60 min).
- Passwords hashed with bcrypt.
- OAuth2 Password Bearer scheme.
- In production: migrate `USERS_DB` to Cosmos DB or SQL.

## 🔌 MCP Server

An alternative access path to the same 9 analysis tools, via the [Model
Context Protocol](https://modelcontextprotocol.io) — usable from any MCP
client (Claude Desktop, Claude.ai, Cursor, etc.), no HTTP client or LangGraph
knowledge required. `app/mcp_server.py` wraps `app/tools.py` directly; the
business logic is not duplicated between the FastAPI and MCP paths.

### Local usage (stdio)

```bash
pip install -r requirements.txt
python -m app.mcp_server
```

Then add it to your MCP client's config file (e.g. `claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "sales-intelligence-agent": {
      "command": "<absolute-path-to-your-venv>/Scripts/python.exe",
      "args": ["-m", "app.mcp_server"],
      "cwd": "<absolute-path-to-project-root>",
      "env": {
        "PYTHONPATH": "<absolute-path-to-project-root>"
      }
    }
  }
}
```

> **Windows note:** the `env.PYTHONPATH` entry works around a known issue
> where Claude Desktop on Windows doesn't always apply `cwd` before launching
> the subprocess, which otherwise causes `ModuleNotFoundError: No module
> named 'app'`. On macOS/Linux it's usually unnecessary but harmless to leave in.

On macOS/Linux, `command` is typically `<path-to-venv>/bin/python`.

### Remote usage (streamable-http)

```bash
export MCP_TRANSPORT=streamable-http
export PORT=8080
export MCP_AUTH_TOKEN=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
python -m app.mcp_server
```

Requires `Authorization: Bearer <MCP_AUTH_TOKEN>` on every request — the
server refuses to start without `MCP_AUTH_TOKEN` set, to avoid accidentally
exposing it unauthenticated.

## 🧪 Tests

```bash
# Unit tests for tools (26 tests)
pytest tests/test_tools.py -v

# API integration tests (calls the real Gemini API — requires GOOGLE_API_KEY)
pytest tests/test_api.py -v

# Truncated memory test
python tests/test_memoria.py

# Standalone smoke test with LangSmith tracing, no FastAPI required
python test_langsmith.py
```

`test_langsmith.py` runs 10 representative questions directly against `run_agent()` and prints pass/fail + latency per question, with full traces sent to LangSmith if `LANGCHAIN_TRACING_V2=true`.

## 🐳 Docker

```bash
docker build -t sales-agent .
docker run -p 8000:8000 -e GOOGLE_API_KEY=xxx sales-agent
```

## ⚙️ CI/CD

The pipeline in `.github/workflows/ci-cd.yml` runs on every push/PR to `main`:

1. **Tests** → `pytest tests/test_tools.py` and `pytest tests/test_api.py`
2. **Build** → builds the Docker image to verify it compiles cleanly

## ⚙️ Local Setup

```bash
# 1. Clone and install
pip install -r requirements.txt

# 2. Configure environment variables — create a .env file (see table below)

# 3. Run
uvicorn app.main:app --reload

# 4. Interactive documentation
open http://localhost:8000/docs
```

## 📄 Environment Variables

| Variable | Description | Default |
|---|---|---|
| `GOOGLE_API_KEY` | Gemini API key | — |
| `GEMINI_MODEL` | Gemini model | `gemini-3.1-flash-lite` |
| `JWT_SECRET_KEY` | Secret key for JWT signing | `dev-secret-key-change-in-production` |
| `JWT_EXPIRE_MINUTES` | Token expiration in minutes | `60` |
| `MEMORY_BACKEND` | Memory backend (`json` / `cosmos`) | `json` |
| `COSMOS_ENDPOINT` | Azure Cosmos DB endpoint | — |
| `COSMOS_KEY` | Azure Cosmos DB key | — |
| `COSMOS_DATABASE` | Database name | `sales-agent-db` |
| `COSMOS_CONTAINER` | Container name | `memory` |
| `LANGCHAIN_TRACING_V2` | Enable LangSmith tracing | `false` |
| `LANGCHAIN_API_KEY` | LangSmith API key | — |
| `LANGCHAIN_PROJECT` | LangSmith project name | — |

## 📝 Notes

- History truncation to 10 messages keeps token consumption stable at ~4,000-6,000 tokens per conversation.
- Docker healthcheck verifies the service responds before marking the container as healthy.
- Latency per request varies (observed ~5-15s) depending on the number of LLM round-trips the agent needs (each tool call adds one) and on Gemini's own response-time variability.

---

**Author:** Bernardo Mantilla Afanador
**License:** MIT