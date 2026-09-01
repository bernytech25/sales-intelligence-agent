<div align="center">

# Sales Intelligence Agent

[![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?logo=fastapi)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-Agent-2C3E50?logo=langchain)](https://langchain-ai.github.io/langgraph/)
[![MCP](https://img.shields.io/badge/MCP-Protocol-purple?logo=modelcontextprotocol)](https://modelcontextprotocol.io/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker)](https://www.docker.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![CI/CD](https://github.com/bernytech25/sales-intelligence-agent/actions/workflows/ci-cd.yml/badge.svg)](https://github.com/bernytech25/sales-intelligence-agent/actions)
[![Last Commit](https://img.shields.io/github/last-commit/bernytech25/sales-intelligence-agent?color=orange)](https://github.com/bernytech25/sales-intelligence-agent/commits/main)

**Agente conversacional de análisis de ventas con LangGraph + MCP**

</div>

> Production-ready conversational sales analysis agent. Enables natural language queries on enterprise sales datasets, eliminating the dependency on SQL or BI dashboards for non-technical users.

## 🏗️ Architecture

User (HTTP)                          User (MCP client:
  │ POST /chat                        Claude Desktop, Cursor, etc.)
  ▼                                     │
┌─────────────────┐                    ▼
│   FastAPI       │  ← JWT Auth  ┌─────────────────┐
│   (main.py)     │              │  MCP Server     │  ← Bearer token
└────────┬────────┘              │  (mcp_server.py)│     (stdio or
         │                       └────────┬────────┘      streamable-http)
    ┌────┴────┐                           │
    ▼         ▼                           │
In-Session  Persistent                    │
Memory      Memory (JSON / Cosmos DB)     │
    │                                     │
    ▼                                     │
┌─────────────────┐                       │
│  LangGraph      │  ← State graph        │
│  Agent          │     LLM → Tools → LLM │
└────────┬────────┘                       │
         │                                │
    ┌────┴────┐                           │
    ▼         ▼                           ▼
  Gemini     10 Tools ◄────────────────────
(3.1 Flash   (Pandas)
 Lite)
```

Both paths share the exact same `tools.py` — no business logic is
duplicated between them. The FastAPI path is orchestrated by LangGraph
(this repo owns the reasoning loop); the MCP path is orchestrated by
whichever MCP client connects (the client's own LLM owns the reasoning
loop, this repo only exposes the tools).

## 📦 Tech Stack

| Layer | Technology |
|---|---|
| **Orchestration** | LangGraph, LangChain |
| **LLM** | Google Gemini 3.1 Flash Lite (via `langchain-google-genai`) |
| **API** | FastAPI, Uvicorn, Pydantic |
| **Auth** | JWT (python-jose), Passlib/bcrypt, OAuth2PasswordBearer |
| **Data Analysis** | Pandas |
| **Memory** | In-Session (RAM), Persistent (JSON), Cosmos DB (Azure) |
| **Infrastructure** | Docker, Azure Container Apps (FastAPI), Google Cloud Run (MCP) |
| **Tool Protocol** | Model Context Protocol (MCP) — stdio + streamable-http |
| **CI/CD** | GitHub Actions (tests + Docker build) |
| **Testing** | Pytest, standalone LangSmith trace script |
| **Observability** | LangSmith tracing |

## 🗂️ Project Structure

```
sales-intelligence-agent/
├── app/
│   ├── main.py              # FastAPI - HTTP endpoints + JWT Auth
│   ├── agent_langgraph.py   # LangGraph agent (state graph, Gemini)
│   ├── mcp_server.py        # MCP server: local stdio + remote streamable-http
│   ├── tools.py             # 10 data analysis functions (Pandas)
│   ├── memory.py            # InSessionMemory + PersistentMemory (JSON)
│   ├── cosmos_memory.py     # CosmosMemory (Azure Cosmos DB NoSQL)
│   └── auth.py              # JWT Authentication
├── data/
│   ├── ventas.csv           # Sales dataset (~15K transactions)
│   └── memory.json          # Local persistent memory
├── tests/
│   ├── test_tools.py        # Unit tests for the tools
│   ├── test_api.py          # API integration tests
│   └── test_memoria.py      # Truncated memory test
├── test_langsmith.py        # Standalone smoke test w/ LangSmith tracing (no FastAPI needed)
├── .github/workflows/
│   └── ci-cd.yml            # CI/CD: Tests → Docker Build (FastAPI path only)
├── Dockerfile                # FastAPI image
├── Dockerfile.mcp            # MCP server image
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

- **10 decoupled tools** in `tools.py`: sales by seller, category, region, month, seller by month, vendor ranking by date range, product by region, product list, top product, general summary.
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

An alternative access path to the same 10 analysis tools, via the [Model
Context Protocol](https://modelcontextprotocol.io) — usable from any MCP
client, no HTTP client or LangGraph knowledge required. `app/mcp_server.py`
wraps `app/tools.py` directly; the business logic is not duplicated between
the FastAPI and MCP paths.

### Client compatibility

| Client | Remote HTTP support | Notes |
|---|---|---|
| Cursor | Native | Paste URL + header, done |
| VS Code + Cline | Native | Same as above |
| Windsurf | Native | Same as above |
| Claude Desktop | stdio only | See below |
| Claude.ai (web) | Via custom connector | Requires OAuth or a beta "static header" feature (early-access only as of Aug 2026) |

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
export ALLOWED_HOST=<your-deployed-host>  # e.g. my-service-xxxxx.a.run.app
python -m app.mcp_server
```

Requires `Authorization: Bearer <MCP_AUTH_TOKEN>` on every request — the
server refuses to start without `MCP_AUTH_TOKEN` set, to avoid accidentally
exposing it unauthenticated.

`ALLOWED_HOST` is required for any deployment behind a real hostname (not
`localhost`): the MCP SDK's DNS-rebinding protection rejects the `Host`
header of any hostname not explicitly allowlisted, returning
`421 Invalid Host header` otherwise.

### Deployed instance (Google Cloud Run)

The remote server is deployed on **Google Cloud Run**, built from
`Dockerfile.mcp` and pushed to **Artifact Registry**
(`us-central1-docker.pkg.dev`) — not the deprecated `gcr.io` Container
Registry, which stopped accepting pushes in 2026. `MCP_AUTH_TOKEN` is
stored in **Secret Manager**, never as a plaintext env var.

```bash
gcloud builds submit --config cloudbuild.yaml .

gcloud run deploy sales-intelligence-mcp \
  --image us-central1-docker.pkg.dev/<project-id>/sales-mcp-repo/sales-intelligence-mcp \
  --region us-central1 \
  --allow-unauthenticated \
  --set-secrets=MCP_AUTH_TOKEN=mcp-auth-token:latest \
  --set-env-vars=ALLOWED_HOST=<your-service>.run.app
```

`--allow-unauthenticated` controls platform-level (Cloud Run IAM) access,
not application-level auth — every request still needs a valid bearer
token to reach any tool, enforced by `mcp_server.py` itself.

### Connecting Claude Desktop to the remote server

Claude Desktop's `claude_desktop_config.json` only understands local
(`stdio`) processes — it cannot be pointed at a remote `url` directly, and
its built-in "Add custom connector" flow requires OAuth (bearer/API-key
auth is a beta feature with limited access as of Aug 2026). The workaround
is a small local stdio↔HTTP bridge script that forwards messages to the
remote server, carrying the `Authorization` header and the MCP session ID:

```json
{
  "mcpServers": {
    "sales-intelligence-agent": {
      "command": "<path-to-python>",
      "args": ["<path-to-bridge-script>"],
      "env": {
        "MCP_AUTH_TOKEN": "<your-token>",
        "MCP_REMOTE_URL": "https://<your-service>.run.app/mcp"
      }
    }
  }
}
```

For any other MCP client with native remote support (Cursor, Windsurf, VS
Code+Cline), no bridge is needed — configure `url` + `headers` directly.

## 🧪 Tests

```bash
# Unit tests for all 10 tools (31 tests)
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

**Author:** Bernardo Mantilla
**License:** MIT