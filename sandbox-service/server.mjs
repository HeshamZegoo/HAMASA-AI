import http from "node:http";
import path from "node:path";
import { timingSafeEqual } from "node:crypto";
import { fileURLToPath } from "node:url";
import { Sandbox } from "railway";

const MAX_REQUEST_BYTES = 55 * 1024;
const MAX_CODE_BYTES = 50_000;
const MAX_OUTPUT_BYTES = 24_000;
const EXECUTION_TIMEOUT_SECONDS = 20;
const MAX_CONCURRENT_RUNS = 2;
const MAX_RUNS_PER_MINUTE = 8;
const recentRuns = [];
let activeRuns = 0;
const PYTHON_TEMPLATE = Sandbox.template().withPackages("python3");

function createRailwaySandbox(options, language) {
  return language === "python"
    ? Sandbox.create(PYTHON_TEMPLATE, options)
    : Sandbox.create(options);
}

function sendJson(response, status, payload) {
  if (response.headersSent) return;
  const body = JSON.stringify(payload);
  response.writeHead(status, {
    "Content-Type": "application/json; charset=utf-8",
    "Content-Length": Buffer.byteLength(body),
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
  });
  response.end(body);
}

async function readJson(request) {
  const chunks = [];
  let size = 0;
  for await (const chunk of request) {
    size += chunk.length;
    if (size > MAX_REQUEST_BYTES) {
      const error = new Error("Request body is too large.");
      error.statusCode = 413;
      throw error;
    }
    chunks.push(chunk);
  }
  try {
    return JSON.parse(Buffer.concat(chunks).toString("utf8"));
  } catch {
    const error = new Error("A valid JSON request body is required.");
    error.statusCode = 400;
    throw error;
  }
}

function isAuthorized(request) {
  const expected = Buffer.from(process.env.HAMASA_EXECUTOR_TOKEN || "");
  const header = request.headers.authorization || "";
  const supplied = Buffer.from(header.startsWith("Bearer ") ? header.slice(7) : "");
  return expected.length > 0 && supplied.length === expected.length && timingSafeEqual(expected, supplied);
}

function validateCodeRequest(body) {
  if (!body || typeof body !== "object" || Array.isArray(body)) {
    return "A JSON object is required.";
  }
  if (!["python", "javascript"].includes(body.language)) {
    return "Supported languages are Python and JavaScript.";
  }
  if (typeof body.code !== "string" || !body.code.trim()) {
    return "Code must be a non-empty string.";
  }
  if (Buffer.byteLength(body.code, "utf8") > MAX_CODE_BYTES) {
    return "Code exceeds the 50,000-byte limit.";
  }
  return null;
}

export function createServer({ sandboxCreate = createRailwaySandbox } = {}) {
  return http.createServer(async (request, response) => {
    const pathname = new URL(request.url || "/", "http://localhost").pathname;

    if (request.method === "GET" && pathname === "/health") {
      const configured = Boolean(
        process.env.RAILWAY_TOKEN
        && process.env.RAILWAY_ENVIRONMENT_ID
        && process.env.HAMASA_EXECUTOR_TOKEN
      );
      return sendJson(response, 200, { status: "ok", configured });
    }

    if (request.method !== "POST" || pathname !== "/execute") {
      return sendJson(response, 404, { error: "Not found." });
    }

    if (!isAuthorized(request)) {
      return sendJson(response, 401, { error: "Unauthorized." });
    }

    let body;
    try {
      body = await readJson(request);
    } catch (error) {
      return sendJson(response, error.statusCode || 400, { error: error.message });
    }

    const validationError = validateCodeRequest(body);
    if (validationError) {
      return sendJson(response, 400, { error: validationError });
    }

    if (!process.env.RAILWAY_TOKEN) {
      return sendJson(response, 503, { error: "The isolated execution provider is not configured." });
    }

    const now = Date.now();
    while (recentRuns.length && now - recentRuns[0] >= 60_000) recentRuns.shift();
    if (activeRuns >= MAX_CONCURRENT_RUNS || recentRuns.length >= MAX_RUNS_PER_MINUTE) {
      return sendJson(response, 429, { error: "The code runner is busy. Please retry shortly." });
    }

    activeRuns += 1;
    recentRuns.push(now);
    const startedAt = Date.now();
    let sandbox;
    let status = 200;
    let resultPayload;

    try {
      sandbox = await sandboxCreate({
        idleTimeoutMinutes: 1,
        resources: { cpu: 1, memoryGB: 2 },
        networkIsolation: "ISOLATED",
      }, body.language);

      const filePath = body.language === "python"
        ? "/tmp/hamasa_main.py"
        : "/tmp/hamasa_main.js";
      const command = body.language === "python"
        ? "python3 /tmp/hamasa_main.py"
        : "node /tmp/hamasa_main.js";

      await sandbox.files.write(filePath, body.code);
      const result = await sandbox.exec(command, {
        timeoutSec: EXECUTION_TIMEOUT_SECONDS,
        maxOutputBytes: MAX_OUTPUT_BYTES,
        ephemeral: true,
      });

      const stdoutRaw = Buffer.from(String(result.stdout || ""));
      const stderrRaw = Buffer.from(String(result.stderr || ""));
      const stdout = stdoutRaw.subarray(0, MAX_OUTPUT_BYTES).toString("utf8");
      const remainingOutputBytes = Math.max(0, MAX_OUTPUT_BYTES - Buffer.byteLength(stdout));
      const stderr = stderrRaw.subarray(0, remainingOutputBytes).toString("utf8");
      const outputWasTrimmed = stdoutRaw.length > MAX_OUTPUT_BYTES
        || stderrRaw.length > remainingOutputBytes;
      resultPayload = {
        ok: result.exitCode === 0 && !result.timedOut,
        language: body.language,
        exit_code: result.exitCode,
        stdout,
        stderr,
        timed_out: Boolean(result.timedOut),
        truncated: Boolean(result.truncated) || outputWasTrimmed,
        duration_ms: Date.now() - startedAt,
      };
    } catch (error) {
      // Log safe provider metadata only; never log source code, tokens, or environment values.
      console.error("Isolated execution failed:", JSON.stringify({
        name: error?.name || "Error",
        message: String(error?.message || "Unknown execution failure").slice(0, 500),
        templateId: error?.templateId || null,
        environmentId: error?.environmentId || process.env.RAILWAY_ENVIRONMENT_ID || null,
        status: error?.status || null,
      }));
      status = 502;
      resultPayload = {
        ok: false,
        error: "The isolated execution environment could not complete this run.",
      };
    } finally {
      if (sandbox) {
        try {
          await sandbox.destroy();
        } catch (error) {
          console.error("Sandbox cleanup failed:", error?.name || "Error");
        }
      }
      activeRuns = Math.max(0, activeRuns - 1);
    }

    return sendJson(response, status, resultPayload);
  });
}

const isDirectRun = process.argv[1]
  && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url);

if (isDirectRun) {
  const port = Number.parseInt(process.env.PORT || "3000", 10);
  const server = createServer();
  server.listen(port, "0.0.0.0", () => {
    console.log(`HAMASA isolated code sandbox listening on port ${port}`);
  });
}
