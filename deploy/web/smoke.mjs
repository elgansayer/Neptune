import { chromium } from 'playwright';
const browser = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-webgl', '--enable-unsafe-swiftshader'] });
const page = await browser.newPage();
const failures = [];
const loaded = new Set();
let connected = false;
let authenticated = false;
let mapReceived = false;
page.on('pageerror', e => failures.push(String(e)));
page.on('console', msg => {
  console.log(`[browser ${msg.type()}] ${msg.text()}`);
  if (msg.text().includes("[Client] Connected to server!")) connected = true;
  if (msg.text().includes("[Client] Authentication successful!")) authenticated = true;
  if (msg.text().includes("[GameView] Map rendered")) mapReceived = true;
  if (/SCRIPT ERROR:|Parse Error:|Failed to load script|Failed to instantiate|Aborted\(/.test(msg.text())) failures.push(msg.text());
});
page.on('response', response => {
  const url = new URL(response.url());
  if (/\.(wasm|pck)$/.test(url.pathname) && response.ok()) loaded.add(url.pathname);
  if (response.status() >= 400 && url.origin === 'http://127.0.0.1:8765') failures.push(`${response.status()} ${url.pathname}`);
});
try {
  await page.goto('http://127.0.0.1:8765/', { waitUntil: 'domcontentloaded' });
  const deadline = Date.now() + 120000;
  while ((!connected || !authenticated || !mapReceived) && Date.now() < deadline) await page.waitForTimeout(250);
  if (!connected || !authenticated || !mapReceived) throw new Error(`Game did not reach authenticated map: connected=${connected} authenticated=${authenticated} map=${mapReceived}`);
  await page.waitForTimeout(10000);
  if (!loaded.has('/index.wasm') || !loaded.has('/index.pck')) throw new Error('The browser did not load the Godot WASM and game pack');
  if (failures.length) throw new Error(failures.join('\n'));
  await page.screenshot({ path: 'browser-startup.png' });
  console.log('PASS: browser connected to the real Godot server, authenticated and rendered its map.');
} finally {
  await page.screenshot({ path: 'browser-startup.png' }).catch(() => {});
  await browser.close();
}
