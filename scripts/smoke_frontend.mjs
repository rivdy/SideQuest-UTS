import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { once } from "node:events";
import net from "node:net";
import { fileURLToPath } from "node:url";

const reservation = net.createServer();
reservation.listen(0, "127.0.0.1");
await once(reservation, "listening");
const port = reservation.address().port;
await new Promise(resolve => reservation.close(resolve));
const cwd = fileURLToPath(new URL("../frontend/", import.meta.url));
const server = spawn(process.execPath, ["node_modules/next/dist/bin/next", "start", "--hostname", "127.0.0.1", "--port", String(port)], {cwd, windowsHide: true, stdio: ["ignore", "pipe", "pipe"]});
let log = "";
server.stdout.on("data", data => { log += data; });
server.stderr.on("data", data => { log += data; });
server.on("error", error => { log += error.message; });
const base = `http://127.0.0.1:${port}`;
try {
  let response;
  for (let attempt = 0; attempt < 80; attempt++) {
    if (server.exitCode !== null) throw new Error(log);
    try { response = await fetch(base, {signal: AbortSignal.timeout(1000)}); break; }
    catch { await new Promise(resolve => setTimeout(resolve, 250)); }
  }
  assert.ok(response, `Server failed to start: ${log}`);
  assert.equal(response.status, 200);
  const html = await response.text();
  assert.match(html, /BAYLab AI/);
  assert.match(html, /id="stage"/);
  assert.match(html, /href="baylab-figma.html"/);
  for (const asset of ["/baylab-figma.html", "/screens/dashboard.jpg", "/screens/screening.jpg", "/screens/rekomendasi.jpg"]) assert.equal((await fetch(base + asset)).status, 200, asset);
  assert.match(html, /lang="id"/);
  assert.equal(response.headers.get("x-frame-options"), "DENY");
  assert.equal(response.headers.get("x-content-type-options"), "nosniff");
  assert.equal(response.headers.get("x-powered-by"), null);
  assert.match(response.headers.get("content-security-policy"), /frame-ancestors 'none'/);
  for (const path of ["/.env", "/README.md", "/soda-backup.html", "/backend/app/main.py"]) {
    assert.equal((await fetch(base + path)).status, 404, path);
  }
  console.log("Frontend HTTP smoke passed: page, headers, and private-path isolation.");
} finally {
  server.kill();
}
