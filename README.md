# Sales Intelligence Agent

> Production-ready conversational sales analysis agent. Enables natural language queries on enterprise sales datasets, eliminating the dependency on SQL or BI dashboards for non-technical users.

## 🎯 Architectural Variants

This repository contains the **LangGraph + Groq variant**. I also developed an equivalent variant using **Semantic Kernel + Azure OpenAI GPT-4o** in a separate repository, evaluated side-by-side via a real latency benchmark.

| Variant | LLM | Avg. Latency | Cost | SLA |
|---|---|---|---|---|
| **LangGraph + Groq** (this repo) | LLaMA 3.3-70b | ~6.5s | $0.00 | No SLA |
| Semantic Kernel + Azure OpenAI | GPT-4o | Variable | ~$0.003/request | 99.9% uptime |

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
  Groq      9 Tools
 (LLaMA)   (Pandas)
```

## 📦 Tech Stack

| Layer | Technology |
|---|---|
| **Orchestration** | LangGraph, LangChain |
| **LLM** | Groq Cloud API (LLaMA 3.3-70b-versatile) |
| **API** | FastAPI, Uvicorn, Pydantic |
| **Auth** | JWT (PyJWT/jose), Passlib/bcrypt, OAuth2PasswordBearer |
| **Data Analysis** | Pandas |
| **Memory** | In-Session (RAM), Persistent (JSON), Cosmos DB (Azure) |
| **Infrastructure** | Docker, Azure Container Apps |
| **CI/CD** | GitHub Actions |
| **Testing** | Pytest |
| **Benchmark** | httpx, Rich, pandas |

## 🗂️ Project Structure

```
sales-intelligence-agent/
├── app/
│   ├── main.py              # FastAPI - HTTP endpoints + JWT Auth
│   ├── agent_langgraph.py   # LangGraph agent (state graph)
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
├── benchmark.py             # Benchmark: LangGraph vs Semantic Kernel
├── .github/workflows/
│   └── ci-cd.yml            # CI/CD: Tests → Docker Build → Azure Deploy
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
curl -X POST http://localhost:8000/auth/token   -d "username=admin&password=admin123"

# 2. Query the agent
curl -X POST http://localhost:8000/chat   -H "Authorization: Bearer <TOKEN>"   -H "Content-Type: application/json"   -d '{"session_id": "user-123", "question": "Who is the top seller?"}'
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

## 🧪 Tests

```bash
# Unit tests for tools (30+ tests)
pytest tests/test_tools.py -v

# API integration tests
pytest tests/test_api.py -v

# Truncated memory test
python tests/test_memoria.py
```

## 📊 Benchmark

The `benchmark.py` script runs the same 10 questions against both variants (LangGraph/Groq on `:8000` and Semantic Kernel/Azure OpenAI on `:8001`), measuring real latency and generating a comparison table + CSV export.

```bash
# Run both services in parallel
uvicorn app.main:app --port 8000          # LangGraph
# (in other repo) uvicorn app.main:app --port 8001  # Semantic Kernel

python benchmark.py
```

## 🐳 Docker

```bash
docker build -t sales-agent .
docker run -p 8000:8000 -e GROQ_API_KEY=xxx sales-agent
```

## ☁️ Deploy on Azure Container Apps

The CI/CD pipeline in `.github/workflows/ci-cd.yml` automates:

1. **Tests** → runs `pytest tests/test_tools.py`
2. **Build & Push** → builds Docker image and pushes to Azure Container Registry
3. **Deploy** → updates Azure Container Apps with the new image

```bash
# Required GitHub Secrets:
# AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_TENANT_ID, AZURE_SUBSCRIPTION_ID
```

## ⚙️ Local Setup

```bash
# 1. Clone and install
pip install -r requirements.txt

# 2. Configure environment variables
cp .env.example .env
# Edit .env: GROQ_API_KEY, GROQ_MODEL, JWT_SECRET_KEY, etc.

# 3. Run
uvicorn app.main:app --reload

# 4. Interactive documentation
open http://localhost:8000/docs
```

## 📄 Environment Variables

| Variable | Description | Default |
|---|---|---|
| `GROQ_API_KEY` | Groq API key | — |
| `GROQ_MODEL` | Groq model | `llama-3.3-70b-versatile` |
| `JWT_SECRET_KEY` | Secret key for JWT signing | `dev-secret-key-change-in-production` |
| `JWT_EXPIRE_MINUTES` | Token expiration in minutes | `60` |
| `MEMORY_BACKEND` | Memory backend (`json` / `cosmos`) | `json` |
| `COSMOS_ENDPOINT` | Azure Cosmos DB endpoint | — |
| `COSMOS_KEY` | Azure Cosmos DB key | — |
| `COSMOS_DATABASE` | Database name | `sales-agent-db` |
| `COSMOS_CONTAINER` | Container name | `memory` |

## 📝 Notes

- The **Semantic Kernel + Azure OpenAI GPT-4o** variant is in a separate repository. Both variants share the same 9 Pandas tools and the same FastAPI, enabling objective comparison.
- History truncation to 10 messages keeps token consumption stable at ~4,000-6,000 tokens per conversation.
- Docker healthcheck verifies the service responds before marking the container as healthy.

---

**Author:** Bernardo Mantilla Afanador  
**License:** MIT
