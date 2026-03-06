# Jarvis — Quick Start

## Prerequisites

- Python 3.11+
- Node.js 20.19+ (22 recommended)

## Environment Variables

Copy the example and fill in as needed:

```bash
cp .env.example .env
```

| Variable | Default | Description |
|---|---|---|
| `LLM_AWS_REGION` | `eu-west-1` | AWS region for Bedrock |
| `LLM_MODEL_ID` | `eu.anthropic.claude-sonnet-4-6` | Bedrock model inference profile |
| `LLM_MAX_TOKENS` | `4096` | Max tokens per LLM response |
| `LLM_MAX_ITERATIONS` | `10` | Max agentic tool-call loops |
| `HOST` | `0.0.0.0` | Backend bind address |
| `PORT` | `8000` | Backend port |

The AI assistant requires AWS credentials configured (e.g. `AWS_PROFILE` or `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`) with Bedrock access in the configured region.

## Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

API runs at `http://localhost:8000`. Verify with:

```bash
curl http://localhost:8000/api/kpi?year=2025
```

### Endpoints

| Route | Description |
|---|---|
| `GET /api/kpi` | KPI summary strip |
| `GET /api/brand` | Revenue by Brand → TA → Total |
| `GET /api/region` | Revenue by Market → Region → Total |
| `GET /api/unit` | Expenses by Sub-unit → Unit → Total |
| `GET /api/market` | Competitive market share data |
| `POST /api/assistant` | AI assistant (SSE stream) |

All endpoints accept `?year=2025&quarter=Q2` query params.

## Frontend

```bash
cd frontend
npm install
npm run dev
```

App runs at `http://localhost:5173`. The Vite dev server proxies `/api` requests to the backend.

## Both at once

Open two terminals:

```bash
# Terminal 1
cd backend && uvicorn main:app --reload --port 8000

# Terminal 2
cd frontend && npm run dev
```

Then open `http://localhost:5173`.
