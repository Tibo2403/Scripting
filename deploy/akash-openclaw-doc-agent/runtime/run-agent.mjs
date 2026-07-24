import { randomBytes } from "node:crypto";
import { spawn } from "node:child_process";
import { createServer } from "node:http";

const gatewayToken =
  process.env.OPENCLAW_GATEWAY_TOKEN || randomBytes(32).toString("hex");

const gateway = spawn(
  "openclaw",
  ["gateway", "run", "--bind", "loopback", "--port", "18789"],
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
        const gatewayHealth = await fetch("http://127.0.0.1:18789/healthz", {
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

health.listen(8080, "0.0.0.0");

function shutdown(signal) {
  health.close();
  if (!gatewayExited) {
    gateway.kill(signal);
  }
}

process.on("SIGTERM", () => shutdown("SIGTERM"));
process.on("SIGINT", () => shutdown("SIGINT"));
