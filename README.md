# POCA — Personal Organization and Cheeky Aid

A private, voice-first AI companion and personal productivity assistant.

## Stack

| Layer | Tech |
|---|---|
| Frontend | React PWA (Vite) — deployed on Vercel |
| Backend | Python FastAPI — deployed on Google Cloud Run |
| Database | PostgreSQL + pgvector (Cloud SQL) |
| AI | Google Gemini (gemini-2.0-flash + Gemini Live API) |
| Auth | Google OAuth 2.0 |
| Calendar | Google Calendar API |

---

## Quick Start

### 1. Backend

```bash
cd backend

# Copy env file and fill in your keys
cp .env.example .env

# Create a virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run database migrations (requires PostgreSQL running with pgvector)
alembic upgrade head

# Start the dev server
uvicorn app.main:app --reload
```

Backend runs at http://localhost:8000

### 2. Frontend

```bash
cd frontend

# Copy env file
cp .env.example .env

# Install dependencies
npm install

# Start dev server
npm run dev
```

Frontend runs at http://localhost:5173

---

## Environment Variables

### Backend (`backend/.env`)

| Variable | Description |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string (`postgresql+asyncpg://...`) |
| `GOOGLE_CLIENT_ID` | From Google Cloud Console OAuth credentials |
| `GOOGLE_CLIENT_SECRET` | From Google Cloud Console OAuth credentials |
| `GOOGLE_REDIRECT_URI` | `http://localhost:8000/auth/google/callback` (dev) |
| `GEMINI_API_KEY` | From Google AI Studio |
| `JWT_SECRET` | Long random secret for signing JWTs |
| `INVITE_PASSPHRASE` | Secret phrase users must enter to register |
| `FRONTEND_URL` | `http://localhost:5173` (dev) |

### Frontend (`frontend/.env`)

| Variable | Description |
|---|---|
| `VITE_API_URL` | Backend URL (default: `/api` which proxies to localhost:8000) |
| `VITE_WS_URL` | WebSocket URL (default: `ws://localhost:8000`) |

---

## Google Cloud Setup

### Google OAuth + Calendar API
1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a new project (or use existing)
3. Enable **Google Calendar API** and **Google People API**
4. Create OAuth 2.0 credentials (Web application type)
5. Add authorized redirect URIs:
   - `http://localhost:8000/auth/google/callback` (dev)
   - `https://your-cloud-run-url.run.app/auth/google/callback` (prod)

### PostgreSQL with pgvector
- Local: `docker run -e POSTGRES_PASSWORD=postgres -p 5432:5432 pgvector/pgvector:pg16`
- Cloud: Create a Cloud SQL instance with PostgreSQL 16

---

## Deployment

### Backend (Cloud Run)

```bash
cd backend
gcloud builds submit --tag gcr.io/YOUR_PROJECT/poca-backend
gcloud run deploy poca-backend \
  --image gcr.io/YOUR_PROJECT/poca-backend \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars DATABASE_URL=...,GEMINI_API_KEY=...,etc
```

### Frontend (Vercel)

1. Push to GitHub
2. Import repo in Vercel
3. Set environment variables
4. Update `vercel.json` with your Cloud Run URL

---

## Features

- **Voice-first chat** with Google Gemini (text fallback)
- **Dual-panel UI**: conversation left, dashboard right
- **Auto task extraction**: deadlines, action items, and priorities extracted from conversation
- **Google Calendar**: read events, add with confirmation
- **Persistent memory**: pgvector semantic search over conversation history
- **Context editor**: upload PDFs, link Google Docs/Sheets/URLs
- **Web search**: on-demand, results auto-expire after 7 days
- **Session opening sequence**: overdue check-in → today's priorities → open invitation
- **Weekly accomplishment summary** at first session of each week
- **Celebration sounds** on task completion
- **PWA**: installable on mobile
- **Invite-gated**: passphrase required at sign-up
