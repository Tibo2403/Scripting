import assert from "node:assert/strict";
import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { spawn } from "node:child_process";
import test from "node:test";

const runtime = resolve(import.meta.dirname, "..", "runtime", "run-agent.mjs");

async function unusedPort() {
  const server = createServer();
  await new Promise((resolveListen) => server.listen(0, "127.0.0.1", resolveListen));
  const address = server.address();
  const port = address.port;
  await new Promise((resolveClose) => server.close(resolveClose));
  return port;
}

async function fakeOpenClawDirectory() {
  const directory = await mkdtemp(join(tmpdir(), "openclaw-runtime-test-"));
  const implementation = join(directory, "gateway");
  await writeFile(
    implementation,
    `import { createServer } from "node:http";
const portIndex = process.argv.indexOf("--port");
const port = Number(process.argv[portIndex + 1]);
if (process.env.FAKE_EXIT_CODE) {
  setTimeout(() => process.exit(Number(process.env.FAKE_EXIT_CODE)), 30);
} else {
  const server = createServer((_request, response) => {
    response.writeHead(Number(process.env.FAKE_HEALTH_STATUS || 200));
    response.end();
  });
  server.listen(port, "127.0.0.1");
  const stop = () => server.close(() => process.exit(0));
  process.on("SIGTERM", stop);
  process.on("SIGINT", stop);
}
`,
    "utf8",
  );

  return directory;
}

function startRuntime(environment, cwd) {
  return spawn(process.execPath, [runtime], {
    env: { ...process.env, ...environment },
    cwd,
    stdio: ["ignore", "pipe", "pipe"],
  });
}

async function waitForResponse(url, expectedStatus) {
  let lastError;
  for (let attempt = 0; attempt < 50; attempt += 1) {
    try {
      const response = await fetch(url);
      if (response.status === expectedStatus) return response;
      lastError = new Error(`Received HTTP ${response.status}`);
    } catch (error) {
      lastError = error;
    }
    await new Promise((resolveWait) => setTimeout(resolveWait, 50));
  }
  throw lastError;
}

async function stopProcess(child) {
  if (child.exitCode !== null) return;
  child.kill("SIGTERM");
  await new Promise((resolveExit) => child.once("exit", resolveExit));
}

test("health endpoint reports readiness and hides all other routes", async (context) => {
  const fakeDirectory = await fakeOpenClawDirectory();
  const healthPort = await unusedPort();
  const gatewayPort = await unusedPort();
  const child = startRuntime(
    {
      OPENCLAW_EXECUTABLE: process.execPath,
      HEALTH_PORT: String(healthPort),
      OPENCLAW_GATEWAY_PORT: String(gatewayPort),
    },
    fakeDirectory,
  );
  context.after(async () => {
    await stopProcess(child);
    await rm(fakeDirectory, { recursive: true, force: true });
  });

  const health = await waitForResponse(`http://127.0.0.1:${healthPort}/healthz`, 200);
  assert.deepEqual(await health.json(), { status: "ok" });
  assert.equal(health.headers.get("cache-control"), "no-store");

  const hidden = await fetch(`http://127.0.0.1:${healthPort}/anything-else`);
  assert.equal(hidden.status, 404);
  assert.deepEqual(await hidden.json(), { error: "not_found" });
});

test("gateway failures propagate a non-zero runtime exit", async (context) => {
  const fakeDirectory = await fakeOpenClawDirectory();
  context.after(() => rm(fakeDirectory, { recursive: true, force: true }));
  const child = startRuntime(
    {
      OPENCLAW_EXECUTABLE: process.execPath,
      HEALTH_PORT: String(await unusedPort()),
      OPENCLAW_GATEWAY_PORT: String(await unusedPort()),
      FAKE_EXIT_CODE: "23",
    },
    fakeDirectory,
  );

  const exitCode = await new Promise((resolveExit) => child.once("exit", resolveExit));
  assert.equal(exitCode, 23);
});

test("invalid port configuration fails before startup", async () => {
  const child = startRuntime({ HEALTH_PORT: "public" });
  let standardError = "";
  child.stderr.on("data", (chunk) => {
    standardError += chunk;
  });

  const exitCode = await new Promise((resolveExit) => child.once("exit", resolveExit));
  assert.notEqual(exitCode, 0);
  assert.match(standardError, /HEALTH_PORT must be an integer/);
});
