import test from 'node:test';
import assert from 'node:assert/strict';
import {STATE_MARKER, parseDiagnostic, checkRelease, checkConfiguration, checkFreshCountdown, checkCompleteCycle} from './smoke_evidence.mjs';

const revision = 'a'.repeat(40);
function diagnostic(phase = 'countdown', epoch = 1, tick = 1) {
  const p = {'42': {p: [24, 24]}, '-1': {p: [40, 24]}, '-2': {p: [56, 24]}, '-3': {p: [72, 24]}};
  return {peer_id: '42', client_revision: revision, server_revision: revision,
    state: {round: {epoch, phase, remaining: phase === 'active' ? 12 : 1, result: {}},
      a: phase === 'active', simulation_tick: tick, server_time: tick * 16, p, b: {},
      room: {participants: Object.fromEntries(Object.keys(p).map(id => [id, {type: id === '42' ? 'human' : 'bot', personality: 'BALANCED'}]))}},
    view: {epoch, map_epoch: epoch, map_signature: 'actual-map-hash', game_over: phase === 'results', winner_id: '',
      timer_text: '0:12', round_text: `DEMO · ${revision.slice(0, 12)} · Round ${epoch} · ${phase === 'countdown' ? 'Starts in 1' : 'Battle'}`,
      result_text: phase === 'results' ? 'DRAW' : '',
      removed_dead_players: 0, bombs: 0, explosions: 0, items: 0, eggs: 0, mounts: 0, hurry: 0, seen_explosions: 0, controls_visible: true,
      roster: Object.keys(p).map(id => ({id, type: id === '42' ? 'human' : 'bot', label: id === '42' ? 'Human' : 'BOT Balanced'}))}};
}
function cycle() {
  const countdown = diagnostic();
  const first = diagnostic('active', 1, 60);
  first.state.b = {'human-bomb': {o: '42'}, 'bot-bomb': {o: '-1'}};
  const later = diagnostic('active', 1, 90);
  later.state.round.remaining = 11.5;
  later.view.timer_text = '0:11';
  for (const actor of Object.values(later.state.p)) actor.p[0] += 4;
  later.state.e = [[1, 1, [[257, 0]], 'human-bomb', 100]];
  const result = diagnostic('results', 1, 780);
  result.state.round.result = {reason: 'timeout', winner_id: '', survivors: ['42', '-1']};
  return [countdown, first, later, result, diagnostic('countdown', 2, 1)];
}
const input = {epoch: 1, peer_id: '42', distance: 4, bomb_id: 'human-bomb'};

test('missing, malformed and empty execution cannot become passing browser evidence', () => {
  assert.equal(parseDiagnostic('unrelated log'), null);
  assert.throws(() => parseDiagnostic(STATE_MARKER + '{'));
  assert.throws(() => parseDiagnostic(STATE_MARKER + '{}'));
  assert.throws(() => checkCompleteCycle([], 1, '42', input, ['42'], 12), /No execution/);
  const broken = diagnostic();
  delete broken.state.a;
  assert.throws(() => parseDiagnostic(STATE_MARKER + JSON.stringify(broken)), /explicitly communicate/);
});

test('release evidence rejects unversioned and mismatched actual peers', () => {
  const value = diagnostic();
  assert.equal(parseDiagnostic(STATE_MARKER + JSON.stringify(value)).peer_id, '42');
  checkRelease(value, revision);
  value.server_revision = 'b'.repeat(40);
  assert.throws(() => checkRelease(value, revision), /mismatch/);
  value.client_revision = 'development';
  assert.throws(() => parseDiagnostic(STATE_MARKER + JSON.stringify(value)), /source identity/);
});

test('complete evidence requires real human and bot actions, explosion, result and subsequent countdown', () => {
  assert.equal(checkCompleteCycle(cycle(), 1, '42', input, ['42'], 12).epoch, 1);
  for (const mutation of [
    values => { values[2].state.e = []; },
    values => { delete values[1].state.b['bot-bomb']; },
    values => { for (const id of ['-1', '-2', '-3']) values[2].state.p[id].p[0] -= 4; },
    values => { values[3].state.a = true; },
    values => { values[3].state.round.result.reason = 'stopped'; },
    values => { values.pop(); },
    values => { values[1].view.roster[1].label = 'Participant'; },
    values => { values[2].view.timer_text = '0:12'; },
    values => { values[3].view.result_text = ''; },
  ]) {
    const values = cycle();
    mutation(values);
    assert.throws(() => checkCompleteCycle(values, 1, '42', input, ['42'], 12));
  }
});

test('fresh-round acceptance rejects each stale presentation registry', () => {
  for (const field of ['bombs', 'explosions', 'items', 'eggs', 'mounts', 'hurry', 'seen_explosions', 'removed_dead_players']) {
    const value = diagnostic();
    value.view[field] = 1;
    assert.throws(() => checkFreshCountdown(value), /retained/);
  }
  const retired = diagnostic();
  retired.view.map_epoch = 0;
  assert.throws(() => checkFreshCountdown(retired), /Fresh reliable map/);
});

test('normal demo and bounded CI timing remain separate explicit trusted configurations', () => {
  const value = diagnostic();
  value.state.round.config = {duration: 180, countdown: 3, intermission: 5};
  value.state.room.bot_fill = {target: 4, personality: 'BALANCED'};
  checkConfiguration(value, 180, 3, 5);
  assert.throws(() => checkConfiguration(value, 20, 1, 1), /unexpected room timings/);
  value.state.room.bot_fill.target = 0;
  assert.throws(() => checkConfiguration(value, 180, 3, 5), /participant target/);
});
