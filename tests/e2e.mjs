// Headless browser check. Serves the site locally, drives it in Chrome (muted, fresh profile),
// and checks the library, filters, reader, French toggle, theme, console errors, failed requests
// and single-line text at desktop and phone widths.
// Usage: node tests/e2e.mjs [--shot]     (CHROME_PATH overrides the browser location)
import { spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const CHROME = process.env.CHROME_PATH || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const HTTP = 8781, CDP = 9341;
const base = `http://127.0.0.1:${HTTP}/`;
const sleep = ms => new Promise(r => setTimeout(r, ms));
const failures = [];
const check = (ok, msg) => { console.log((ok ? "PASS " : "FAIL ") + msg); if (!ok) failures.push(msg); };

const profile = fs.mkdtempSync(path.join(os.tmpdir(), "gr-chrome-"));
const server = spawn("perl", ["-e", "alarm 200; exec @ARGV", "python3", "-m", "http.server", String(HTTP), "--bind", "127.0.0.1"],
  { cwd: root, detached: true, stdio: "ignore" });
const chrome = spawn(CHROME, ["--headless=new", `--remote-debugging-port=${CDP}`, `--user-data-dir=${profile}`,
  "--mute-audio", "--window-size=1440,900", "--no-first-run", "--no-default-browser-check", "--disable-gpu", "about:blank"],
  { stdio: "ignore" });
const chromePid = chrome.pid;
function cleanup() {
  try { process.kill(chromePid); } catch (e) {}
  try { process.kill(-server.pid); } catch (e) {}
  try { fs.rmSync(profile, { recursive: true, force: true }); } catch (e) {}
}
process.on("exit", cleanup);
setTimeout(() => { console.error("global timeout"); cleanup(); process.exit(2); }, 170000).unref();

let ws, msgId = 0; const pending = new Map(), listeners = [];
async function connect() {
  let target;
  for (let i = 0; i < 60 && !target; i++) {
    try { const list = await (await fetch(`http://127.0.0.1:${CDP}/json/list`)).json(); target = list.find(t => t.type === "page"); } catch (e) {}
    if (!target) await sleep(250);
  }
  if (!target) throw new Error("chrome did not start");
  ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
  ws.onmessage = e => {
    const m = JSON.parse(e.data);
    if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); }
    else if (m.method) listeners.forEach(f => f(m));
  };
}
const send = (method, params = {}) => new Promise(res => { const id = ++msgId; pending.set(id, res); ws.send(JSON.stringify({ id, method, params })); });
async function ev(expr) {
  const r = await send("Runtime.evaluate", { expression: expr, awaitPromise: true, returnByValue: true });
  if (r.result && r.result.exceptionDetails) throw new Error("eval: " + ((r.result.exceptionDetails.exception && r.result.exceptionDetails.exception.description) || "").slice(0, 300));
  return r.result && r.result.result ? r.result.result.value : undefined;
}
async function waitFor(expr, ms = 15000) {
  const t0 = Date.now();
  while (Date.now() - t0 < ms) { if (await ev(expr)) return true; await sleep(100); }
  throw new Error("timeout waiting for " + expr);
}

const problems = [];
listeners.push(m => {
  if (m.method === "Runtime.exceptionThrown") problems.push("exception: " + JSON.stringify(m.params.exceptionDetails.text + " " + ((m.params.exceptionDetails.exception || {}).description || "")).slice(0, 200));
  if (m.method === "Runtime.consoleAPICalled" && (m.params.type === "error" || m.params.type === "warning")) problems.push("console." + m.params.type + ": " + JSON.stringify(m.params.args.map(a => a.value || a.description)).slice(0, 200));
  if (m.method === "Log.entryAdded" && m.params.entry.level === "error") problems.push("log error: " + m.params.entry.text + " " + (m.params.entry.url || ""));
  if (m.method === "Network.loadingFailed") problems.push("request failed: " + m.params.errorText);
  if (m.method === "Network.responseReceived" && m.params.response.status >= 400) problems.push("HTTP " + m.params.response.status + " " + m.params.response.url);
});

async function go(url) {
  await send("Page.navigate", { url: base + url });
  await sleep(300);
  await waitFor("document.readyState === 'complete'");
}
async function phone(on) {
  if (on) await send("Emulation.setDeviceMetricsOverride", { width: 390, height: 844, deviceScaleFactor: 2, mobile: true });
  else await send("Emulation.clearDeviceMetricsOverride");
}

// Every listed element must be on one line and not clipped; the page must not scroll sideways.
const LAYOUT = `(() => {
  const out = [];
  const sel = ARGS;
  for (const s of sel) for (const e of document.querySelectorAll(s)) {
    const r = e.getBoundingClientRect();
    if (r.width === 0) continue;
    let lines = 1;
    if (!/^(SELECT|INPUT)$/.test(e.tagName)) {
      const cys = [];
      for (const n of e.childNodes) {
        if (n.nodeType === 1) { const q = n.getBoundingClientRect(); if (q.width > 0) cys.push(q.top + q.height / 2); }
        else if (n.nodeType === 3 && n.textContent.trim()) {
          const rg = document.createRange(); rg.selectNodeContents(n);
          for (const q of rg.getClientRects()) if (q.width > 0) cys.push(q.top + q.height / 2);
        }
      }
      cys.sort((x, y) => x - y);
      lines = cys.length ? 1 : 1;
      for (let i = 1; i < cys.length; i++) if (cys[i] - cys[i - 1] > 8) lines++;
    }
    const clipped = e.scrollWidth > e.clientWidth + 1 || r.right > window.innerWidth + 1 || r.left < -1;
    if (lines > 1 || clipped) out.push(s + " '" + e.textContent.trim().slice(0, 50) + "' lines=" + lines + (clipped ? " CLIPPED" : ""));
  }
  if (document.documentElement.scrollWidth > window.innerWidth + 1) out.push("page scrolls sideways: " + document.documentElement.scrollWidth + " > " + window.innerWidth);
  return out;
})()`;
const layout = sels => ev(LAYOUT.replace("ARGS", JSON.stringify(sels)));

try {
  await connect();
  await send("Page.enable"); await send("Runtime.enable"); await send("Network.enable"); await send("Log.enable");

  // ---- library
  await go("index.html");
  await waitFor("document.querySelectorAll('.card').length > 0");
  const total = await ev("document.querySelectorAll('.card').length");
  check(total === 52, "library shows all 52 stories (" + total + ")");
  await ev("localStorage.clear()");

  await ev("[...document.querySelectorAll('#levels .pill')].find(b => b.textContent.startsWith('Very Hard')).click()");
  const vh = await ev("[...document.querySelectorAll('.card .badge:first-child')].map(b => b.textContent)");
  check(vh.length === 10 && vh.every(t => t === "Very Hard"), "level filter: Very Hard shows 10 Very Hard cards (" + vh.length + ")");
  await ev("[...document.querySelectorAll('#levels .pill')].find(b => b.textContent.startsWith('All')).click()");
  await ev("document.getElementById('frbtn').click()");
  const frc = await ev("document.querySelectorAll('.card').length");
  check(frc === 10, "French filter shows 10 stories (" + frc + ")");
  await ev("document.getElementById('frbtn').click()");
  await ev("(() => { const q = document.getElementById('q'); q.value = 'alice'; q.dispatchEvent(new Event('input')); })()");
  const sr = await ev("[...document.querySelectorAll('.card h2')].map(h => h.textContent)");
  check(sr.length === 1 && /Alice/.test(sr[0]), "search 'alice' finds one story (" + sr.join("|") + ")");
  await ev("(() => { const q = document.getElementById('q'); q.value = ''; q.dispatchEvent(new Event('input')); })()");

  // ---- desktop layout + screenshot
  await sleep(200);
  const ld = await layout([".brand", ".topnav .pill", "#levels .pill", ".badge", ".card h2", ".card .row", "#sort", ".intro h1"]);
  check(ld.length === 0, "library single-line text fits at 1440: " + JSON.stringify(ld));
  if (process.argv.includes("--shot")) {
    await ev("document.documentElement.setAttribute('data-theme', 'light')");
    const shot = await send("Page.captureScreenshot", { format: "png" });
    fs.writeFileSync(path.join(root, "screenshot.png"), Buffer.from(shot.result.data, "base64"));
    console.log("saved screenshot.png");
    await ev("document.documentElement.removeAttribute('data-theme')");
  }

  // ---- reader, English
  await ev("document.querySelector('.card').click()");
  await waitFor("document.querySelectorAll('.chapter').length > 0");
  const chs = await ev("document.querySelectorAll('.chapter').length");
  check(chs > 0 && /reader\.html\?story=/.test(await ev("location.href")), "a story opens with chapters (" + chs + ")");

  // ---- French story
  await go("reader.html?story=a_christmas_carol");
  await waitFor("document.querySelectorAll('.chapter').length > 0");
  check(await ev("!document.getElementById('langseg').hidden"), "French story shows the language toggle");
  await ev("document.querySelector('#langseg [data-lang=fr]').click()");
  const fr1 = await ev("document.querySelector('.para.fr') && document.querySelector('.para.fr').textContent");
  check(!!fr1 && fr1.startsWith("Marley était mort"), "French toggle shows French text (" + (fr1 || "").slice(0, 40) + ")");
  await ev("document.querySelector('#langseg [data-lang=both]').click()");
  const pairs = await ev("document.querySelectorAll('.pair.two').length");
  const cols = await ev("getComputedStyle(document.querySelector('.pair.two')).gridTemplateColumns.split(' ').length");
  check(pairs > 0 && cols === 2, "side by side shows two columns at 1440 (" + pairs + " pairs, " + cols + " cols)");
  await ev("document.querySelector('#langseg [data-lang=en]').click()");
  // English-only story has no toggle
  await go("reader.html?story=cinderella");
  await waitFor("document.querySelectorAll('.chapter').length > 0");
  check(await ev("document.getElementById('langseg').hidden"), "English-only story hides the language toggle");
  // script-format story renders speaker labels
  await go("reader.html?story=three_billy_goats_gruff");
  await waitFor("document.querySelectorAll('.chapter').length > 0");
  check(await ev("document.querySelectorAll('.sp').length > 10"), "script-format story shows speaker labels");
  // theme
  const before = await ev("getComputedStyle(document.body).backgroundColor");
  await ev("document.getElementById('theme-btn').click()");
  const after = await ev("getComputedStyle(document.body).backgroundColor");
  check(before !== after, "theme toggle changes the background (" + before + " -> " + after + ")");
  await ev("document.getElementById('theme-btn').click()");
  // bad slug
  await go("reader.html?story=..%2Fetc");
  check(await ev("document.getElementById('loading').className === 'err'"), "an invalid story id shows an error, not a fetch");

  // ---- layout on the reader and method pages (desktop, then phone)
  const readerSel = [".brand", ".topnav .pill", ".badge", ".story-head .row", ".seg button", ".tool", ".pager .btn"];
  for (const [label, on] of [["1440", false], ["390", true]]) {
    await phone(on);
    await go("index.html");
    await waitFor("document.querySelectorAll('.card').length > 0");
    const a = await layout([".brand", ".topnav .pill", "#levels .pill", ".badge", ".card .row", "#sort", "#frbtn", ".intro h1", ".card h2"]);
    check(a.length === 0, "library single-line text fits at " + label + ": " + JSON.stringify(a));
    for (const slug of ["strange_case_of_dr_jekyll_and_mr_hyde", "jekyll_and_hyde", "east_of_the_sun_and_west_of_the_moon", "alice_in_wonderland"]) {
      const ok = await fetch(base + "data/stories/" + slug + ".json").then(r => r.ok);
      if (!ok) continue;
      await go("reader.html?story=" + slug);
      await waitFor("document.querySelectorAll('.chapter').length > 0");
      const b = await layout(readerSel.concat([".story-head h1", "#chsel", ".readerbar .title"]));
      check(b.length === 0, "reader (" + slug + ") single-line text fits at " + label + ": " + JSON.stringify(b));
    }
    await go("reader.html?story=a_christmas_carol");
    await waitFor("document.querySelectorAll('.chapter').length > 0");
    await ev("document.querySelector('#langseg [data-lang=both]').click()");
    const both = await ev("getComputedStyle(document.querySelector('.pair.two')).gridTemplateColumns.split(' ').length");
    check(label === "1440" ? both === 2 : both === 1, "side by side is " + (label === "1440" ? "two columns" : "stacked") + " at " + label);
    if (process.env.SHOTDIR) {
      await ev("document.documentElement.setAttribute('data-theme', 'light'); window.scrollTo(0, 0)");
      const sh = await send("Page.captureScreenshot", { format: "png" });
      fs.writeFileSync(path.join(process.env.SHOTDIR, "reader-" + label + ".png"), Buffer.from(sh.result.data, "base64"));
      await ev("document.documentElement.removeAttribute('data-theme')");
    }
    const c = await layout(readerSel);
    check(c.length === 0, "reader side-by-side fits at " + label + ": " + JSON.stringify(c));
    await ev("document.querySelector('#langseg [data-lang=en]').click()");
    await go("method.html");
    const m = await layout([".brand", ".topnav .pill"]);
    check(m.length === 0, "method page fits at " + label + ": " + JSON.stringify(m));
  }
  await phone(false);

  check(problems.length === 0, "no console errors or failed requests" + (problems.length ? ": " + problems.slice(0, 5).join(" | ") : ""));
} catch (e) {
  console.error("ERROR " + e.message);
  failures.push(e.message);
}
cleanup();
console.log(failures.length ? "\n" + failures.length + " FAILED" : "\nall checks passed");
process.exit(failures.length ? 1 : 0);
