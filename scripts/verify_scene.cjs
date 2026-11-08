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
let nextId = 0, sourceAssignments = 0;
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
  matchMedia: () => ({ matches: true, addEventListener() {} }),
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
function flush() {
  let count = 0;
  while (frames.size) {
    assert.ok(++count < 30, "Scene must settle without autoplay");
    const [id, callback] = frames.entries().next().value;
    frames.delete(id); callback(count * 16);
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
assert.equal(api.progress, progress, "Cursor movement must never advance the scene");
receive({ type: "pointerleave" });
assert.equal(node("cursor-ghost").style.opacity, "0");
receive({ type: "navigate", chapter: 0 });
assert.equal(shell.hidden, true);
assert.equal(sent.at(-1).data.chapter, 0, "Returning to the intro dismisses any pending child approval");
assert.equal(node("photo-background").style.opacity, "1");
api.goToChapter(1); flush();
assert.equal(sourceAssignments, 1, "Rewinding to intro must not discard the loaded workflow");
assert.equal(sent.at(-1).data.chapter, 1);
assert.equal(api.isAnimating, false);
assert.ok(html.includes('title="GhostPatch real backend workflow"'));
assert.ok(html.includes('id="workspace-retry"'));
console.log("PASS: six chapters, lazy persistent iframe, trusted-origin/source handshake, invalid-message rejection, Next/Previous, rewind, cursor relay, no autoplay.");
