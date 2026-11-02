# LinkedIn SEO AI — React + FastAPI

## What this is
A full-stack LinkedIn profile optimizer:
- React + Vite frontend
- FastAPI backend
- Google Gemini for profile extraction, analysis and content generation
- Resend for emailing the finished report
- Supports manual form data plus LinkedIn PDF/screenshots

**Colab note:** Colab disconnects and is not a reliable permanent API host. This package moves the notebook workflow into a persistent FastAPI backend. You can continue experimenting in Colab, but the website calls FastAPI.

## Run locally

### Backend
Python 3.10+ required.

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and add your keys:
- `GEMINI_API_KEY` — required
- `RESEND_API_KEY` — required only for email
- `RESEND_FROM` — sender address on a domain verified in Resend

Start:
```bash
uvicorn app.main:app --reload --port 8000
```
API docs: http://localhost:8000/docs

### Frontend
Open a second terminal:
```bash
cd frontend
npm install
npm run dev
```
Open http://localhost:5173.

## Email caveat
Resend generally requires a domain you own and have verified for production sending. A free DuckDNS hostname is not an acceptable substitute. Without Resend configuration, analysis still works and the API clearly reports that email was not sent. Never put API keys in frontend code.

## Deploy
Deploy `backend/` as a persistent Python service and `frontend/` as a static Vite site. Set `VITE_API_BASE_URL` in the frontend hosting dashboard to the deployed backend URL. Configure Gemini and Resend secrets only on the backend.

## Scope / safety
No LinkedIn scraping, login, automatic profile edits, auto-posting or connection requests. Uploaded files are processed in memory, not permanently stored by this starter. Review AI-generated content and claims before publishing. Add authentication, rate limiting, retention controls and malware scanning before public launch.
