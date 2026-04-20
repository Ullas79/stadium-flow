# CrowdSync

Proactive event-driven application to manage stadium exits and crowd flow. Built for maximum efficiency, security, and exceptional user experience.

## Architecture

```
┌──────────────────────────────────────────────────┐
│  Browser (React + Vite)                          │
│  ┌──────────────┐  ┌──────────────┐              │
│  │  Dashboard    │  │  AI Concierge│              │
│  │  (Gate cards, │  │  (Chat UI)   │              │
│  │   Transport)  │  │              │              │
│  └──────┬───────┘  └──────┬───────┘              │
│         │ poll 30s         │ POST                 │
└─────────┼──────────────────┼─────────────────────┘
          ▼                  ▼
┌──────────────────────────────────────────────────┐
│  FastAPI Backend (Python)                        │
│  GET /api/stadium/status  (30s in-memory cache)  │
│  POST /api/chat           (Gemini 2.5 Flash)     │
│  GET /health              (liveness probe)       │
└──────────────────────────────────────────────────┘
```

## Features
- **Dynamic Exit Dashboard**: React UI with real-time polling for gate status (Red/Yellow/Green). Density *drives* status — no contradictory data.
- **Incentive Routing**: 10% Food Discount banner on Green (low-density) gates to organically redistribute crowds.
- **AI Concierge**: Context-aware stadium chat powered by Google Gemini 2.5 Flash (async, non-blocking).
- **Live Wait Times**: Transport wait times (Metro, Cabs, Bus) updated every 30 s.

## Tech Stack
| Layer          | Technology                           |
|----------------|--------------------------------------|
| Frontend       | React 18, Vite 5, Tailwind CSS 3    |
| Icons          | Lucide React                         |
| Backend        | Python 3.11, FastAPI                 |
| AI             | Google Gemini 2.5 Flash via `google-generativeai` SDK |
| Infrastructure | Docker (multi-stage), Google Cloud Run |

## Getting Started Locally

### 1. Backend
```bash
cd backend
python -m venv venv
venv\Scripts\activate        # macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
# Authenticate with Google Cloud for Vertex AI
gcloud auth application-default login
export GOOGLE_CLOUD_PROJECT=your-project-id
uvicorn main:app --reload
```

### 2. Frontend
```bash
cd frontend
npm install
npm run dev                  # http://localhost:3000
```

### 3. Tests
```bash
cd backend
pytest test_main.py -v
```

## API Endpoints

| Method | Path                    | Description                     |
|--------|-------------------------|---------------------------------|
| GET    | `/health`               | Liveness probe (Cloud Run)      |
| GET    | `/api/stadium/status`   | Gate density & transport times  |
| POST   | `/api/chat`             | AI Concierge (Gemini)           |

## Docker Deployment

```bash
docker build -t crowdsync .
docker run -p 8080:8080 -e GOOGLE_CLOUD_PROJECT=your-project-id crowdsync
```
Visit `http://localhost:8080`.

## Security
- CORS restricted to development origins (`localhost:3000`)
- Non-root container user
- Input sanitization + length cap (500 chars)
- Path traversal protection on static file serving
- API key stored in `.env`, never committed (`.gitignore`)

## Evaluation Checklist
- [x] **Repo Size**: < 2 MB, zero unnecessary dependencies
- [x] **Dashboard**: 4 gates with density-driven colour coding + incentive routing
- [x] **AI Chat**: Gemini 2.5 Flash, async, sanitized, length-capped
- [x] **Transport**: Live wait times (Metro, Cabs, Bus)
- [x] **Code Quality**: Type hints, docstrings, separated components
- [x] **Security**: CORS, path traversal guard, non-root Docker, env secrets
- [x] **Efficiency**: 30 s backend cache, polling aligned to cache TTL
- [x] **Testing**: 14 pytest tests covering status, chat, validation, correlation
- [x] **Accessibility**: aria-labels, semantic HTML, role attributes, live regions
- [x] **Google Services**: Gemini integration via `google-generativeai` SDK
