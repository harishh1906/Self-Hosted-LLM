# 🛡️ Self-Hosted AI Security Advisory Engine

<p align="center">
  <img src="https://img.shields.io/badge/FastAPI-0.100+-green?style=for-the-badge&logo=fastapi" />
  <img src="https://img.shields.io/badge/Ollama-Phi--3_Mini-blue?style=for-the-badge" />
  <img src="https://img.shields.io/badge/PostgreSQL-15-blue?style=for-the-badge&logo=postgresql" />
  <img src="https://img.shields.io/badge/Qdrant-Vector_DB-purple?style=for-the-badge" />
  <img src="https://img.shields.io/badge/Docker-Compose-2496ED?style=for-the-badge&logo=docker" />
  <img src="https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge" />
</p>

> **A fully self-hosted, on-premises AI engine that analyzes security findings from vulnerability scanners and generates structured advisory reports — all without sending data to any cloud AI provider.**


AI takes raw security findings from scanners (Burp Suite, Nessus, OWASP ZAP, etc.) and uses a **local LLM (Phi-3 Mini via Ollama)** to generate:

- 📊 **Risk Summary** — plain-language explanation of the threat
- 💥 **Business Impact** — financial / reputational consequences
- 🎯 **Severity Classification** — Low / Medium / High / Critical
- 🔧 **Remediation Steps** — concrete, actionable fix instructions
- 📈 **Risk Score** — deterministic 0–100 score with SLA assignment
- 🔍 **Confidence Score** — how confident the model is in its advisory

All AI output is enriched with **Retrieval-Augmented Generation (RAG)** from a security knowledge base (CWE database) stored in Qdrant.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    AI LLM Stack                       │
│                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │   FastAPI    │───▶│   Ollama     │    │   Qdrant     │  │
│  │  Advisory    │    │  Phi-3 Mini  │    │  Vector DB   │  │
│  │    API       │    │  (Local LLM) │    │  (RAG Store) │  │
│  └──────┬───────┘    └──────────────┘    └──────────────┘  │
│         │                                                    │
│  ┌──────▼───────┐    ┌──────────────┐    ┌──────────────┐  │
│  │  PostgreSQL  │    │  JWT + HMAC  │    │ Drift Detect │  │
│  │  (Audit/DB)  │    │    Auth      │    │  + Metrics   │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Key Components

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **API Server** | FastAPI (Python) | REST API, routing, middleware |
| **Frontend UI** | React + Vite | Premium interactive UI with glassmorphism |
| **Local LLM** | Ollama + Phi-3 Mini | On-prem advisory generation |
| **Vector DB** | Qdrant | RAG knowledge retrieval |
| **Database** | PostgreSQL 15 | Audit logs, analytics, policies |
| **Auth** | JWT + HMAC | User and service-to-service auth |
| **Drift Detection** | Custom engine | AI output quality monitoring |
| **Model Optimization** | Auto-promotion engine | Automatic model selection |
| **Circuit Breaker** | Custom implementation | Fault tolerance |

---

## ✨ Features

### 🔐 Security & Auth
- **Dual authentication**: JWT tokens for users, HMAC signatures for service-to-service
- **Multi-tenancy**: Complete org-level isolation of data, policies, and RAG context
- **Rate limiting**: Per-IP rate limiting with configurable limits
- **Input validation**: Strict Pydantic schemas with allowlist validation

### 🤖 AI & LLM
- **Local-first**: Phi-3 Mini runs entirely on your infrastructure — no data leaves your network
- **RAG-enhanced**: Security knowledge base (CWE) retrieved from Qdrant for context
- **Demo mode**: Returns mock advisories when Ollama is unavailable (for showcasing)
- **Model hot-reload**: Switch models without restarting the service
- **Fallback logic**: Graceful degradation if primary model fails

### 📊 Observability & Governance
- **Drift detection**: Monitors AI output quality over time (confidence, severity distribution)
- **Audit trail**: Every request logged with full context for compliance
- **Cost analytics**: Token usage, latency, and cost tracking per org/policy
- **Model health**: Per-model latency, SLA violations, fallback rates
- **Auto model promotion**: Automatically promotes better-performing models
- **Circuit breaker**: Opens circuit on repeated failures, prevents cascade

### 📝 Policy Governance
- **Per-org policy profiles**: Configure risk tolerance, verbosity, compliance mode, remediation style
- **Compliance modes**: SOC2, ISO 27001, HIPAA-aware advisory generation
- **Scanner integration**: Per-request policy override from scanner metadata

---

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- 8GB+ RAM (for Phi-3 Mini)
- (Optional) NVIDIA GPU for faster inference

### 1. Clone the Repository
```bash
git clone https://github.com/harishh1906/Self-Hosted-LLM.git
cd Self-Hosted-LLM
```

### 2. Configure Environment
```bash
cp .env.example .env
# Edit .env and set your SECRET keys
nano .env
```

**Required env vars:**
```
SERVICE_SECRET_KEY=<random 32+ char string>
JWT_SECRET_KEY=<random 32+ char string>
```

### 3. Start the Stack
```bash
docker-compose up -d
```

This starts:
- 🤖 **Ollama** on port `11434`
- 🛡️ **Advisory API** on port `8000`
- 🔍 **Qdrant** on port `6333`
- 🐘 **PostgreSQL** on port `5432`

### 4. Pull the LLM Model
```bash
docker exec virtue-ollama ollama pull phi3:mini
```

### 5. Start the React Frontend

Open a new terminal and start the UI:
```bash
cd frontend
npm install
npm run dev
```

The beautiful interactive UI will now be running at **http://localhost:5173**. 
Simply click **"Fill Sample Data"** and then **"Generate AI Advisory"** to test it out!

### 6. Test the API directly (Optional)
```bash
# Get a token
TOKEN=$(curl -s -X POST "http://localhost:8000/login?username=demo&org_id=demo-org" | jq -r .access_token)

# Analyze a finding
curl -X POST http://localhost:8000/analyze \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "SQL Injection in login form",
    "description": "User input is concatenated directly into SQL queries without parameterization.",
    "severity": "Critical",
    "affected_asset": "Authentication Service",
    "scanner": "burp_suite",
    "org_id": "demo-org"
  }'
```

### 7. View API Docs
Open `http://localhost:8000/docs` in your browser.

---

## 📡 API Reference

### Authentication

#### `POST /login`
Generate a JWT token for testing.
```bash
curl -X POST "http://localhost:8000/login?username=myuser&org_id=my-org&role=security_analyst"
```
Response:
```json
{"access_token": "eyJ...", "token_type": "bearer"}
```

### Analysis

#### `POST /analyze` 🔒 *Requires Auth*
Analyze a security finding and get an AI-generated advisory.

**Request body:**
```json
{
  "title": "SQL Injection in login endpoint",
  "description": "Detailed description of the finding...",
  "severity": "Critical",
  "evidence": "Proof of concept or scanner output",
  "affected_asset": "Authentication Service",
  "scanner": "burp_suite",
  "org_id": "your-org-id",
  "risk_tolerance": "high",
  "verbosity": "detailed",
  "compliance_mode": "soc2"
}
```

**Response:**
```json
{
  "finding": "SQL Injection in login endpoint",
  "advisory": {
    "risk_summary": "...",
    "business_impact": "...",
    "severity": "Critical",
    "remediation_steps": ["Step 1", "Step 2", "..."],
    "confidence": 0.92
  },
  "risk_assessment": {
    "risk_score": 91,
    "risk_level": "Critical",
    "sla": "24 hours",
    "justification": "..."
  }
}
```

#### `POST /demo/analyze` 🌐 *No Auth Required*
Returns a pre-generated advisory for live demos. Rate limited.

### Policy Management

#### `GET /api/v1/ai/governance/policy/{org_id}` 🔒
Get the AI policy profile for an organization.

#### `POST /api/v1/ai/governance/policy` 🔒
Create or update an AI policy profile.

```json
{
  "org_id": "my-org",
  "risk_tolerance": "high",
  "verbosity": "detailed",
  "compliance_mode": "soc2",
  "remediation_style": "strict"
}
```

#### `DELETE /api/v1/ai/governance/policy/{org_id}` 🔒
Reset policy to system defaults.

### Governance & Analytics

| Endpoint | Description |
|----------|-------------|
| `GET /api/v1/ai/governance/policy-cost-summary` | Token cost by policy |
| `GET /api/v1/ai/governance/policy-latency-summary` | Latency stats by policy |
| `GET /api/v1/ai/governance/model-optimization-recommendations` | Model upgrade recommendations |
| `GET /api/v1/ai/governance/active-models` | Currently active models per org |
| `POST /api/v1/ai/governance/model-hot-reload` | Switch models without restart |

### Internal Monitoring

| Endpoint | Description |
|----------|-------------|
| `GET /internal/health` | Full health check with dependency status |
| `GET /internal/metrics` | Request counts, latency percentiles |
| `GET /internal/model-health` | Per-model health metrics |
| `GET /internal/optimization-insights` | AI performance intelligence |

---

## 🧪 Running Tests

```bash
cd advisory-api

# Install test dependencies
pip install pytest httpx

# Set environment variables for tests
export DEMO_MODE=true
export SERVICE_SECRET_KEY=test-secret-key-32-chars-minimum
export JWT_SECRET_KEY=test-jwt-secret-32-chars-minimum
export DATABASE_URL=sqlite:///./test.db

# Run all tests
pytest tests/ -v

# Run with coverage
pip install pytest-cov
pytest tests/ -v --cov=app --cov-report=html
```

**Test coverage includes:**
- ✅ Schema validation (15+ cases)
- ✅ Health endpoints
- ✅ JWT auth (create, decode, expire, invalid)
- ✅ /analyze endpoint (success, auth failure, org mismatch)
- ✅ /demo/analyze (no auth, rate limiting)
- ✅ Risk engine (scoring, SLA, criticality)
- ✅ Circuit breaker (state machine)
- ✅ Internal metrics
- ✅ Policy CRUD (create, get, forbidden)

---

## ⚙️ Configuration Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `SERVICE_SECRET_KEY` | **Required** | HMAC secret for service auth |
| `JWT_SECRET_KEY` | **Required** | JWT signing secret |
| `DATABASE_URL` | `postgresql://virtue:virtuepass@postgres:5432/virtue` | PostgreSQL connection |
| `QDRANT_HOST` | `qdrant` | Qdrant hostname |
| `QDRANT_PORT` | `6333` | Qdrant port |
| `OLLAMA_URL` | `http://ollama:11434/api/generate` | Ollama API URL |
| `MODEL_VERSION` | `phi3:mini` | LLM model to use |
| `DEMO_MODE` | `false` | Return mock responses (no Ollama needed) |
| `SLA_LATENCY_THRESHOLD_MS` | `2000.0` | SLA breach threshold in ms |
| `RATE_LIMIT_PER_MINUTE` | `60` | API rate limit per IP |
| `ALLOWED_ORIGINS` | `*` | CORS allowed origins |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

---

## 🌐 Deployment

### Deploy to Railway (Recommended for Demo)

1. Fork this repository
2. Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub
3. Select your fork
4. Add environment variables:
   - `SERVICE_SECRET_KEY` = (random string)
   - `JWT_SECRET_KEY` = (random string)
   - `DEMO_MODE` = `true` (for demo without Ollama)
5. Deploy! Railway auto-detects the `railway.toml`

### Deploy to a VPS (Self-Hosted with Full Ollama)

```bash
# On your server (Ubuntu 22.04+)
git clone https://github.com/harishh1906/Self-Hosted-LLM.git
cd Self-Hosted-LLM
cp .env.example .env
# Edit .env with production secrets
docker-compose up -d
docker exec virtue-ollama ollama pull phi3:mini
```

Access via `http://your-server-ip:8000`

---

## 📁 Project Structure

```
.
├── docker-compose.yml          # Full stack orchestration
├── .env.example                # Environment variable template
├── railway.toml                # Railway deployment config
├── frontend/                   # 🌟 NEW: Beautiful React UI
│   ├── src/
│   │   ├── App.jsx             # Main dashboard UI
│   │   └── index.css           # Premium glassmorphism styles
│   ├── package.json            # React deps
│   └── vite.config.js          # Vite configuration
└── advisory-api/
    ├── Dockerfile              # Production container
    ├── requirements.txt        # Python dependencies
    └── app/
        ├── main.py             # FastAPI app, all routes (1100+ lines)
        ├── advisory_engine.py  # LLM orchestration, policy shaping
        ├── ollama_client.py    # Ollama API client + demo mode
        ├── schemas.py          # Pydantic input/output models
        ├── config.py           # Environment-aware configuration
        ├── risk_engine.py      # Deterministic risk scoring
        ├── prompt_shaper.py    # Policy-aware prompt templating
        ├── vector_store.py     # Qdrant RAG operations
        ├── context_retriever.py# RAG context retrieval
        ├── circuit_breaker.py  # Fault tolerance
        ├── metrics.py          # Latency percentile tracking
        ├── health.py           # Readiness checks
        ├── model_manager.py    # Hot-reload model config
        ├── model_health.py     # Per-model health tracking
        ├── drift/
        │   └── detector.py     # AI output drift detection
        ├── analytics/
        │   └── service.py      # Cost/latency/success analytics
        ├── optimization/
        │   └── engine.py       # Auto model promotion
        ├── auth/
        │   ├── jwt.py          # JWT creation/validation
        │   ├── service_auth.py # HMAC service auth
        │   └── dependencies.py # FastAPI auth dependencies
        ├── db/
        │   ├── models.py       # SQLAlchemy ORM models (7 tables)
        │   ├── database.py     # Connection pool setup
        │   └── crud.py         # Database operations
        └── tests/
            └── test_advisory.py # 50+ test cases
```

---

## 🔒 Security Considerations

- **No data leaves your network** — LLM runs locally via Ollama
- **Secrets via environment variables** — never hardcoded
- **Multi-tenant data isolation** — all queries filtered by org_id
- **JWT expiry** — configurable token lifetime
- **HMAC service auth** — prevents unauthorized service calls
- **Input sanitization** — Pydantic validators on all inputs
- **Non-root Docker user** — container runs as unprivileged user
- **Rate limiting** — prevents API abuse

---

## 📜 License

MIT License — see [LICENSE](LICENSE) for details.

---

## 👤 Author

**Harish** — [@harishh1906](https://github.com/harishh1906)

> Built as part of the security platform — a production AI-powered security advisory engine for enterprise vulnerability management.

---

*⭐ Star this repo if you found it useful!*
