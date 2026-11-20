# HAMASA AI — حماصة

**Your personal AI assistant | مساعدك الذكي**

HAMASA is an Arabic/English AI assistant built as a web application. It combines a responsive chat interface with a FastAPI backend, configurable AI providers, optional live web research, account-based conversation sync, saved memory, file and image attachments, and text-to-speech.

- **Live app:** https://heshamzegoo.github.io/HAMASA-AI/
- **Repository:** https://github.com/HeshamZegoo/HAMASA-AI

> HAMASA is an actively developed project. Available features depend on the configured AI provider, model capabilities, and server environment.

## Features

- **Arabic and English chat:** interact in either language.
- **Token streaming:** assistant replies stream into the conversation as the provider generates them, while the bounded tool loop preserves web research, calculator, and sandbox execution.
- **AI provider configuration:** connect an OpenAI-compatible chat-completions provider and choose its model through backend environment variables.
- **Live and deep web research:** Tavily-backed search can open and read up to three relevant public pages for multi-source comparisons and verification, preserving source links in chat.
- **Code workspace:** browser-local multi-file editor with automatic local saving, individual downloads, isolated HTML preview, and optional Python/JavaScript execution through the private sandbox.
- **Image generation and editing:** an optional image lab supports OpenAI-compatible `/images/generations` and `/images/edits` providers when `AI_IMAGE_MODEL` is configured. It is intentionally reported unavailable until a compatible provider is configured.
- **Accounts and conversation sync:** authenticated users can save and retrieve conversations through the backend.
- **Saved memory:** account memories can be supplied as relevant context; configure encryption for stored memory in production.
- **Attachments:** text documents and supported office/PDF formats can be extracted for chat context. Images require a vision-capable model. See `backend/app/attachments.py` for supported formats and limits.
- **Voice:** speech input and spoken responses are available in the web interface; provider credentials and browser support affect availability.
- **Responsive interface:** web UI designed for desktop and mobile browsers.

## Architecture

| Component | Technology | Purpose |
|---|---|---|
| Frontend | HTML, CSS, JavaScript | Chat interface, browser interaction and local settings |
| Frontend hosting | GitHub Pages | Publishes the static website |
| Backend | Python, FastAPI, Uvicorn | Authentication, chat orchestration, files, memory and API routes |
| AI provider | OpenAI-compatible API | Generates assistant responses |
| Web research | Tavily (optional) | Retrieves current web sources |
| Production hosting | Railway | Runs the backend and connects persistent services |

The frontend's public API address is configured in `config.js`. **Never put provider API keys or other secrets in frontend files.**

## Run locally

### 1. Clone the repository

```bash
git clone https://github.com/HeshamZegoo/HAMASA-AI.git
cd HAMASA-AI
```

### 2. Configure and run the backend

```bash
cd backend
python -m venv .venv

# macOS / Linux
source .venv/bin/activate

# Windows PowerShell:
# .venv\Scripts\Activate.ps1

pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

On Windows, create `.env` by copying `.env.example` if the `cp` command is unavailable.

Edit `backend/.env` and provide the required provider settings. Keep this file private and do not commit it.

### 3. Point the frontend to your local API

In the repository-root `config.js`, set:

```js
window.HAMASA_CONFIG = Object.freeze({
  API_URL: "http://localhost:8000"
});
```

Then serve the repository root through a local web server and open the frontend from that server. Do not rely on opening the HTML file directly with a `file://` URL.

## Backend environment variables

Set these in `backend/.env` for local development or in the Railway service's Variables page for production.

| Variable | Purpose |
|---|---|
| `AI_API_KEY` | Secret API key for the selected AI provider |
| `AI_BASE_URL` | OpenAI-compatible API base URL; defaults to OpenAI's API |
| `AI_MODEL` | Chat model identifier supported by the provider |
| `AI_VISION_MODEL` | Optional vision-capable model for image understanding |
| `AI_IMAGE_MODEL` | Optional image model supporting OpenAI-compatible image generation and edits; leave blank to disable image generation |
| `AI_IMAGE_BASE_URL` | Optional image API base URL; defaults to `AI_BASE_URL` |
| `TAVILY_API_KEY` | Optional server-side key for live web research |
| `DATABASE_URL` | Database connection string for persistent account data |
| `JWT_SECRET` | Strong secret used to sign authentication tokens |
| `MEMORY_ENCRYPTION_KEY` | Fernet key used to encrypt saved memories at rest |
| `CORS_ORIGINS` | Comma-separated list of permitted frontend origins |
| `APP_ENV` | Set to `development` or `production` |

See [`backend/.env.example`](backend/.env.example) for the current variable template. Never share real keys in issues, screenshots, chat messages, or source control.

## Deployment

### Frontend — GitHub Pages

1. Open the repository's **Settings → Pages**.
2. Choose **GitHub Actions** as the build and deployment source.
3. The workflow in `.github/workflows/pages.yml` publishes the static frontend from the repository.
4. Confirm that `config.js` points to the intended production API URL.

### Backend — Railway

1. Connect this GitHub repository to the existing Railway backend service and deploy the `main` branch.
2. Set the backend environment variables in Railway. Add secrets there, not to GitHub or the frontend.
3. Set `CORS_ORIGINS` to the exact frontend origin, for example `https://heshamzegoo.github.io`.
4. Confirm the service health endpoint at `/health`.
5. Review the deployment logs and test chat, authentication, conversation sync, attachments, and web research after deployment.

The repository includes `railway.json` for Railway build/start configuration and GitHub Actions workflows for validation and Pages deployment.

## Security notes

- Use HTTPS for deployed frontend and backend services.
- Configure CORS with trusted origins rather than a wildcard in production.
- Use a strong, unique `JWT_SECRET` and a valid Fernet `MEMORY_ENCRYPTION_KEY` when memory encryption is enabled.
- Do not expose a private AI provider endpoint to untrusted users without appropriate authentication, rate limits, and abuse protections.
- A hosted Railway backend cannot automatically reach an Ollama instance running on a computer inside a private home network. A reachable, secured endpoint is required.

## Development and tests

Run the backend test suite from the repository root:

```bash
python -m unittest discover -s backend/tests -v
```

The backend test workflow is defined in `.github/workflows/backend-tests.yml`. Run the tests and review the changes before deploying to production.

The suite also contains deterministic, offline assistant evaluations for search intent, tool argument handling, source URL/date grounding, untrusted-page handling, SSRF protection, memory relevance, account isolation, and memory encryption. These evaluate application orchestration and safety without calling a paid model; they do not replace a separately approved live-model quality evaluation.

## Project status

HAMASA is under active development. This README describes the current application architecture and configured capabilities; it does not imply that every optional provider or feature is enabled in every deployment. Actual AI quality, image understanding, web research, and voice behavior depend on the selected provider, model, credentials, and runtime environment.

---

Made with care for Arabic-first AI experiences.
