import { chromium } from 'playwright';
const browser = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-webgl', '--enable-unsafe-swiftshader'] });
const origin = process.env.SMOKE_BASE_URL || 'http://127.0.0.1:8765';
try {
  // A fresh server is insufficient proof: leaving the first match used to
  // strand every subsequent visitor behind a terminal round_finished room.
  for (const visit of [1, 2]) {
    const page = await browser.newPage();
    const failures = [];
    const loaded = new Set();
    let connected = false;
    let authenticated = false;
    let mapReceived = false;
    page.on('pageerror', e => failures.push(String(e)));
    page.on('console', msg => {
      console.log(`[visit ${visit} browser ${msg.type()}] ${msg.text()}`);
      if (msg.text().includes('[Client] Connected to server!')) connected = true;
      if (msg.text().includes('[Client] Authentication successful!')) authenticated = true;
      if (msg.text().includes('[GameView] Map rendered')) mapReceived = true;
      if (/SCRIPT ERROR:|Parse Error:|Failed to load script|Failed to instantiate|Aborted\(/.test(msg.text())) failures.push(msg.text());
    });
    page.on('response', response => {
      const url = new URL(response.url());
      if (/\.(wasm|pck)$/.test(url.pathname) && response.ok()) loaded.add(url.pathname);
      if (response.status() >= 400 && url.origin === origin) failures.push(`${response.status()} ${url.pathname}`);
    });
    try {
      await page.goto(origin + '/', { waitUntil: 'domcontentloaded' });
      const deadline = Date.now() + 120000;
      while ((!connected || !authenticated || !mapReceived) && Date.now() < deadline) await page.waitForTimeout(250);
      if (!connected || !authenticated || !mapReceived) throw new Error(`Visit ${visit} did not reach authenticated map: connected=${connected} authenticated=${authenticated} map=${mapReceived}`);
      await page.waitForTimeout(10000);
      if (!loaded.has('/index.wasm') || !loaded.has('/index.pck')) throw new Error('The browser did not load the Godot WASM and game pack');
      if (failures.length) throw new Error(failures.join('\n'));
      console.log(`PASS: clean visitor ${visit} connected, authenticated and rendered the authoritative map.`);
    } finally {
      await page.screenshot({ path: visit === 1 ? 'browser-startup.png' : 'browser-rejoin.png' }).catch(() => {});
      await page.close();
    }
    await new Promise(resolve => setTimeout(resolve, 1000));
  }
} finally {
  await browser.close();
}
