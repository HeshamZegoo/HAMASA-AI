# HAMASA AI — حماصة

Your Personal AI Companion.

A web-first Arabic/English AI companion with a premium dark interface, animated orb/avatar, and browser-local conversation history.

## Current architecture
- **Frontend:** static HTML/CSS/JavaScript, deployable to GitHub Pages.
- **Backend:** FastAPI, deployable to Railway.
- **AI:** OpenAI-compatible Chat Completions API. Configure a provider and model through server environment variables; Ollama can be used by setting `AI_BASE_URL` to an Ollama-compatible endpoint reachable by the backend.
- **Conversation history:** stored in browser local storage, so conversations remain available in the same browser/device. The API receives the latest 40 messages for continuity; server-side account sync is not enabled.
- **Attachments:** supports images (through an image-capable provider model), PDF, DOCX, TXT, Markdown, CSV, JSON and XML. Files are limited to 8 MB each and five per message. PDF and DOCX text extraction runs on the backend.

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
- `DATABASE_URL` — reserved for future database integration; PostgreSQL conversation persistence is not implemented in this starter.
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
