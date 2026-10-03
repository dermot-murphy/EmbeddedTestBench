// benchtools test run viewer (#137). Plain JavaScript, nothing from a CDN.
"use strict";

const $ = (id) => document.getElementById(id);
let state = null;
let records = [];
const hidden = new Set();
const MAX_EVENTS = 3000;

function el(tag, attrs, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    if (key === "class") node.className = value;
    else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value);
  }
  for (const child of children) {
    if (child !== null && child !== undefined) node.append(child);
  }
  return node;
}

function statusClass(status) {
  return "s-" + String(status || "PENDING").split(" ")[0];
}

async function post(path, body) {
  const response = await fetch(path, {
    method: "POST",
    headers: {"Content-Type": "application/json", "X-Benchtools": "1"},
    body: JSON.stringify(body),
  });
  return response.json();
}

// ---------------------------------------------------------------- tabs
for (const tab of document.querySelectorAll("#tabs button")) {
  tab.addEventListener("click", () => {
    for (const other of document.querySelectorAll("#tabs button")) {
      other.setAttribute("aria-selected", String(other === tab));
      $("page-" + other.dataset.page).hidden = other !== tab;
    }
    if (tab.dataset.page === "start") loadCatalogue();
  });
}

// ---------------------------------------------------------------- run page
function format(value) {
  if (value === null || value === undefined) return "";
  if (typeof value === "number") return String(Math.round(value * 1e6) / 1e6);
  if (typeof value === "string") return value;
  return JSON.stringify(value);
}

function stepRow(step, where) {
  const pieces = [];
  if (step.save && step.status === "PASS") pieces.push(step.save + " = " + format(step.result));
  else if (step.result !== null && step.result !== undefined) pieces.push("→ " + format(step.result));
  for (const m of step.measurements || []) {
    pieces.push(m.name + " " + format(m.value) + (m.unit ? " " + m.unit : "") +
                " [" + m.limit + "] " + m.status + (m.reason ? " - " + m.reason : ""));
  }
  const canRestart = where.phase === "test" && state && state.status === "RUNNING" &&
                     state.position.phase !== "teardown";
  return el("div", {class: "step"},
    el("span", {class: "dot " + statusClass(step.status), title: step.status}),
    el("span", {class: "text"}, step.text),
    el("span", {class: "time"}, step.duration_s != null ? step.duration_s.toFixed(3) + " s" : ""),
    canRestart ? el("button", {class: "again", title: "Restart from this step",
      onclick: () => control({cmd: "restart_from", case: where.case, step: step.step})}, "↻") : el("span"),
    step.error ? el("div", {class: "detail error"}, step.error) : null,
    pieces.length ? el("div", {class: "detail"}, pieces.join("   ")) : null);
}

function group(title, extra, status, reason, steps, where) {
  return el("div", {class: "group"},
    el("header", {},
      el("span", {class: "dot " + statusClass(status), title: status}),
      el("span", {class: "name"}, title),
      extra ? el("span", {class: "req"}, extra) : null,
      el("span", {class: statusClass(status)}, status),
      reason ? el("span", {class: "reason"}, reason) : null),
    ...steps.map((step) => stepRow(step, where)));
}

function renderRun() {
  const tree = $("tree");
  tree.replaceChildren();
  if (!state || state.status === "WAITING") {
    $("suite").textContent = "No run yet";
    $("meta").textContent = state && state.event_log
      ? "Following " + state.event_log : "Start a run, or attach to one.";
    $("verdict").textContent = "WAITING";
    $("verdict").className = "badge s-WAITING";
    updateControls();
    return;
  }
  $("suite").textContent = state.suite;
  const plan = state.plan || {};
  const meta = [];
  if (plan.bench) meta.push("bench " + plan.bench + (plan.simulated ? " (simulated)" : ""));
  if (plan.selection && plan.selection.length) meta.push("selected: " + plan.selection.join(", "));
  if (state.event_log) meta.push(state.event_log);
  $("meta").textContent = meta.join(" · ");
  const shown = state.paused && state.status === "RUNNING" ? "PAUSED" : state.status;
  $("verdict").textContent = shown;
  $("verdict").className = "badge " + (shown === "PAUSED" ? "paused" : statusClass(shown));

  if (state.setup.length) {
    tree.append(group("Setup", null, phaseStatus(state.setup), "", state.setup, {phase: "setup"}));
  }
  for (const c of state.cases) {
    tree.append(group(c.name, c.requirement, c.status, c.error || c.skip_reason, c.steps,
                      {phase: "test", case: c.case}));
  }
  if (state.teardown.length) {
    tree.append(group("Teardown", null, phaseStatus(state.teardown), "", state.teardown,
                      {phase: "teardown"}));
  }
  if (state.verdict && state.verdict.setup_error) {
    tree.prepend(el("div", {class: "detail error"}, "Setup: " + state.verdict.setup_error));
  }
  updateControls();
}

function phaseStatus(steps) {
  if (steps.some((s) => s.status === "RUNNING")) return "RUNNING";
  if (steps.every((s) => s.status === "PENDING")) return "PENDING";
  const order = ["PASS", "SKIP", "FAIL", "ERROR"];
  return steps.map((s) => s.status).filter((s) => order.includes(s))
    .reduce((a, b) => (order.indexOf(b) > order.indexOf(a) ? b : a), "PASS");
}

function updateControls() {
  const running = state && state.status === "RUNNING";
  const controllable = running && state.control_port;
  const teardown = running && state.position.phase === "teardown";
  for (const button of document.querySelectorAll("#controls button")) {
    const cmd = button.dataset.cmd;
    let enabled = controllable && !teardown;
    if (cmd === "pause") enabled = enabled && !state.paused;
    if (cmd === "resume") enabled = enabled && state.paused;
    if (cmd === "restart_test") enabled = enabled && state.position.phase === "test" &&
                                          state.position.case !== null;
    button.disabled = !enabled;
  }
  if (running && !state.control_port) {
    $("control-note").textContent = "This run has no control channel.";
  } else if (state && state.last_control && !state.last_control.accepted) {
    $("control-note").textContent = "Refused: " + state.last_control.reason;
  } else if (!$("control-note").dataset.sticky) {
    $("control-note").textContent = "";
  }
}

async function control(body) {
  if (body.cmd === "abort" && !confirm("Abort the run? Teardown will still run.")) return;
  const reply = await post("/api/control", body);
  const note = $("control-note");
  note.textContent = reply.ok ? body.cmd.replace("_", " ") + " accepted" : "Refused: " + reply.error;
}

for (const button of document.querySelectorAll("#controls button")) {
  button.addEventListener("click", () => control({cmd: button.dataset.cmd}));
}

// ---------------------------------------------------------------- event log page
function time(t) {
  if (!t) return "";
  const d = new Date(t * 1000);
  return d.toLocaleTimeString([], {hour12: false}) + "." + String(d.getMilliseconds()).padStart(3, "0");
}

function eventRow(record) {
  return el("div", {class: "event", "data-source": record.source},
    el("span", {}, time(record.t)),
    el("span", {class: "src"}, record.source),
    el("span", {class: "txt"}, record.text));
}

function renderFilters() {
  const sources = [...new Set(records.map((r) => r.source))].sort();
  const box = $("filters");
  if (box.dataset.sources === sources.join(",")) return;
  box.dataset.sources = sources.join(",");
  box.replaceChildren(...sources.map((source) => {
    const input = el("input", {type: "checkbox"});
    input.checked = !hidden.has(source);
    input.addEventListener("change", () => {
      if (input.checked) hidden.delete(source); else hidden.add(source);
      renderEvents(true);
    });
    return el("label", {}, input, source);
  }));
}

function renderEvents(full, added) {
  const box = $("events");
  const atBottom = box.scrollTop + box.clientHeight >= box.scrollHeight - 20;
  if (full) {
    box.replaceChildren(...records.filter((r) => !hidden.has(r.source)).map(eventRow));
  } else {
    for (const record of added) if (!hidden.has(record.source)) box.append(eventRow(record));
    while (box.childElementCount > MAX_EVENTS) box.firstElementChild.remove();
  }
  if (atBottom) box.scrollTop = box.scrollHeight;
  renderFilters();
}

// ---------------------------------------------------------------- live stream
let pending = [];
let scheduled = false;
function flush() {
  scheduled = false;
  renderRun();
  if (pending.length) {
    records.push(...pending);
    if (records.length > MAX_EVENTS) records = records.slice(-MAX_EVENTS);
    renderEvents(false, pending);
    pending = [];
  }
}
function schedule() {
  if (!scheduled) { scheduled = true; requestAnimationFrame(flush); }
}

function connect() {
  const source = new EventSource("/api/events");
  source.addEventListener("open", () => { $("link").textContent = "live"; $("link").className = "link up"; });
  source.addEventListener("error", () => { $("link").textContent = "reconnecting"; $("link").className = "link down"; });
  source.addEventListener("reset", () => { records = []; pending = []; $("events").replaceChildren(); });
  source.addEventListener("record", (event) => { pending.push(JSON.parse(event.data)); schedule(); });
  source.addEventListener("state", (event) => { state = JSON.parse(event.data); schedule(); });
}

// ---------------------------------------------------------------- start / attach
let catalogue = null;
async function loadCatalogue() {
  catalogue = await (await fetch("/api/catalogue")).json();
  const spec = $("spec");
  const current = spec.value;
  spec.replaceChildren(...catalogue.specs.map((entry) =>
    el("option", {value: entry.path}, (entry.name || entry.path) + (entry.error ? " (will not load)" : ""))));
  if (current) spec.value = current;
  $("bench").replaceChildren(el("option", {value: ""}, "Simulated (no hardware)"),
    ...catalogue.benches.map((path) => el("option", {value: path}, path)));
  showSpec();
}

function showSpec() {
  const entry = catalogue && catalogue.specs.find((item) => item.path === $("spec").value);
  const tests = $("tests");
  tests.replaceChildren(el("legend", {}, "Test cases to run"));
  const warning = $("spec-warning");
  warning.hidden = !(entry && entry.warning);
  warning.textContent = entry && entry.warning ? "Safety warning:\n" + entry.warning : "";
  if (!entry) return;
  if (entry.error) { tests.append(el("div", {class: "detail error"}, entry.error)); return; }
  for (const test of entry.tests) {
    const box = el("input", {type: "checkbox", value: test.name});
    box.checked = !test.skip;
    tests.append(el("label", {}, box, test.name + (test.requirement ? "  (" + test.requirement + ")" : "")));
  }
}
$("spec").addEventListener("change", showSpec);

$("start-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const boxes = [...document.querySelectorAll("#tests input")];
  const chosen = boxes.filter((b) => b.checked).map((b) => b.value);
  const bench = $("bench").value;
  const reply = await post("/api/start", {
    spec: $("spec").value,
    simulate: !bench,
    bench: bench || null,
    tests: chosen.length === boxes.length ? [] : chosen,
    acknowledge: $("acknowledge").checked,
  });
  $("start-note").textContent = reply.ok ? "Started; writing " + reply.event_log : "Refused: " + reply.error;
  if (reply.ok) document.querySelector('#tabs button[data-page="run"]').click();
});

$("attach-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const port = $("attach-port").value.trim();
  const reply = await post("/api/attach", {
    event_log: $("attach-log").value.trim(),
    control_port: port ? Number(port) : null,
  });
  $("attach-note").textContent = reply.ok ? "Following " + reply.event_log : "Refused: " + reply.error;
  if (reply.ok) document.querySelector('#tabs button[data-page="run"]').click();
});

renderRun();
connect();
