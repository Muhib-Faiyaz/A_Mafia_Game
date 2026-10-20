// Run with node tests/test_music.cjs. Exercise audio behavior without a device.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('static/game.js', 'utf8');
let starts = 0;
const ramps = [];
let allowAudio = false;
class AudioContext {
  state = 'suspended';
  currentTime = 10;
  destination = {};
  addEventListener() {}
  resume() {
    if (!allowAudio) return Promise.reject(new Error('Gesture required'));
    this.state = 'running';
    return Promise.resolve();
  }
  createGain() {
    return {connect() {}, disconnect() {}, gain: {
      setValueAtTime() {}, setTargetAtTime() {}, cancelAndHoldAtTime() {},
      linearRampToValueAtTime(value, time) { ramps.push([value, time]); },
    }};
  }
  createDynamicsCompressor() { return {threshold: {}, ratio: {}, connect() {}}; }
  createBufferSource() {
    return {connect() {}, disconnect() {}, start() { starts++; }, stop() {}};
  }
}
const sandbox = {
  window: {AudioContext}, document: {hidden: false}, state: null,
  $: () => ({setAttribute() {}}), toast: message => {throw Error(message);},
};
vm.createContext(sandbox);
vm.runInContext(source.slice(source.indexOf('const SOUNDTRACK ='), source.indexOf('function openHelp()')) + ';globalThis.music = music;', sandbox);
const music = sandbox.music;
music.loadTrack = async () => ({});
const flush = () => new Promise(resolve => setImmediate(resolve));
(async () => {
  music.start(); await flush();
  assert.equal(starts, 0, 'blocked autoplay must wait for interaction');
  allowAudio = true;
  music.start(); await flush();
  assert.equal(starts, 1, 'first gesture starts landing-page music');
  assert.equal(music.activeTrack.source.loop, true);
  assert.ok(ramps.some(([value, time]) => value === 0.9 && time === 12), 'two-second fade-in');
  for (const state of [{phase: 'lobby'}, {phase: 'night', night_step: 'mafia'}, {phase: 'day', voting: true}]) {
    sandbox.state = state; music.sync(); await flush();
  }
  assert.equal(starts, 1, 'phase changes must not restart the soundtrack');
  await music.toggle(); music.start(); await flush();
  assert.equal(starts, 1, 'explicit mute prevents automatic restart');
  await music.toggle(); await flush(); assert.equal(starts, 2);
  sandbox.document.hidden = true; music.sync();
  assert.equal(music.requestedTrack, '');
  sandbox.document.hidden = false; music.sync(); await flush();
  assert.equal(starts, 3);
  sandbox.state = {phase: 'over'}; music.sync();
  assert.equal(music.requestedTrack, '', 'game end stops music');
  console.log('Music checks passed: blocked autoplay, gesture retry, landing/lobby, fade-in, continuity, mute, visibility and game end.');
})().catch(error => {console.error(error); process.exitCode = 1;});
