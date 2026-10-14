# DocBot — Document RAG Chatbot

Upload PDF / DOCX / TXT files, ask questions, get answers **only from the selected document**, with page-level citations.
Backend: FastAPI + ChromaDB + local sentence-transformers + Groq. Frontend: React + Vite + Tailwind + Vanta.js (birds intro → waves background).

```
rag-chatbot/
├── README.md                  <- this file (setup + run)
├── HOW_IT_WORKS.md            <- where each feature lives and how it works
├── .gitignore                 <- keeps .env, data/, node_modules out of git
├── backend/
│   ├── requirements.txt       <- runtime deps (pinned)
│   ├── requirements-dev.txt   <- + pytest, reportlab
│   ├── .env.example           <- copy to .env and add your Groq key
│   ├── data/                  <- created at runtime: app.db (SQLite) + chroma/ (vectors)
│   ├── app/
│   │   ├── main.py            <- app factory, CORS, size guard, static frontend
│   │   ├── config.py          <- settings from env / .env
│   │   ├── container.py       <- holds db, vector store, embedder, llm
│   │   ├── security.py        <- owner id check + rate limiter
│   │   ├── errors.py          <- one JSON error shape
│   │   ├── db.py              <- SQLite document metadata
│   │   ├── schemas.py         <- request/response models + validation
│   │   ├── routes/            <- documents.py, chat.py, health.py (HTTP only)
│   │   └── services/
│   │       ├── extractor.py   <- validate + extract text (PDF/DOCX/TXT)
│   │       ├── chunker.py     <- overlapping recursive splitter
│   │       ├── embedder.py    <- local sentence-transformers
│   │       ├── vector_store.py<- ChromaDB (persistent, filtered)
│   │       ├── ingest.py      <- upload -> chunks -> vectors pipeline
│   │       ├── chat.py        <- rewrite -> retrieve -> answer -> verify citations
│   │       ├── llm.py         <- Groq client
│   │       └── prompts.py     <- all prompt text
│   └── tests/                 <- 33 automated tests
└── frontend/
    ├── package.json, vite.config.js, index.html
    └── src/
        ├── App.jsx            <- state, intro timing, polling, upload/chat logic
        ├── api.js             <- axios client (adds X-Owner-Id)
        ├── index.css          <- theme tokens + glass style
        └── components/ Intro.jsx (birds), WavesBackground.jsx, Sidebar.jsx, ChatPanel.jsx
```

## Prerequisites
- Python 3.10+ (tested on 3.12), Node.js 18+, VS Code
- A Groq API key from https://console.groq.com/keys
- Internet on first run (the ~90 MB embedding model downloads once; PyTorch is also a large install)

## Run it (VS Code: open the `rag-chatbot` folder, then open TWO terminals with Ctrl+`)

### Terminal 1 — backend

**Windows (PowerShell)**
```powershell
cd backend
python -m venv .venv
# if activation is blocked:  Set-ExecutionPolicy -Scope Process Bypass
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
notepad .env          # paste your key after GROQ_API_KEY=  then save
uvicorn app.main:create_app --factory --reload --port 8000
```

**macOS / Linux**
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env             # paste your key after GROQ_API_KEY=  then save
uvicorn app.main:create_app --factory --reload --port 8000
```
Check it: open http://localhost:8000/api/health — you should see `"llm_configured": true`.

### Terminal 2 — frontend
```bash
cd frontend
npm install
npm run dev
```
Open **http://localhost:5173**. Birds fly for 3 seconds, then the waves take over.

## Run the tests
```bash
cd backend
pip install -r requirements-dev.txt
pytest -q
```
The tests use a fake embedder and fake LLM so they run offline. See HOW_IT_WORKS.md section 6 for what they do and don't prove.

## Single-server mode (optional)
```bash
cd frontend && npm run build        # creates frontend/dist
cd ../backend && uvicorn app.main:create_app --factory --port 8000
```
Now http://localhost:8000 serves both the UI and the API.

## Troubleshooting
| Symptom | Fix |
|---|---|
| Red banner "Chat is disabled" | `GROQ_API_KEY` missing in `backend/.env`; restart backend |
| "Groq rejected the API key" | Key is wrong/revoked; create a new one at console.groq.com/keys |
| "Model ... was not found" | Groq retired it; pick a current one from console.groq.com/docs/models and set `GROQ_MODEL` |
| Upload stuck on failed: "embedding model could not be loaded" | First run needs internet to download the model; reconnect and re-upload |
| "Can't reach the server" | Backend isn't running on port 8000 |
| Answers say "not enough information" too often | Lower `MIN_SIMILARITY` in `.env` (try 0.18) |
| Wrong answers slip through | Raise `MIN_SIMILARITY` (try 0.32) |
| Black screen, no animation | Browser/GPU has WebGL disabled; the app still works, check the console warning |
