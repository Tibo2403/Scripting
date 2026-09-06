import { randomBytes } from "node:crypto";
import { spawn } from "node:child_process";
import { createServer } from "node:http";

function readPort(name, fallback) {
  const value = process.env[name] ?? String(fallback);
  if (!/^\d+$/.test(value)) {
    throw new Error(`${name} must be an integer between 1 and 65535.`);
  }

  const port = Number(value);
  if (port < 1 || port > 65535) {
    throw new Error(`${name} must be an integer between 1 and 65535.`);
  }
  return port;
}

const gatewayPort = readPort("OPENCLAW_GATEWAY_PORT", 18789);
const healthPort = readPort("HEALTH_PORT", 8080);
const openclawExecutable = process.env.OPENCLAW_EXECUTABLE || "openclaw";
const gatewayToken =
  process.env.OPENCLAW_GATEWAY_TOKEN || randomBytes(32).toString("hex");

const gateway = spawn(
  openclawExecutable,
  ["gateway", "run", "--bind", "loopback", "--port", String(gatewayPort)],
  {
    env: {
      ...process.env,
      OPENCLAW_GATEWAY_TOKEN: gatewayToken,
    },
    stdio: "inherit",
  },
);

let gatewayExited = false;
gateway.once("error", (error) => {
  gatewayExited = true;
  console.error(`Unable to start the OpenClaw gateway: ${error.message}`);
});
gateway.once("exit", (code, signal) => {
  gatewayExited = true;
  console.error(`OpenClaw gateway stopped (code=${code}, signal=${signal}).`);
  process.exitCode = code ?? 1;
  health.close(() => process.exit(process.exitCode));
});

const health = createServer(async (request, response) => {
  if (request.method === "GET" && request.url === "/healthz") {
    let ready = false;
    if (!gatewayExited) {
      try {
        const gatewayHealth = await fetch(`http://127.0.0.1:${gatewayPort}/healthz`, {
          signal: AbortSignal.timeout(1500),
        });
        ready = gatewayHealth.ok;
      } catch {
        ready = false;
      }
    }

    response.writeHead(ready ? 200 : 503, {
      "Content-Type": "application/json",
      "Cache-Control": "no-store",
    });
    response.end(JSON.stringify({ status: ready ? "ok" : "starting" }));
    return;
  }

  response.writeHead(404, {
    "Content-Type": "application/json",
    "Cache-Control": "no-store",
  });
  response.end(JSON.stringify({ error: "not_found" }));
});

health.listen(healthPort, "0.0.0.0");

function shutdown(signal) {
  health.close();
  if (!gatewayExited) {
    gateway.kill(signal);
  }
}

process.on("SIGTERM", () => shutdown("SIGTERM"));
process.on("SIGINT", () => shutdown("SIGINT"));
