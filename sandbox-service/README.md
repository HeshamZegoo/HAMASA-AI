# HAMASA isolated code sandbox

This private Railway service runs user-requested Python and JavaScript in a fresh Railway Sandbox VM for each execution. It is not a general shell inside the HAMASA API process.

## Security and limits

- One fresh VM per run, destroyed in a `finally` cleanup path.
- `networkIsolation: "ISOLATED"`: the VM cannot reach services on the Railway private network. Railway documents that isolated sandboxes retain outbound public internet access.
- No API keys, database URLs, Railway tokens, or service environment variables are copied into the execution VM.
- 1 vCPU / 2 GB memory ceiling, 20-second command timeout, 50,000-byte source limit, 24,000-byte output cap.
- Maximum two concurrent runs and eight starts per minute per service instance.
- Internal bearer authentication; no public domain should be attached to this service.
- Python VMs are created from a cached Railway template with `python3` installed; JavaScript uses the standard Node-enabled image. Third-party packages are not installed per request.

## Railway service configuration

Create a private service in the existing HAMASA-AI production project:

- Repository: `HeshamZegoo/HAMASA-AI`
- Root directory: `/sandbox-service`
- Build command: `npm install --no-audit --no-fund`
- Start command: `npm start`
- Healthcheck path: `/health`
- Private network endpoint: `hamasa-code-sandbox`
- Do not create a public domain.

Set `RAILWAY_TOKEN` on this service to a Railway **project token scoped only to the production environment**. Create it in Project Settings → Tokens. The Railway SDK uses this token to create/destroy sandboxes; it is never passed into the sandbox VM.

Set the same randomly generated `HAMASA_EXECUTOR_TOKEN` on this service and the `hamasa-api` service. On the API service also set:

- `HAMASA_EXECUTOR_URL=http://hamasa-code-sandbox.railway.internal:3000`
- `HAMASA_EXECUTOR_ENABLED=true`

The API exposes the model tool only when all three API-side settings are present. Do not put either token in frontend files, chat messages, GitHub, or logs.

## Local tests

From this directory:

```bash
npm install --no-audit --no-fund
npm test
```
