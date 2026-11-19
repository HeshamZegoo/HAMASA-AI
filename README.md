# HAMASA AI — حماصة

Your Personal AI Companion.

A web-first Arabic/English AI companion with a premium dark interface, animated orb/avatar, and browser-local conversation history.

## Current architecture
- **Frontend:** static HTML/CSS/JavaScript, deployable to GitHub Pages.
- **Backend:** FastAPI, deployable to Railway.
- **AI:** OpenAI-compatible Chat Completions API. Configure a provider and model through server environment variables; Ollama can be used by setting `AI_BASE_URL` to an Ollama-compatible endpoint reachable by the backend. Optional live web research uses Tavily when `TAVILY_API_KEY` is configured; HAMASA searches only when the latest user request asks for current information or external sources, then grounds the answer with source links.
- **Conversation history:** stored locally in the browser and synchronized to the account for signed-in users through the authenticated `/api/chats` endpoints. The API receives the latest 40 messages for response continuity.
- **Memory:** user-managed memories are stored per account, encrypted at rest when `MEMORY_ENCRYPTION_KEY` is configured, and included as relevant context by the frontend.
- **Attachments:** supports images (through an image-capable provider model), PDF, DOCX, TXT, Markdown, CSV, JSON and XML. See `backend/app/attachments.py` for current size and count limits.

## Quick start — frontend only
Open `index.html` through HTTPS (for example GitHub Pages).

## Run the backend locally
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```
Set `HAMASA_API_URL=http://localhost:8000` in the frontend configuration in `config.js` (or edit it before deployment).

## Backend environment
- `AI_API_KEY` — provider API key (keep secret; never put it in frontend code).
- `AI_BASE_URL` — OpenAI-compatible base URL, e.g. `https://api.openai.com/v1`.
- `AI_MODEL` — text model identifier supported by your provider.
- `AI_VISION_MODEL` — optional image-capable model identifier supported by the same OpenAI-compatible provider; required for image analysis.
- `DATABASE_URL` — PostgreSQL connection string for persistent accounts, sessions, conversations, and memories. SQLite is used only as a local-development fallback.
- `TAVILY_API_KEY` — optional Tavily key enabling live web research and source-grounded answers. Keep it server-side.
- `MEMORY_ENCRYPTION_KEY` — Fernet key required in production to encrypt saved memory.
- `JWT_SECRET` — signing secret (at least 32 characters) required for account authentication.
- `CORS_ORIGINS` — comma-separated allowed frontend origins.
- `APP_ENV` — `development` or `production`.

## Deploy
1. Enable GitHub Pages for this repository using **GitHub Actions** as the source. The workflow in `.github/workflows/pages.yml` publishes the static site.
2. Deploy the repository root to Railway; `railway.json` installs `backend/requirements.txt` and starts `backend.app.main:app`.
3. Add the environment variables above in Railway.
4. Set the frontend API URL in `config.js` to the deployed backend URL, then commit the change.
5. Set `CORS_ORIGINS` to the exact GitHub Pages origin.\n6. Confirm `/health` reports the chat provider configured, then test `/api/chat`.

## Security and limitations
- API credentials belong only on the backend.
- Do not expose private provider endpoints to untrusted users without authentication, rate limiting, and abuse controls.
- A local Ollama model is only local if the backend can reach the user's Ollama instance; a hosted Railway backend cannot automatically access a computer on the user's private network.
- No AI response is simulated. If no provider is configured, the API returns a clear configuration error.
