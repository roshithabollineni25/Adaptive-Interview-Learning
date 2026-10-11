# Adaptive Interview Intelligence

Adaptive Interview Intelligence is an AI-augmented, evidence-based recruitment platform built for the **Google Student Club Welcome Hackathon 2026**.

The system dynamically adapts technical interview questions in real-time according to candidate performance, benchmarks candidate competency profiles against job requirements, monitors proctoring integrity events, and equips recruiters with detailed interview dossiers and evidence quotes to make informed hiring decisions.

---

## 🛠️ Technology Stack

- **Frontend**: React 19, TypeScript, Vite, React Router, Lucide Icons
- **Backend**: FastAPI, Python 3.12, Uvicorn, Pydantic v2
- **Database & ORM**: PostgreSQL (with SQLite portable dev fallback), SQLAlchemy 2.0, Alembic Migrations
- **AI / LLM Integration**: Google Gemini API (`google-genai` SDK) / OpenAI API (Backend only, never exposed to client)
- **Document Parsing**: `pypdf` & `python-docx` for resume extraction

---

## 📁 Repository Structure

```
├── .env.example              # Sample environment config with safe placeholders
├── backend/                  # FastAPI Application
│   ├── alembic/              # Database migration scripts
│   │   └── versions/         # Version migration files
│   ├── app/
│   │   ├── api/              # Routers (health, auth, recruitment, interview)
│   │   ├── core/             # Configuration, database engine, JWT security
│   │   ├── models/           # SQLAlchemy database entities
│   │   ├── schemas/          # Pydantic validation schemas
│   │   ├── services/         # LLM service, document parser, adaptive engine
│   │   └── main.py           # FastAPI entrypoint
│   ├── tests/                # Pytest unit & integration tests
│   └── requirements.txt      # Python dependencies
├── frontend/                 # React + Vite + TypeScript Application
│   ├── src/
│   │   ├── api/              # Centralized typed Axios API client
│   │   ├── components/       # Reusable components (HealthCheck, UI badges)
│   │   ├── pages/            # Recruiter Dashboard, Candidate Experience, Dossier
│   │   ├── types/            # TypeScript data models and interfaces
│   │   ├── App.tsx           # Router navigation
│   │   └── index.css         # UI design styling
│   └── package.json          # Node dependencies
└── README.md
```

---

## 🚀 Setup & Execution Guide

### Prerequisites
- Python 3.10+
- Node.js 18+ and npm
- PostgreSQL (Optional: SQLite default allows zero-setup instant local running)

### 1. Environment Configuration

Copy `.env.example` to create your local `.env`:

```bash
cp .env.example .env
```

To enable live Google Gemini evaluations, populate your Gemini API key in `.env`:
```env
LLM_PROVIDER=gemini
GEMINI_API_KEY=AIzaSy...
GEMINI_MODEL=gemini-2.5-flash
```

*(Note: If no LLM key is configured, the system uses its built-in fallback engine, allowing full workflow testing without failure).*

---

### 2. Backend Setup & Run

Create and activate a virtual environment:

```bash
# Windows PowerShell
python -m venv venv
.\venv\Scripts\Activate.ps1

# Linux / macOS
python3 -m venv venv
source venv/bin/activate
```

Install backend dependencies:
```bash
pip install -r backend/requirements.txt
```

Run database migrations:
```bash
cd backend
alembic upgrade head
```

Run backend server:
```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
API Documentation will be live at: `http://127.0.0.1:8000/docs`

---

### 3. Frontend Setup & Run

In a new terminal window:

```bash
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173` in your browser.

---

### 4. Running Backend Tests

```bash
cd backend
python -m pytest -p no:cacheprovider tests/
```

---

## 🧭 Core Workflow

1. **System Health Check**: Visit `http://127.0.0.1:5173/` to view live backend connection, database migration status, and LLM configuration.
2. **Recruiter Authentication**: Register or sign in at `/login`.
3. **Job Specification**: Post a new role with required technical competencies.
4. **Candidate Resume Upload**: Upload PDF or DOCX resumes; the engine parses skills, education, and experience.
5. **Interview Session Generation**: Launch an adaptive session to generate a candidate interview link.
6. **Candidate Adaptive Experience**: Candidates access their unique URL, face adaptive difficulty questions, and trigger proctor integrity telemetry (tab switches, pastes).
7. **Recruiter Review & Decision**: Inspect candidate dossiers, evidence quotes, resume-to-interview skill gaps, and record final hiring decisions.
