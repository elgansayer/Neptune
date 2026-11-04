import assert from 'node:assert/strict';

export const STATE_MARKER = 'NEPTUNE_STATE=';
const phases = new Set(['waiting', 'countdown', 'active', 'results']);
const revisionPattern = /^[0-9a-f]{40}$/;

export function parseDiagnostic(line) {
  if (!line.startsWith(STATE_MARKER)) return null;
  const value = JSON.parse(line.slice(STATE_MARKER.length));
  assert.ok(value && typeof value === 'object', 'Missing diagnostic envelope');
  assert.ok(String(value.peer_id).match(/^\d+$/) && Number(value.peer_id) > 1, 'Invalid authenticated peer identity');
  value.peer_id = String(value.peer_id);
  assert.match(value.client_revision || '', revisionPattern, 'Missing client source identity');
  assert.match(value.server_revision || '', revisionPattern, 'Missing server source identity');
  const state = value.state;
  assert.ok(state && typeof state === 'object', 'Missing actual received state');
  assert.ok(Number.isInteger(state.round?.epoch) && state.round.epoch >= 1, 'Missing round epoch');
  assert.ok(phases.has(state.round.phase), 'Missing authoritative phase');
  assert.ok(Number.isFinite(state.round.remaining) && state.round.remaining >= 0, 'Invalid authoritative phase timing');
  assert.equal(typeof state.a, 'boolean', 'Every state must explicitly communicate activation');
  assert.ok(Number.isInteger(state.simulation_tick) && state.simulation_tick >= 0, 'Missing completed simulation tick');
  assert.ok(Number.isFinite(state.server_time) && state.server_time >= 0, 'Missing simulation clock');
  assert.ok(state.p && typeof state.p === 'object', 'Missing authoritative actor snapshot');
  assert.ok(state.b && typeof state.b === 'object', 'Missing authoritative bomb snapshot');
  assert.ok(value.view && typeof value.view === 'object', 'Missing presentation diagnostics');
  return value;
}

export function position(diagnostic, id = diagnostic.peer_id) {
  const point = diagnostic.state.p[String(id)]?.p;
  return Array.isArray(point) && point.length === 2 ? point : null;
}

export function distance(a, b) {
  return a && b ? Math.hypot(a[0] - b[0], a[1] - b[1]) : 0;
}

export function explosionIds(diagnostic) {
  return (diagnostic.state.e || []).map(event => String(event[3]));
}

export function checkRelease(diagnostic, expectedRevision = '') {
  assert.equal(diagnostic.client_revision, diagnostic.server_revision, 'Browser/server release mismatch');
  if (expectedRevision) assert.equal(diagnostic.client_revision, expectedRevision, 'Wrong public/candidate release');
}

export function checkConfiguration(diagnostic, duration, countdown, intermission) {
  assert.deepEqual(diagnostic.state.round.config, {duration, countdown, intermission}, 'Authority announced unexpected room timings');
  assert.equal(diagnostic.state.room?.bot_fill?.target, 4, 'Wrong total casual participant target');
  assert.equal(diagnostic.state.room?.bot_fill?.personality, 'BALANCED', 'Wrong casual production bot profile');
}

export function checkRoster(diagnostic, humanIds, seats = 4) {
  const players = diagnostic.state.p;
  const participants = diagnostic.state.room?.participants;
  assert.ok(participants && typeof participants === 'object', 'Missing explicit participant metadata');
  assert.equal(Object.keys(players).length, seats, 'Wrong actual actor count');
  assert.equal(new Set(Object.keys(players)).size, seats, 'Duplicate actor identity');
  for (const id of Object.keys(players)) {
    assert.equal(participants[id]?.type, humanIds.map(String).includes(id) ? 'human' : 'bot', 'Roster type mismatch');
    if (participants[id].type === 'bot') assert.equal(participants[id].personality, 'BALANCED', 'Wrong configured production bot profile');
    const shown = diagnostic.view.roster?.find(value => String(value.id) === id);
    assert.ok(shown && shown.type === participants[id].type, 'Participant identity was not presented in HUD');
    if (participants[id].type === 'bot') assert.match(shown.label, /BOT/, 'Real bot is not visibly labeled');
  }
  for (const id of humanIds) assert.ok(players[String(id)], `Human ${id} was not admitted`);
  return Object.keys(players).filter(id => participants[id].type === 'bot');
}

export function checkFreshCountdown(diagnostic) {
  assert.equal(diagnostic.state.round.phase, 'countdown');
  assert.equal(diagnostic.state.a, false, 'Countdown is already active');
  assert.ok(diagnostic.state.round.remaining > 0, 'Countdown was truncated before presentation');
  assert.equal(Object.keys(diagnostic.state.b).length, 0, 'Bombs survived the round boundary');
  assert.equal((diagnostic.state.e || []).length, 0, 'Explosion events survived the round boundary');
  const view = diagnostic.view;
  assert.equal(view.epoch, diagnostic.state.round.epoch, 'View retained a previous round');
  assert.equal(view.map_epoch, diagnostic.state.round.epoch, 'Fresh reliable map was not rendered');
  assert.equal(view.game_over, false, 'Client retained game-over state');
  assert.equal(view.result_text, '', 'Client retained its visible result label');
  assert.equal(view.winner_id, '', 'Client retained winner identity');
  assert.equal(view.removed_dead_players, 0, 'Client retained dead-player registry');
  for (const field of ['bombs', 'explosions', 'items', 'eggs', 'mounts', 'hurry', 'seen_explosions']) {
    assert.equal(view[field], 0, `Client retained ${field}`);
  }
  assert.ok(typeof view.map_signature === 'string' && view.map_signature.length > 0, 'Missing actual fresh map identity');
  assert.equal(view.controls_visible, true, 'Actual keyboard controls are not visible');
  assert.ok(view.round_text?.includes(diagnostic.client_revision.slice(0, 7)), 'Compact client build identity is not visible');
  assert.match(view.round_text, /Starts in [1-9]/, 'Authoritative countdown is not visible');
}

export function checkCompleteCycle(observations, epoch, peerId, input, expectedHumans, expectedDuration) {
  const round = observations.filter(value => value.state.round.epoch === epoch);
  assert.ok(round.length > 0, `No execution for round ${epoch}`);
  const countdown = round.find(value => value.state.round.phase === 'countdown');
  assert.ok(countdown, 'No visible countdown');
  checkFreshCountdown(countdown);
  const active = round.filter(value => value.state.round.phase === 'active');
  assert.ok(active.length >= 2, 'No progressing authoritative battle');
  const bots = checkRoster(active[0], expectedHumans);
  assert.ok(active[0].state.round.remaining <= expectedDuration && active[0].state.round.remaining > expectedDuration - 2,
    'Configured battle duration was not observed');
  assert.ok(active.some(value => value.state.round.remaining < active[0].state.round.remaining - 0.25), 'Authoritative battle timer did not decrease');
  assert.ok(active.every(value => /Battle/.test(value.view.round_text)), 'Active battle phase is not visible');
  assert.ok(active.some(value => value.view.timer_text !== active[0].view.timer_text), 'Actual HUD battle timer did not decrease');
  assert.ok(active.every(value => value.peer_id === peerId), 'Connected human identity changed within the round');
  for (const id of bots) {
    const first = active.find(value => position(value, id));
    assert.ok(first && active.some(value => distance(position(first, id), position(value, id)) >= 2), `Production bot ${id} never moved`);
  }
  const bombOwners = new Map();
  for (const value of active) for (const [id, bomb] of Object.entries(value.state.b)) {
    assert.equal(typeof bomb.o, 'string', 'Bomb did not expose actual authoritative owner');
    bombOwners.set(id, bomb.o);
  }
  assert.ok([...bombOwners.values()].some(id => bots.includes(id)), 'Production bots placed no authoritative bomb');
  assert.ok(input && input.epoch === epoch && input.peer_id === peerId && input.distance >= 2, 'Real keyboard input did not move the authoritative human');
  assert.ok(input.bomb_id && bombOwners.get(input.bomb_id) === peerId, 'Space did not place an authoritative human bomb');
  assert.ok(round.some(value => explosionIds(value).includes(input.bomb_id)), 'The human bomb did not produce a real authoritative explosion');
  const result = round.find(value => value.state.round.phase === 'results');
  assert.ok(result, 'No authoritative terminal result');
  assert.equal(result.state.a, false, 'Terminal snapshot omitted explicit inactive state');
  assert.ok(['timeout', 'survivors'].includes(result.state.round.result?.reason), 'No gameplay-driven settlement reason');
  assert.ok(typeof result.state.round.result.winner_id === 'string', 'No authoritative winner/draw identity');
  assert.equal(result.view.game_over, true, 'Result did not reach presentation');
  assert.match(result.view.result_text, /DRAW|Winner:/, 'Authoritative winner or draw is not visible');
  assert.ok(observations.some(value => value.state.round.epoch > epoch && value.state.round.phase === 'countdown'), 'Same session never received the next fresh countdown');
  return {epoch, peer_id: peerId, bot_ids: bots, bot_bombs: [...bombOwners].filter(([, owner]) => bots.includes(owner)).map(([id]) => id),
    human_input: input, result: result.state.round.result, first_remaining: active[0].state.round.remaining,
    last_remaining: active.at(-1).state.round.remaining, map_signature: countdown.view.map_signature};
}
