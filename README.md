# 🤖 Sales Agent API

Agente de análisis de ventas construido con **LangGraph + Groq + FastAPI**.  
El agente recibe preguntas en lenguaje natural, decide qué datos consultar y responde con insights del negocio.

## Stack

| Componente | Tecnología |
|---|---|
| Orquestación del agente | LangGraph |
| LLM | Groq (compound-beta) |
| API | FastAPI |
| Análisis de datos | Pandas |
| Deploy local | Uvicorn |
| Deploy cloud | Azure Container Apps |

## Estructura

```
sales-agent/
├── app/
│   ├── main.py              # FastAPI - endpoints HTTP
│   ├── agent_langgraph.py   # Agente LangGraph
│   └── tools.py             # Funciones de análisis de datos
├── data/
│   └── ventas.csv           # Datos de ventas simulados
├── tests/
│   └── test_agent.py        # Tests del agente
├── .env                     # Variables de entorno (no commitear)
├── requirements.txt
├── Dockerfile
└── README.md
```

## Setup local

```bash
# 1. Clonar e instalar dependencias
pip install -r requirements.txt

# 2. Configurar variables de entorno
cp .env .env.local
# Editar .env y agregar tu GROQ_API_KEY

# 3. Correr el servidor
uvicorn app.main:app --reload

# 4. Abrir la documentación
# http://localhost:8000/docs
```

## Endpoints

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/` | Health check |
| GET | `/ventas/resumen` | Resumen general de ventas |
| POST | `/chat` | Conversar con el agente |

### Ejemplo de uso

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "¿Cuál es el vendedor con más ventas?"}'
```

## Flujo del agente (LangGraph)

```
Usuario pregunta
      ↓
   Nodo LLM
  (¿uso tool?)
      ↓
  ¿tool_calls?
   /        \
  Sí         No
  ↓           ↓
Nodo Tools   END
  ↓
Nodo LLM
(genera respuesta final)
      ↓
    END
```

## Deploy en Azure Container Apps

```bash
# 1. Build y push de la imagen
az acr build --registry <tu-registry> --image sales-agent:latest .

# 2. Crear Container App
az containerapp create \
  --name sales-agent \
  --resource-group <tu-rg> \
  --environment <tu-env> \
  --image <tu-registry>.azurecr.io/sales-agent:latest \
  --target-port 8000 \
  --ingress external \
  --env-vars GROQ_API_KEY=secretref:groq-key GROQ_MODEL=compound-beta
```
