import test from "node:test";
import assert from "node:assert/strict";
import { createServer } from "./server.mjs";

async function withServer(server, callback) {
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const address = server.address();
  try {
    await callback(`http://127.0.0.1:${address.port}`);
  } finally {
    await new Promise((resolve, reject) => {
      server.close((error) => error ? reject(error) : resolve());
    });
  }
}

test("health endpoint reports provider configuration without exposing secrets", async () => {
  const previous = process.env.RAILWAY_TOKEN;
  delete process.env.RAILWAY_TOKEN;
  process.env.HAMASA_EXECUTOR_TOKEN = "test-shared-token";
  const server = createServer({ sandboxCreate: async () => { throw new Error("must not run"); } });
  try {
    await withServer(server, async (base) => {
      const response = await fetch(base + "/health");
      assert.equal(response.status, 200);
      assert.deepEqual(await response.json(), { status: "ok", configured: false });
    });
  } finally {
    if (previous === undefined) delete process.env.RAILWAY_TOKEN;
    else process.env.RAILWAY_TOKEN = previous;
    delete process.env.HAMASA_EXECUTOR_TOKEN;
  }
});

test("health reports configured only when all provider credentials are present", async () => {
  process.env.RAILWAY_TOKEN = "railway-test-token";
  process.env.HAMASA_EXECUTOR_TOKEN = "test-shared-token";
  delete process.env.RAILWAY_ENVIRONMENT_ID;
  const server = createServer({ sandboxCreate: async () => { throw new Error("must not run"); } });
  try {
    await withServer(server, async (base) => {
      const missingEnvironment = await (await fetch(base + "/health")).json();
      assert.equal(missingEnvironment.configured, false);
      process.env.RAILWAY_ENVIRONMENT_ID = "production-environment-id";
      const ready = await (await fetch(base + "/health")).json();
      assert.equal(ready.configured, true);
    });
  } finally {
    delete process.env.RAILWAY_TOKEN;
    delete process.env.RAILWAY_ENVIRONMENT_ID;
    delete process.env.HAMASA_EXECUTOR_TOKEN;
  }
});

test("execution requires the internal bearer token", async () => {
  process.env.RAILWAY_TOKEN = "railway-test-token";
  process.env.HAMASA_EXECUTOR_TOKEN = "test-shared-token";
  const server = createServer({ sandboxCreate: async () => { throw new Error("must not run"); } });
  try {
    await withServer(server, async (base) => {
      const response = await fetch(base + "/execute", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ language: "javascript", code: "console.log(1)" }),
      });
      assert.equal(response.status, 401);
      assert.equal((await response.json()).error, "Unauthorized.");
    });
  } finally {
    delete process.env.RAILWAY_TOKEN;
    delete process.env.HAMASA_EXECUTOR_TOKEN;
  }
});

test("unsupported languages are rejected before a VM is created", async () => {
  process.env.RAILWAY_TOKEN = "railway-test-token";
  process.env.HAMASA_EXECUTOR_TOKEN = "test-shared-token";
  const server = createServer({ sandboxCreate: async () => { throw new Error("must not run"); } });
  try {
    await withServer(server, async (base) => {
      const response = await fetch(base + "/execute", {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: "Bearer test-shared-token" },
        body: JSON.stringify({ language: "bash", code: "whoami" }),
      });
      assert.equal(response.status, 400);
      assert.match((await response.json()).error, /Python and JavaScript/);
    });
  } finally {
    delete process.env.RAILWAY_TOKEN;
    delete process.env.HAMASA_EXECUTOR_TOKEN;
  }
});

test("code runs in an isolated VM and the VM is destroyed after the run", async () => {
  process.env.RAILWAY_TOKEN = "railway-test-token";
  process.env.HAMASA_EXECUTOR_TOKEN = "test-shared-token";
  const events = [];
  let createOptions;
  let createLanguage;
  const sandbox = {
    files: {
      write: async (path, code) => events.push({ type: "write", path, code }),
    },
    exec: async (command, options) => {
      events.push({ type: "exec", command, options });
      return { exitCode: 0, stdout: "2\n", stderr: "", timedOut: false, truncated: false };
    },
    destroy: async () => events.push({ type: "destroy" }),
  };
  const server = createServer({
    sandboxCreate: async (options, language) => {
      createOptions = options;
      createLanguage = language;
      events.push({ type: "create" });
      return sandbox;
    },
  });
  try {
    await withServer(server, async (base) => {
      const response = await fetch(base + "/execute", {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: "Bearer test-shared-token" },
        body: JSON.stringify({ language: "python", code: "print(1 + 1)" }),
      });
      assert.equal(response.status, 200);
      const result = await response.json();
      assert.equal(result.ok, true);
      assert.equal(result.stdout, "2\n");
      assert.equal(createOptions.networkIsolation, "ISOLATED");
      assert.deepEqual(createOptions.resources, { cpu: 1, memoryGB: 2 });
      assert.equal(createOptions.idleTimeoutMinutes, 1);
      assert.equal(createLanguage, "python");
      assert.equal(events[1].command.includes("apt-get install -y -qq python3"), true);
      assert.equal(events[1].options.timeoutSec, 120);
      assert.equal(events[2].path, "/tmp/hamasa_main.py");
      assert.equal(events[3].command, "python3 /tmp/hamasa_main.py");
      assert.equal(events[3].options.timeoutSec, 20);
      assert.equal(events[3].options.ephemeral, true);
      assert.equal(events.at(-1).type, "destroy");
    });
  } finally {
    delete process.env.RAILWAY_TOKEN;
    delete process.env.HAMASA_EXECUTOR_TOKEN;
  }
});

test("timed out code is reported accurately and its VM is still destroyed", async () => {
  process.env.RAILWAY_TOKEN = "railway-test-token";
  process.env.HAMASA_EXECUTOR_TOKEN = "test-shared-token";
  let destroyed = false;
  const sandbox = {
    files: { write: async () => {} },
    exec: async () => ({ exitCode: -1, stdout: "", stderr: "deadline", timedOut: true, truncated: false }),
    destroy: async () => { destroyed = true; },
  };
  const server = createServer({ sandboxCreate: async () => sandbox });
  try {
    await withServer(server, async (base) => {
      const response = await fetch(base + "/execute", {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: "Bearer test-shared-token" },
        body: JSON.stringify({ language: "javascript", code: "while (true) {}" }),
      });
      const result = await response.json();
      assert.equal(response.status, 200);
      assert.equal(result.ok, false);
      assert.equal(result.timed_out, true);
      assert.equal(destroyed, true);
    });
  } finally {
    delete process.env.RAILWAY_TOKEN;
    delete process.env.HAMASA_EXECUTOR_TOKEN;
  }
});

test("oversized code is rejected before a VM is created", async () => {
  process.env.RAILWAY_TOKEN = "railway-test-token";
  process.env.HAMASA_EXECUTOR_TOKEN = "test-shared-token";
  const server = createServer({ sandboxCreate: async () => { throw new Error("must not run"); } });
  try {
    await withServer(server, async (base) => {
      const response = await fetch(base + "/execute", {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: "Bearer test-shared-token" },
        body: JSON.stringify({ language: "javascript", code: "x".repeat(50_001) }),
      });
      assert.equal(response.status, 400);
      assert.match((await response.json()).error, /50,000-byte limit/);
    });
  } finally {
    delete process.env.RAILWAY_TOKEN;
    delete process.env.HAMASA_EXECUTOR_TOKEN;
  }
});
