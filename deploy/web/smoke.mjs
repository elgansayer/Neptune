import { pathToFileURL } from 'node:url';

export function consoleFailure(type, message) {
  return type === 'error' || /(?:^|\n)\s*(?:(?:SCRIPT|USER|SHADER) )?ERROR:|Parse Error:|Failed to load script|Failed to instantiate|Aborted\(/.test(message);
}

// Every real smoke first checks the actual engine diagnostic that the previous
// gate accepted as healthy. Warnings and ordinary log text remain diagnostics.
export function verifyErrorContract() {
  for (const [type, message, expected] of [
    ['error', "ERROR: Animation 'default' doesn't exist.", true],
    ['log', "ERROR: Animation 'default' doesn't exist.\n   at: get_frame_count (scene/resources/sprite_frames.cpp:71)", true],
    ['log', 'SCRIPT ERROR: Invalid access to property playing', true],
    ['error', 'WebAssembly exception', true],
    ['log', '[Client] Connected to server!', false],
    ['warning', 'WebGL fallback selected', false],
    ['log', 'Native assertions: 0 errors', false],
  ]) {
    if (consoleFailure(type, message) !== expected) throw new Error(`Browser error detector rejected its contract: ${message}`);
  }
}

export async function runSmoke({ browserType } = {}) {
  verifyErrorContract();
  const chromium = browserType || (await import('playwright')).chromium;
  const browser = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-webgl', '--enable-unsafe-swiftshader'] });
  const origin = process.env.SMOKE_BASE_URL || 'http://127.0.0.1:8765';
  try {
    // A fresh server is insufficient proof: leaving the first match used to
    // strand every subsequent visitor behind a terminal round_finished room.
    for (const visit of [1, 2]) {
      const page = await browser.newPage();
      const failures = new Set();
      const loaded = new Set();
      let connected = false;
      let authenticated = false;
      let mapReceived = false;
      page.on('pageerror', e => failures.add(String(e)));
      page.on('console', msg => {
        console.log(`[visit ${visit} browser ${msg.type()}] ${msg.text()}`);
        if (msg.text().includes('[Client] Connected to server!')) connected = true;
        if (msg.text().includes('[Client] Authentication successful!')) authenticated = true;
        if (msg.text().includes('[GameView] Map rendered')) mapReceived = true;
        if (consoleFailure(msg.type(), msg.text())) failures.add(msg.text());
      });
      page.on('response', response => {
        const url = new URL(response.url());
        if (/\.(wasm|pck)$/.test(url.pathname) && response.ok()) loaded.add(url.pathname);
        if (response.status() >= 400 && url.origin === origin) failures.add(`${response.status()} ${url.pathname}`);
      });
      try {
        await page.goto(origin + '/', { waitUntil: 'domcontentloaded' });
        const deadline = Date.now() + 120000;
        while ((!connected || !authenticated || !mapReceived) && Date.now() < deadline) await page.waitForTimeout(250);
        if (!connected || !authenticated || !mapReceived) throw new Error(`Visit ${visit} did not reach authenticated map: connected=${connected} authenticated=${authenticated} map=${mapReceived}`);
        await page.waitForTimeout(10000);
        if (!loaded.has('/index.wasm') || !loaded.has('/index.pck')) throw new Error('The browser did not load the Godot WASM and game pack');
        if (failures.size) throw new Error([...failures].join('\n'));
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
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  if (process.argv.includes('--verify-error-contract')) {
    verifyErrorContract();
    console.log('PASS: recorded browser engine errors fail the smoke contract.');
  } else {
    await runSmoke();
  }
}
