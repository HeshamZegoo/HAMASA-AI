# HAMASA AI — حماصة

Your Personal AI Companion.

A web-first Arabic/English AI companion with a premium dark interface, animated orb/avatar, continuous Gemini Live voice conversations, and browser-local conversation history.

## Current architecture
- **Frontend:** static HTML/CSS/JavaScript, deployable to GitHub Pages.
- **Backend:** FastAPI, deployable to Railway.
- **AI:** OpenAI-compatible Chat Completions API. Configure a provider and model through server environment variables; Ollama can be used by setting `AI_BASE_URL` to an Ollama-compatible endpoint reachable by the backend.
- **Voice:** Gemini Live API through a FastAPI WebSocket proxy. The browser streams 16 kHz PCM microphone audio and plays 24 kHz PCM responses; no MediaRecorder or browser speech-synthesis fallback is used.
- **Conversation history:** currently stored in the browser's local storage. The backend includes a minimal SQLite initialization scaffold; server-side conversation sync and PostgreSQL persistence are not implemented yet.

## Quick start — frontend only
Open `index.html` through HTTPS (for example GitHub Pages). Microphone access requires a secure context and explicit browser permission.

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
- `DATABASE_URL` — reserved for future database integration; PostgreSQL conversation persistence is not implemented in this starter.
- `CORS_ORIGINS` — comma-separated allowed frontend origins.
- `TTS_GEMINI_API_KEY` — Gemini Developer API key used by the Live voice route and Gemini TTS/transcription endpoints. Keep it server-side.\n- `APP_ENV` — `development` or `production`.

## Deploy
1. Enable GitHub Pages for this repository using **GitHub Actions** as the source. The workflow in `.github/workflows/pages.yml` publishes the static site.
2. Deploy the repository root to Railway; `railway.json` installs `backend/requirements.txt` and starts `backend.app.main:app`.
3. Add the environment variables above in Railway.
4. Set the frontend API URL in `config.js` to the deployed backend URL, then commit the change.
5. Set `CORS_ORIGINS` to the exact GitHub Pages origin.\n6. Confirm `/health` reports the chat provider configured, then test `/api/live` from the deployed page with microphone permission enabled.

## Security and limitations
- API credentials belong only on the backend.
- Do not expose private provider endpoints to untrusted users without authentication, rate limiting, and abuse controls.
- Live voice requires a Gemini API key with Live API access, an HTTPS browser context, microphone permission, and a stable WebSocket connection.
- A local Ollama model is only local if the backend can reach the user's Ollama instance; a hosted Railway backend cannot automatically access a computer on the user's private network.
- No AI response is simulated. If no provider is configured, the API returns a clear configuration error.
