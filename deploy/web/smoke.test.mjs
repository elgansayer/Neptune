import assert from 'node:assert/strict';
import test from 'node:test';
import { consoleFailure, verifyErrorContract, runSmoke } from './smoke.mjs';

test('the recorded mounted Tirra diagnostic fails on every console channel', () => {
  const diagnostic = "ERROR: Animation 'default' doesn't exist.\n   at: get_frame_count (scene/resources/sprite_frames.cpp:71)";
  for (const channel of ['error', 'log', 'warning']) assert.equal(consoleFailure(channel, diagnostic), true);
  verifyErrorContract();
});

test('engine, script, shader and JavaScript console errors block success', () => {
  for (const message of ['ERROR: Missing texture', 'USER ERROR: Assertion failed', 'SHADER ERROR: Compilation failed', '\n  SCRIPT ERROR: Invalid access', 'Parse Error: bad token', 'Failed to instantiate scene', 'Aborted(native error)']) {
    assert.equal(consoleFailure('log', message), true, message);
  }
  assert.equal(consoleFailure('error', 'unprefixed worker exception'), true);
});

test('ordinary diagnostics and warnings do not invent failures', () => {
  for (const message of ['[GameView] Map rendered', 'Connected to server!', '0 errors', "Animation name contains 'default'", 'WebGL fallback selected']) {
    assert.equal(consoleFailure('log', message), false, message);
    assert.equal(consoleFailure('warning', message), false, message);
  }
});

test('the actual console event handler blocks smoke success and closes the browser', async () => {
  const listeners = new Map();
  let pageClosed = false;
  let browserClosed = false;
  const origin = process.env.SMOKE_BASE_URL || 'http://127.0.0.1:8765';
  const page = {
    on: (event, callback) => listeners.set(event, callback),
    goto: async () => {
      for (const text of ['[Client] Connected to server!', '[Client] Authentication successful!', '[GameView] Map rendered']) {
        listeners.get('console')({ type: () => 'log', text: () => text });
      }
      for (const path of ['/index.wasm', '/index.pck']) {
        listeners.get('response')({ url: () => origin + path, ok: () => true, status: () => 200 });
      }
      listeners.get('console')({ type: () => 'error', text: () => "ERROR: Animation 'default' doesn't exist." });
    },
    waitForTimeout: async () => {},
    screenshot: async () => {},
    close: async () => { pageClosed = true; },
  };
  const browserType = { launch: async () => ({
    newPage: async () => page,
    close: async () => { browserClosed = true; },
  }) };
  // Controlled adapter: exercises runSmoke's real registered callbacks and
  // failure path, without claiming an actual browser/server run.
  await assert.rejects(runSmoke({ browserType }), /Animation 'default' doesn't exist/);
  assert.equal(pageClosed, true);
  assert.equal(browserClosed, true);
});
