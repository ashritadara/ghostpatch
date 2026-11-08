// Exercise the actual standalone controller without a browser or backend mutations.
// This verifies the iframe protocol, not React hydration or visual layout.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const html = fs.readFileSync(path.join(__dirname, "..", "cyberpunk_front.html"), "utf8");
const source = html.match(/<script>([\s\S]*?)<\/script>/)[1];
const nodes = new Map(), windowEvents = {}, documentEvents = {}, frames = new Map(), timers = new Map();
const sent = [];
let nextId = 0, sourceAssignments = 0, clock = 0;
const motionPreference = { matches: true, addEventListener() {} };
function node(id) {
  if (!nodes.has(id)) nodes.set(id, {
    id, style: {}, dataset: {}, handlers: {}, hidden: false, inert: false,
    addEventListener(type, callback) { this.handlers[type] = callback; },
    setAttribute(key, value) { this[key] = value; },
    getBoundingClientRect: () => ({ width: 1600, height: 900, left: 0, top: 0 }),
    focus() {}, querySelector: () => null, querySelectorAll: () => [], matches: () => false,
  });
  return nodes.get(id);
}
const canvas = node("scene"); canvas.getContext = () => null;
const iframe = node("workspace-frame");
iframe.contentWindow = { postMessage(data, origin) { sent.push({ data, origin }); } };
Object.defineProperty(iframe, "src", { get() { return this.url; }, set(value) { this.url = value; sourceAssignments++; } });
const buttons = Array.from({ length: 6 }, (_, i) => Object.assign(node("chapter-" + i), { dataset: { chapter: String(i) } }));
const document = {
  getElementById: node, querySelectorAll: () => buttons, querySelector: () => buttons[0],
  documentElement: { scrollHeight: 5850 }, activeElement: null, hidden: false,
  addEventListener(type, callback) { documentEvents[type] = callback; },
};
const window = {
  scrollY: 0, innerHeight: 900, devicePixelRatio: 1,
  matchMedia: () => motionPreference,
  addEventListener(type, callback) { windowEvents[type] = callback; },
  scrollTo({ top }) { this.scrollY = top; windowEvents.scroll(); },
};
vm.runInNewContext(source, {
  window, document, console,
  requestAnimationFrame(callback) { const id = ++nextId; frames.set(id, callback); return id; },
  cancelAnimationFrame(id) { frames.delete(id); },
  setTimeout(callback) { const id = ++nextId; timers.set(id, callback); return id; },
  clearTimeout(id) { timers.delete(id); },
});
function tick() {
  const [id, callback] = frames.entries().next().value;
  frames.delete(id); callback(clock += 16);
}
function flush() {
  let count = 0;
  while (frames.size) {
    assert.ok(++count < 600, "Scene must settle without autoplay");
    tick();
  }
}
function receive(data, origin = "http://127.0.0.1:3000", from = iframe.contentWindow) {
  windowEvents.message({ source: from, origin, data: { channel: "ghostpatch-workspace", ...data } });
  flush();
}
flush();
const api = window.cyberpunkFront, shell = node("workspace-shell");
assert.equal(api.chapter, 0);
assert.equal(shell.hidden, true);
assert.equal(sourceAssignments, 0, "Intro must not load an invisible backend iframe");
api.goToChapter(1); flush();
assert.equal(shell.hidden, false);
assert.equal(iframe.src, "http://127.0.0.1:3000/scene-workspace");
assert.equal(sourceAssignments, 1);
receive({ type: "ready" }, "https://untrusted.example");
receive({ type: "ready" }, "http://127.0.0.1:3000", {});
assert.equal(sent.length, 0, "Unknown origins/windows cannot complete the handshake");
receive({ type: "ready" });
assert.equal(shell.dataset.ready, "true");
assert.equal(sent.at(-1).data.chapter, 1);
assert.equal(sent.at(-1).origin, "http://127.0.0.1:3000");
assert.ok(sent.some(item => item.data.type === "viewport" && item.data.width === 1600), "Child typography receives the full scene width rather than the narrow iframe width");
assert.equal(timers.size, 0);
for (const chapter of ["2", -1, 6, 1.5, null]) receive({ type: "navigate", chapter });
assert.equal(api.chapter, 1, "Malformed/out-of-range chapter messages are ignored");
receive({ type: "execute", approved: true, consent_to_model: true });
assert.equal(api.chapter, 1, "Messages cannot grant consent or execute a plan");
receive({ type: "navigate", chapter: 5 }, "https://untrusted.example");
assert.equal(api.chapter, 1);
for (let chapter = 2; chapter < 6; chapter++) {
  receive({ type: "navigate", chapter });
  assert.equal(api.chapter, chapter);
  assert.equal(sent.at(-1).data.chapter, chapter);
  assert.equal(node("photo-background").style.opacity, "1");
}
assert.equal(sourceAssignments, 1, "Page changes must retain the same iframe and its repository/job state");
const progress = api.progress;
receive({ type: "pointer", x: 200, y: 200, pointerType: "mouse" });
assert.match(node("cursor-ghost").style.transform, /translate3d/);
assert.equal(node("cursor-glow").style.opacity, "1");
assert.equal(api.progress, progress, "Cursor movement must never advance the scene");
receive({ type: "pointerleave" });
assert.equal(node("cursor-ghost").style.opacity, "0");
assert.equal(node("cursor-glow").style.opacity, "1", "Moving out of the embedded controls keeps the pointer glow continuous");
receive({ type: "navigate", chapter: 0 });
assert.equal(shell.hidden, true);
assert.equal(sent.at(-1).data.chapter, 0, "Returning to the intro dismisses any pending child approval");
assert.equal(node("photo-background").style.opacity, "1");
api.goToChapter(1); flush();
assert.equal(sourceAssignments, 1, "Rewinding to intro must not discard the loaded workflow");
assert.equal(sent.at(-1).data.chapter, 1);
assert.equal(api.isAnimating, false);
motionPreference.matches = false;
const beforeMotion = clock;
api.goToChapter(2); tick();
assert.equal(api.isAnimating, true);
assert.equal(sent.at(-1).data.chapter, 1, "Outgoing workspace remains until its fade finishes");
for (let i = 0; i < 20; i++) tick();
assert.ok(api.progress > .17 && api.progress < .37, "Arrow travel interpolates between pages");
assert.equal(sent.at(-1).data.chapter, 1);
assert.ok(Number.parseFloat(shell.style.translate.split(" ")[1]) < 0, "The outgoing interface travels up when advancing down");
assert.equal(shell.style.opacity, "1", "Vertical travel moves the page rather than fading it away");
assert.equal(node("photo-background").style.transform, "translate3d(0,0,0)", "Photos crossfade without sliding past each other");
assert.ok(Number(node("background-transition-shade").style.opacity) > 0, "A dark magenta blend masks the middle-page picture seams");
assert.equal(node("photo-background-next").dataset.chapter, "2");
for (let i = 0; i < 35; i++) tick();
assert.ok(Number.parseFloat(shell.style.translate.split(" ")[1]) > 0, "The next interface enters from below");
flush();
assert.equal(api.chapter, 2);
assert.equal(sent.at(-1).data.chapter, 2);
assert.ok(clock - beforeMotion >= 1550, "Arrow travel has a deliberate duration");
assert.equal(api.isAnimating, false);
assert.equal(shell.style.translate, "0 0.00px");
assert.equal(node("photo-background-next").style.opacity, "0", "The extra background layer is hidden after arrival");
assert.equal(node("background-transition-shade").style.opacity, "0");
receive({ type: "inspector", open: true });
assert.equal(node("viewport").dataset.inspectorOpen, "true");
receive({ type: "inspector", open: false }, "https://untrusted.example");
receive({ type: "inspector", open: "false" });
assert.equal(node("viewport").dataset.inspectorOpen, "true", "Only validated inspector messages affect layout");
receive({ type: "inspector", open: false });
assert.equal(node("viewport").dataset.inspectorOpen, "false");
const beforeJump = sent.length, jumpStart = window.scrollY;
api.goToChapter(5); tick();
for (let i = 0; i < 20; i++) tick();
assert.equal(window.scrollY, jumpStart, "Long jumps do not scroll through other chapters");
flush();
assert.equal(api.chapter, 5);
assert.ok(sent.slice(beforeJump).every(item => item.data.chapter === 5));
assert.equal(node("advance").disabled, true);
node("advance").handlers.click(); flush();
assert.equal(api.chapter, 5, "The final arrow never wraps back through the assets");
assert.equal(api.progress, 1);
assert.equal(node("scene").style.opacity, "1");
api.goToChapter(1); flush();
api.goToChapter(2); tick();
node("advance").handlers.click(); flush();
assert.equal(api.chapter, 3, "Rapid next clicks advance from the chosen destination");
api.goToChapter(4); tick();
windowEvents.wheel();
window.scrollY = .17 * 4950; windowEvents.scroll(); flush();
assert.equal(api.chapter, 1, "Manual input interrupts arrow travel");
assert.equal(api.isAnimating, false);
motionPreference.matches = true;
api.goToChapter(2); flush();
const boundary = (.37 + .58) / 2;
window.scrollY = (boundary + .003) * 4950; windowEvents.scroll(); flush();
assert.equal(api.chapter, 2, "Small scroll-boundary jitter keeps the existing panel");
window.scrollY = (boundary + .012) * 4950; windowEvents.scroll(); flush();
assert.equal(api.chapter, 3, "Deliberate manual scrolling still changes pages");
window.scrollY = (boundary - .003) * 4950; windowEvents.scroll(); flush();
assert.equal(api.chapter, 3, "Reverse jitter does not flicker between panels");
window.scrollY = (boundary - .012) * 4950; windowEvents.scroll(); flush();
assert.equal(api.chapter, 2);
assert.equal(sourceAssignments, 1, "Navigation fixes must not reload or reset the backend interface");
assert.ok(html.includes('title="GhostPatch real backend workflow"'));
assert.ok(html.includes('id="workspace-retry"'));
// Exercise the real draw function with a recording renderer: the foreground
// drone must leave below the canvas before the robot is substantially visible.
const recorded = [], droneAsset = {};
const drawing = {
  ctx: new Proxy({}, { get: () => () => {} }), width: 1600, height: 900, dpr: 1, mobile: false,
  drone: droneAsset, vehicle: {}, sentinel: () => ({}), glow() {}, flare() {}, skyline() {}, alley() {},
  model(asset, x, y, scale, rotation, alpha) { recorded.push({ asset, x, y, scale, alpha }); return () => [0, 0]; },
};
const helperSource = source.slice(source.indexOf("  const clamp="), source.indexOf("  const poly="));
const drawingSource = source.slice(source.indexOf("  function draw("), source.indexOf("  function opacity("));
vm.runInNewContext(helperSource + drawingSource + "globalThis.drawScene=draw;", drawing);
function foregroundDrone(t) {
  recorded.length = 0; drawing.drawScene(t, true, false);
  return recorded.find(item => item.asset === droneAsset && item.scale !== 55);
}
assert.ok(foregroundDrone(1.1).y < 900, "The foreground drone is still visible while leaving import");
const leavingDrone = foregroundDrone(1.45);
assert.ok(leavingDrone.y - leavingDrone.scale > 900, "The drone fully exits below the viewport before the robot entrance");
assert.equal(foregroundDrone(1.86), undefined, "No drone remains parked behind the robot on analysis");
const facades = [];
const closingScene = {
  width: 1600, height: 900, mobile: false,
  corridor: { complete: true, naturalWidth: 724, naturalHeight: 2172 },
  ctx: { globalAlpha: 1, save() {}, restore() {}, fillRect() {}, drawImage(...args) { facades.push(args); } },
};
const closingSource = source.slice(source.indexOf("  function paintFacades("), source.indexOf("  function draw("));
vm.runInNewContext(helperSource + closingSource + "globalThis.closeBuildings=closingFacades;globalThis.introBuildings=introFacades;", closingScene);
closingScene.closeBuildings(3.95);
assert.equal(facades.length, 0, "Diamond 5 has the atrium photo without the closing foreground");
closingScene.closeBuildings(4.55);
const entering = facades.splice(0);
closingScene.closeBuildings(5);
assert.equal(entering.length, 2);
assert.equal(facades.length, 2);
assert.ok(facades[0][5] > entering[0][5], "The left facade moves inward toward diamond 6");
assert.ok(facades[1][5] < entering[1][5], "The right facade moves inward toward diamond 6");
assert.equal(facades[0][6], entering[0][6], "Final pillars keep their vertical placement as they close");
assert.equal(facades[0][3], 362, "Closing uses the original separate left/right source crops");
facades.length = 0;
closingScene.introBuildings(0);
const introStart = facades.splice(0);
closingScene.introBuildings(.85);
assert.equal(facades.length, 2);
assert.ok(facades[0][5] > introStart[0][5], "The first left pillar closes inward between diamonds 1 and 2");
assert.ok(facades[1][5] < introStart[1][5], "The first right pillar closes inward between diamonds 1 and 2");
assert.equal(facades[0][6], introStart[0][6], "Intro pillars close horizontally without moving up or down");
motionPreference.matches = false;
for (const [from, to] of [[0, 1], [4, 5]]) {
  api.goToChapter(from); flush();
  api.goToChapter(to); tick();
  for (let i = 0; i < 35; i++) tick();
  assert.equal(node("photo-background").style.transform, "translate3d(0,0,0)");
  assert.equal(node("photo-background-next").style.opacity, "0", "Shared first/last backgrounds do not shift or duplicate");
  assert.equal(node("background-transition-shade").style.opacity, "0", "Shared first/last backgrounds remain uninterrupted");
  flush();
}
console.log("PASS: persistent workflow, inspector message validation, timed arrow travel, fade jumps, stable ending, manual interruption, reduced motion, boundary hysteresis, cursor relay, no autoplay.");
