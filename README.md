# HAMASA AI — حماصة

Your Personal AI Companion.

A web-first Arabic/English AI companion with a premium dark interface, animated orb/avatar, push-to-talk voice, persistent conversations, and a provider-agnostic backend.

## Current architecture
- **Frontend:** static HTML/CSS/JavaScript, deployable to GitHub Pages.
- **Backend:** FastAPI, deployable to Railway.
- **AI:** OpenAI-compatible Chat Completions API. Configure a provider and model through server environment variables; Ollama can be used by setting `AI_BASE_URL` to an Ollama-compatible endpoint reachable by the backend.
- **Voice:** browser speech recognition and speech synthesis where supported. Voice availability depends on the browser and device.
- **Persistence:** SQLite by default for local development; set `DATABASE_URL` to PostgreSQL for hosted deployments.

## Quick start — frontend only
Open `index.html` in a modern browser. The interface loads without a backend; chat requests explain when the API is not configured.

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
- `AI_MODEL` — model identifier supported by your provider.
- `DATABASE_URL` — optional PostgreSQL URL; defaults to local SQLite.
- `CORS_ORIGINS` — comma-separated allowed frontend origins.
- `APP_ENV` — `development` or `production`.

## Deploy
1. Enable GitHub Pages for this repository using **GitHub Actions** as the source. The workflow in `.github/workflows/pages.yml` publishes the static site.
2. Deploy the `backend` directory to Railway.
3. Add the environment variables above in Railway.
4. Set the frontend API URL in `config.js` to the deployed backend URL, then commit the change.
5. Set `CORS_ORIGINS` to the exact GitHub Pages origin.

## Security and limitations
- API credentials belong only on the backend.
- Do not expose private provider endpoints to untrusted users without authentication, rate limiting, and abuse controls.
- Browser speech recognition may use browser/vendor services; it is not guaranteed to be fully offline.
- A local Ollama model is only local if the backend can reach the user's Ollama instance; a hosted Railway backend cannot automatically access a computer on the user's private network.
- No AI response is simulated. If no provider is configured, the API returns a clear configuration error.
