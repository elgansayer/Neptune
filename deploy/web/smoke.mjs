import assert from 'node:assert/strict';
import {mkdir, writeFile} from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {STATE_MARKER, parseDiagnostic, position, distance, checkRelease, checkConfiguration, checkRoster, checkFreshCountdown, checkCompleteCycle} from './smoke_evidence.mjs';

export function consoleFailure(type, message) {
  return type === 'error' || /(?:^|\n)\s*(?:(?:SCRIPT|USER|SHADER) )?ERROR:|Parse Error:|Failed to load script|Failed to instantiate|Aborted\(|query.?flush|flushing queries/.test(message);
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

export async function runSmoke({browserType, evidenceDirectory} = {}) {
verifyErrorContract();
const chromium = browserType || (await import('playwright')).chromium;
const origin = new URL(process.env.SMOKE_BASE_URL || 'http://127.0.0.1:8765').origin;
const evidenceDir = path.resolve(evidenceDirectory || process.env.SMOKE_EVIDENCE_DIR || 'web-smoke-evidence');
const timeout = Number(process.env.SMOKE_TIMEOUT_MS || '240000');
const expectedDuration = Number(process.env.SMOKE_EXPECT_DURATION || '20');
const expectedCountdown = Number(process.env.SMOKE_EXPECT_COUNTDOWN || '1');
const expectedIntermission = Number(process.env.SMOKE_EXPECT_INTERMISSION || '1');
const expectedRevision = process.env.SMOKE_EXPECT_REVISION || '';
const mode = process.env.SMOKE_MODE || 'full';
assert.ok(Number.isInteger(timeout) && timeout >= 10000 && timeout <= 960000, 'SMOKE_TIMEOUT_MS must be 10000..960000');
assert.ok(Number.isFinite(expectedDuration) && expectedDuration >= 3 && expectedDuration <= 3600, 'Invalid SMOKE_EXPECT_DURATION');
assert.ok(Number.isFinite(expectedCountdown) && expectedCountdown >= 0.1 && expectedCountdown <= 60, 'Invalid SMOKE_EXPECT_COUNTDOWN');
assert.ok(Number.isFinite(expectedIntermission) && expectedIntermission >= 0.1 && expectedIntermission <= 60, 'Invalid SMOKE_EXPECT_INTERMISSION');
assert.ok(['full', 'release'].includes(mode), 'SMOKE_MODE must be full or release');
if (expectedRevision) assert.match(expectedRevision, /^[0-9a-f]{40}$/);
await mkdir(evidenceDir, {recursive: true});
const started = Date.now();
const deadline = started + timeout;
const report = {schema: 1, mode, origin, expected_revision: expectedRevision, expected_duration: expectedDuration,
  expected_countdown: expectedCountdown, expected_intermission: expectedIntermission,
  passing: false, visits: [], cycles: [], actions: [], checks: {}, started_at: new Date().toISOString()};
const errors = [];
const visitors = [];
const launchOptions = {args: ['--use-angle=swiftshader', '--enable-webgl', '--enable-unsafe-swiftshader']};
if (process.env.SMOKE_CHROMIUM_EXECUTABLE) launchOptions.executablePath = process.env.SMOKE_CHROMIUM_EXECUTABLE;
let browser;

function failIfErrors() {
  if (errors.length) throw new Error(errors.slice(0, 20).join('\n'));
  if (Date.now() >= deadline) throw new Error('Full browser acceptance exceeded its explicit execution bound');
}

async function waitFor(visitor, predicate, description, localTimeout = timeout) {
  const until = Math.min(deadline, Date.now() + localTimeout);
  while (Date.now() < until) {
    failIfErrors();
    const value = predicate();
    if (value) return value;
    if (visitor.page.isClosed()) throw new Error(`${description}: page closed`);
    await visitor.page.waitForTimeout(50);
  }
  throw new Error(`Timed out: ${description}; latest=${JSON.stringify(visitor.snapshots.at(-1)?.state.round)}`);
}

function latest(visitor) { return visitor.snapshots.at(-1); }

async function openVisitor(name, context) {
  const page = await context.newPage();
  const visitor = {name, page, snapshots: [], logs: [], logBytes: 0, loaded: new Set(), authCount: 0, connectedCount: 0,
    mapCount: 0, navigations: 0, sockets: [], context};
  visitors.push(visitor);
  page.on('pageerror', error => errors.push(`[${name}] ${error}`));
  page.on('framenavigated', frame => { if (frame === page.mainFrame()) visitor.navigations++; });
  page.on('websocket', socket => {
    const entry = {url: socket.url(), opened_at: new Date().toISOString(), closed: false};
    visitor.sockets.push(entry);
    socket.on('close', () => { entry.closed = true; });
    socket.on('socketerror', error => errors.push(`[${name}] WebSocket ${error}`));
  });
  page.on('console', message => {
    const line = message.text();
    visitor.logBytes += Buffer.byteLength(line, 'utf8');
    if (visitor.logBytes > 16 * 1024 * 1024) {
      if (!errors.some(value => value.includes(`${name}: bounded log`))) errors.push(`${name}: bounded log budget exceeded`);
      return;
    }
    visitor.logs.push(`[${message.type()}] ${line}`);
    if (line.includes('[Client] Connected to server!')) visitor.connectedCount++;
    if (line.includes('[Client] Authentication successful!')) visitor.authCount++;
    if (line.includes('[GameView] Map rendered')) visitor.mapCount++;
    if (consoleFailure(message.type(), line)) errors.push(`[${name}] ${line}`);
    if (line.startsWith(STATE_MARKER)) {
      try {
        const diagnostic = parseDiagnostic(line);
        checkRelease(diagnostic, expectedRevision);
        if (mode === 'full') checkConfiguration(diagnostic, expectedDuration, expectedCountdown, expectedIntermission);
        const previous = latest(visitor);
        if (previous) {
          assert.ok(diagnostic.state.round.epoch >= previous.state.round.epoch, 'Previous-round update reached presentation');
          if (diagnostic.state.round.epoch === previous.state.round.epoch) {
            assert.ok(diagnostic.state.simulation_tick >= previous.state.simulation_tick, 'Simulation tick regressed within epoch');
          }
        }
        if (visitor.snapshots.length >= 12000) throw new Error('Bounded snapshot budget exceeded');
        visitor.snapshots.push(diagnostic);
      } catch (error) { errors.push(`[${name}] ${error}`); }
    }
  });
  page.on('response', response => {
    const url = new URL(response.url());
    if (/\.(wasm|pck)$/.test(url.pathname) && response.ok()) visitor.loaded.add(url.pathname);
    if (response.status() >= 400 && url.origin === origin) errors.push(`[${name}] ${response.status()} ${url.pathname}`);
  });
  await page.goto(origin + '/?smoke=1', {waitUntil: 'domcontentloaded', timeout: Math.min(120000, timeout)});
  await waitFor(visitor, () => visitor.authCount && visitor.mapCount && latest(visitor), `${name} authenticated rendered authoritative map`, 120000);
  assert.ok([...visitor.loaded].some(value => value.endsWith('.wasm')), 'Actual Godot WASM was not loaded');
  assert.ok([...visitor.loaded].some(value => value.endsWith('.pck')), 'Actual Godot game pack was not loaded');
  const headers = await page.request.get(origin + '/', {headers: {'Cache-Control': 'no-cache'}});
  assert.equal(headers.status(), 200, 'Revalidated page failed');
  assert.equal(headers.headers()['cross-origin-opener-policy'], 'same-origin', 'Missing cross-origin opener isolation');
  assert.equal(headers.headers()['cross-origin-embedder-policy'], 'require-corp', 'Missing cross-origin embedder isolation');
  assert.ok(await page.evaluate(() => crossOriginIsolated), 'Browser is not cross-origin isolated');
  await page.locator('canvas').click();
  return visitor;
}

async function screenshot(visitor, label) {
  await visitor.page.screenshot({path: path.join(evidenceDir, `${visitor.name}-${label}.png`)});
}

async function exerciseHuman(visitor, epoch) {
  const peerId = latest(visitor).peer_id;
  const atStart = await waitFor(visitor, () => {
    const value = latest(visitor);
    return value.state.round.epoch === epoch && value.state.round.phase === 'active' && position(value) && !value.state.p[peerId].d && value;
  }, `round ${epoch} living authoritative human`, 10000);
  let moved = 0;
  let movementKey = '';
  let afterMove = atStart;
  for (const key of ['ArrowRight', 'ArrowDown', 'ArrowLeft', 'ArrowUp']) {
    const before = latest(visitor);
    await visitor.page.keyboard.down(key);
    try { await visitor.page.waitForTimeout(550); }
    finally { await visitor.page.keyboard.up(key); }
    afterMove = latest(visitor);
    moved = distance(position(before), position(afterMove));
    if (moved >= 2) { movementKey = key; break; }
  }
  assert.ok(moved >= 2, `Round ${epoch} real arrow input never moved the human`);
  const beforeBombIds = new Set(Object.keys(afterMove.state.b));
  await visitor.page.keyboard.press('Space', {delay: 80});
  const bombSnapshot = await waitFor(visitor, () => visitor.snapshots.find(value =>
    value.state.round.epoch === epoch && value.state.simulation_tick >= afterMove.state.simulation_tick &&
    Object.entries(value.state.b).some(([id, bomb]) => !beforeBombIds.has(id) && bomb.o === peerId)), `round ${epoch} real Space authoritative bomb`, 3000);
  const bombId = Object.entries(bombSnapshot.state.b).find(([id, bomb]) => !beforeBombIds.has(id) && bomb.o === peerId)[0];
  // Escape uses the same browser keyboard path as a person. No RPC, direct
  // state mutation, debug command, invulnerability or time scaling is used.
  await visitor.page.keyboard.down(movementKey);
  try { await visitor.page.waitForTimeout(750); }
  finally { await visitor.page.keyboard.up(movementKey); }
  const action = {epoch, peer_id: peerId, key: movementKey, distance: moved, bomb_id: bombId,
    move_tick: afterMove.state.simulation_tick, bomb_tick: bombSnapshot.state.simulation_tick};
  report.actions.push(action);
  return action;
}

try {
  browser = await chromium.launch(launchOptions);
  const cleanContext = await browser.newContext();
  const first = await openVisitor('primary', cleanContext);
  await screenshot(first, 'entry');
  if (mode === 'release') {
    checkRelease(latest(first), expectedRevision);
    assert.ok(expectedRevision, 'Release verification requires SMOKE_EXPECT_REVISION');
    report.checks = {authenticated_map: true, matching_build_pair: true, actual_wasm_pck: true};
  } else {
    const firstCountdown = await waitFor(first, () => first.snapshots.find(value => value.state.round.phase === 'countdown'), 'first human visible countdown', 10000);
    checkFreshCountdown(firstCountdown);
    const epoch1 = firstCountdown.state.round.epoch;
    const peerId = firstCountdown.peer_id;
    const active1 = await waitFor(first, () => first.snapshots.find(value => value.state.round.epoch === epoch1 && value.state.round.phase === 'active'), 'first active round', 10000);
    checkRoster(active1, [peerId]);
    const lateContext = await browser.newContext();
    let lateError;
    const pendingLate = openVisitor('late', lateContext).catch(error => { lateError = error; return null; });
    const input1 = await exerciseHuman(first, epoch1);
    await screenshot(first, 'battle');
    const late = await pendingLate;
    if (lateError) throw lateError;
    const lateId = latest(late).peer_id;
    const spectating = await waitFor(late, () => late.snapshots.find(value => value.state.round.epoch === epoch1 && value.state.round.phase === 'active'), 'late visitor observes current active arena', 10000);
    assert.ok(!spectating.state.p[lateId], 'Late arrival was inserted into a live battle');
    assert.ok(Array.isArray(spectating.state.room.spectators) && spectating.state.room.spectators.map(String).includes(lateId), 'Late arrival lacks explicit waiting/spectating metadata');
    assert.equal(spectating.view.spectating, true, 'Late visitor did not see the waiting/spectating HUD');
    await screenshot(late, 'spectating');
    const nextCountdown = await waitFor(first, () => first.snapshots.find(value => value.state.round.epoch > epoch1 && value.state.round.phase === 'countdown'), 'same connected human fresh second round');
    const epoch2 = nextCountdown.state.round.epoch;
    checkFreshCountdown(nextCountdown);
    assert.equal(nextCountdown.view.map_signature, firstCountdown.view.map_signature, 'Fresh arena differed from selected original map');
    assert.ok(nextCountdown.view.map_generation > firstCountdown.view.map_generation, 'Fresh round reused retired rendered map');
    const lateAdmitted = await waitFor(late, () => late.snapshots.find(value => value.state.round.epoch === epoch2 && value.state.p[lateId]), 'late human admitted at next countdown', 10000);
    assert.equal(lateAdmitted.state.room.participants[lateId].type, 'human');
    const active2 = await waitFor(first, () => first.snapshots.find(value => value.state.round.epoch === epoch2 && value.state.round.phase === 'active'), 'second active round', 10000);
    checkRoster(active2, [peerId, lateId]);
    const input2 = await exerciseHuman(first, epoch2);
    await exerciseHuman(late, epoch2);
    await waitFor(first, () => first.snapshots.find(value => value.state.round.epoch > epoch2 && value.state.round.phase === 'countdown'), 'two complete cycles and third countdown');
    report.cycles.push(checkCompleteCycle(first.snapshots, epoch1, peerId, input1, [peerId], expectedDuration));
    report.cycles.push(checkCompleteCycle(first.snapshots, epoch2, peerId, input2, [peerId, lateId], expectedDuration));
    assert.equal(first.authCount, 1, 'Repeat play reauthenticated the same human');
    assert.equal(first.connectedCount, 1, 'Repeat play reconnected the same human');
    assert.equal(first.navigations, 1, 'Repeat play navigated/reloaded the page');
    assert.equal(first.sockets.length, 1, 'Repeat play created another transport connection');
    await screenshot(first, 'third-countdown');
    await late.page.close();
    await first.page.close();
    // No observer connection is kept alive here: the actual last human leaves.
    // The native lifecycle suite checks zero unattended scheduling. Browser
    // coverage checks that a later clean human is never stranded by that cleanup.
    const remaining = deadline - Date.now();
    assert.ok(remaining > 15000, 'Insufficient bounded time left for empty-room and reconnect acceptance');
    await new Promise(resolve => setTimeout(resolve, 1500));
    const fresh = await openVisitor('after-empty', cleanContext);
    const resumed = await waitFor(fresh, () => fresh.snapshots.find(value => value.state.round.phase === 'countdown'), 'later first human restarts countdown', 10000);
    checkFreshCountdown(resumed);
    await waitFor(fresh, () => latest(fresh).state.round.phase === 'active', 'fresh visit starts authoritative battle', 10000);
    checkRoster(latest(fresh), [latest(fresh).peer_id]);
    await screenshot(fresh, 'restarted');
    const reloadAuth = fresh.authCount;
    const reloadSnapshots = fresh.snapshots.length;
    await fresh.page.reload({waitUntil: 'domcontentloaded'});
    await waitFor(fresh, () => fresh.authCount > reloadAuth && fresh.snapshots.length > reloadSnapshots && latest(fresh).state.p[latest(fresh).peer_id], 'warm-cache reload reconnect admission', 30000);
    checkRelease(latest(fresh), expectedRevision);
    await screenshot(fresh, 'warm-reconnect');
    report.checks = {actual_wasm_pck: true, matching_build_pair: true, two_cycles_same_connection: true,
      actual_keyboard: true, human_bomb_explosion: true, production_bot_movement_bombs: true,
      fresh_arena_presentation: true, late_spectator_next_round: true, second_human_input: true,
      last_departure_fresh_admission: true, warm_cache_reconnect: true};
  }
  failIfErrors();
  report.passing = true;
  console.log(`PASS: ${mode} browser acceptance${mode === 'full' ? ', two full rounds on one authenticated connection' : ', matching public client/server identity'}.`);
} catch (error) {
  report.error = String(error.stack || error);
  throw error;
} finally {
  for (const visitor of visitors) {
    if (!visitor.page.isClosed()) await screenshot(visitor, 'final').catch(error => errors.push(String(error)));
    const summary = {name: visitor.name, connected: visitor.connectedCount, authenticated: visitor.authCount,
      maps: visitor.mapCount, navigations: visitor.navigations, loaded: [...visitor.loaded], sockets: visitor.sockets,
      snapshots: visitor.snapshots.length, peer_ids: [...new Set(visitor.snapshots.map(value => value.peer_id))]};
    report.visits.push(summary);
    await writeFile(path.join(evidenceDir, `${visitor.name}.log`), visitor.logs.join('\n') + '\n');
    await writeFile(path.join(evidenceDir, `${visitor.name}-states.json`), JSON.stringify(visitor.snapshots, null, 2) + '\n');
    await visitor.page.close();
  }
  report.failures = errors;
  if (errors.length) { report.passing = false; }
  report.wall_seconds = (Date.now() - started) / 1000;
  await writeFile(path.join(evidenceDir, 'report.json'), JSON.stringify(report, null, 2) + '\n');
  if (browser) await browser.close();
}

}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  runSmoke().catch(error => { console.error(error); process.exitCode = 1; });
}
