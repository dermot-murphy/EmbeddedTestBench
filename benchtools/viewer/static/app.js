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
    if (tab.dataset.page === "instruments") loadInstruments();
    if (tab.dataset.page === "rf") loadRadio();
    if (tab.dataset.page === "graphs") loadGraphs();
    if (tab.dataset.page === "ble") loadBle();
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
  const key = where.phase + ":" + where.case + ":" + step.step;
  const text = el("span", {class: "text" + (step.started ? " clickable" : ""),
                           title: step.started ? "Show the instrument traffic of this step" : ""},
                  step.text);
  if (step.started) text.addEventListener("click", () => toggleTraffic(key, step));
  const traffic = openTraffic.has(key) ? openTraffic.get(key) : null;
  return el("div", {class: "step"},
    el("span", {class: "dot " + statusClass(step.status), title: step.status}),
    text,
    el("span", {class: "time"}, step.duration_s != null ? step.duration_s.toFixed(3) + " s" : ""),
    canRestart ? el("button", {class: "again", title: "Restart from this step",
      onclick: () => control({cmd: "restart_from", case: where.case, step: step.step})}, "↻") : el("span"),
    step.error ? el("div", {class: "detail error"}, step.error) : null,
    pieces.length ? el("div", {class: "detail"}, pieces.join("   ")) : null,
    traffic);
}

// ---------------------------------------------------------------- instrument traffic
const openTraffic = new Map();      // step key -> its traffic element, while shown

function exchangeRow(source, entry) {
  const replies = entry.kind === "exchange" ? (entry.replies || []).join("\n") : "";
  const label = {event: "event: ", note: "", unasked: "unasked: "}[entry.kind];
  return el("div", {class: "exchange " + entry.kind},
    el("span", {}, time(entry.t)),
    el("span", {class: "sent"}, source ? el("span", {class: "src"}, source) : null,
       (label || "") + entry.text),
    el("span", {class: "reply"}, replies),
    el("span", {class: "ms"}, entry.ms != null ? entry.ms.toFixed(1) : ""));
}

async function toggleTraffic(key, step) {
  if (openTraffic.has(key)) { openTraffic.delete(key); renderRun(); return; }
  const t1 = step.ended || Date.now() / 1000;
  const reply = await (await fetch("/api/instruments?t0=" + step.started + "&t1=" + t1)).json();
  const rows = [];
  for (const [source, listed] of Object.entries(reply.sources)) {
    for (const entry of listed.entries) rows.push([entry.t, exchangeRow(source, entry)]);
  }
  rows.sort((a, b) => a[0] - b[0]);
  openTraffic.set(key, el("div", {class: "traffic exchanges"},
    ...(rows.length ? rows.map((row) => row[1])
                    : [el("div", {class: "exchange note"}, el("span"), el("span", {class: "sent"},
                       "No instrument traffic during this step."))])));
  renderRun();
}

let instrument = null;
async function loadInstruments() {
  const reply = await (await fetch("/api/instruments")).json();
  const panels = $("panels");
  panels.replaceChildren(...Object.entries(reply.panels).map(([source, panel]) =>
    el("div", {class: "panel"}, el("h3", {}, source + " - " +
       (panel.kind === "psu" ? "power supply" : "debug probe")),
       el("dl", {}, ...panel.rows.flatMap(([label, value]) => [el("dt", {}, label), el("dd", {}, value)])))));
  const sources = Object.keys(reply.sources).sort();
  if (!sources.includes(instrument)) instrument = sources[0] || null;
  $("instrument-tabs").replaceChildren(...sources.map((source) => el("button", {
    role: "tab", "aria-selected": String(source === instrument),
    onclick: () => { instrument = source; loadInstruments(); }},
    source + " (" + reply.sources[source].count + ")")));
  const box = $("exchanges");
  const atBottom = box.scrollTop + box.clientHeight >= box.scrollHeight - 20;
  const entries = instrument ? reply.sources[instrument].entries : [];
  box.replaceChildren(...(entries.length ? entries.map((entry) => exchangeRow(null, entry))
    : [el("div", {class: "exchange note"}, el("span"), el("span", {class: "sent"}, "No instrument traffic yet."))]));
  if (atBottom) box.scrollTop = box.scrollHeight;
}

setInterval(() => { if (!$("page-instruments").hidden) loadInstruments(); }, 1000);

// ---------------------------------------------------------------- tables, RF and BLE pages
function table(columns, rows, onclick) {
  const head = el("tr", {}, ...columns.map((c) => el("th", {}, c.label)));
  const body = rows.map((row) => {
    const tr = el("tr", onclick ? {class: "clickable"} : {},
      ...columns.map((c) => el("td", {class: c.class || ""}, format(c.value(row)))));
    if (onclick) tr.addEventListener("click", () => onclick(row));
    return tr;
  });
  return el("table", {}, el("thead", {}, head), el("tbody", {}, ...body));
}

function fill(id, columns, rows, empty, onclick) {
  $(id).replaceChildren(rows.length ? table(columns, rows, onclick)
    : el("div", {class: "note", style: "padding: 8px"}, empty));
}

function stickToBottom(id, draw) {
  const box = $(id);
  const atBottom = box.scrollTop + box.clientHeight >= box.scrollHeight - 20;
  draw();
  if (atBottom) box.scrollTop = box.scrollHeight;
}

async function loadRadio() {
  const chosen = $("rf-sensor").value;
  const reply = await (await fetch("/api/radio?sensor=" + encodeURIComponent(chosen))).json();
  const select = $("rf-sensor");
  const ids = reply.sensors.map((s) => s.sensor_id);
  if (select.dataset.ids !== ids.join(",")) {
    select.dataset.ids = ids.join(",");
    select.replaceChildren(el("option", {value: ""}, "All sensors"),
      ...ids.map((id) => el("option", {value: id}, id)));
    select.value = ids.includes(chosen) ? chosen : "";
  }
  $("rf-counts").textContent = reply.received + " received, " + reply.failed +
    " with a radio error, " + reply.sent + " sent";
  const sensors = reply.sensors.filter((s) => !chosen || s.sensor_id === chosen);
  fill("rf-sensors", [
    {label: "Sensor", value: (s) => s.sensor_id, class: "mono id"},
    {label: "Frames", value: (s) => s.frames, class: "num"},
    {label: "Last heard", value: (s) => time(s.last_t)},
    {label: "RSSI dBm", value: (s) => s.rssi_dbm, class: "num"},
    {label: "Latest by type", value: (s) => Object.entries(s.latest).map(
      ([type, f]) => type + ": " + f.summary).join("  |  ")},
  ], sensors, "No Kepler frames received yet.");
  stickToBottom("rf-frames", () => fill("rf-frames", [
    {label: "Time", value: (f) => time(f.t)},
    {label: "Sensor", value: (f) => f.sensor_id, class: "mono id"},
    {label: "Type", value: (f) => f.type || (f.error ? "error" : "?")},
    {label: "Bytes", value: (f) => f.length, class: "num"},
    {label: "RSSI dBm", value: (f) => f.rssi_dbm, class: "num"},
    {label: "Content", value: (f) => f.summary},
  ], reply.frames, "No frames.", (frame) => {
    const box = $("rf-detail");
    box.hidden = false;
    box.textContent = JSON.stringify({hex: frame.hex, decoded: frame.decoded, problem: frame.problem}, null, 2);
  }));
}
$("rf-sensor").addEventListener("change", loadRadio);

async function loadBle() {
  const reply = await (await fetch("/api/ble")).json();
  fill("ble-devices", [
    {label: "Address", value: (d) => d.addr, class: "mono id"},
    {label: "Name", value: (d) => d.name},
    {label: "Adverts", value: (d) => d.adverts, class: "num"},
    {label: "Interval ms", value: (d) => d.interval_ms, class: "num"},
    {label: "RSSI dBm", value: (d) => d.rssi, class: "num"},
    {label: "Mean RSSI", value: (d) => d.rssi_mean, class: "num"},
    {label: "Last heard", value: (d) => time(d.last_t)},
  ], reply.devices, "No BLE devices heard yet.");
  stickToBottom("ble-events", () => fill("ble-events", [
    {label: "Time", value: (e) => time(e.t)},
    {label: "Event", value: (e) => e.event},
    {label: "Details", value: (e) => Object.entries(e.fields).map(([k, v]) => k + "=" + v).join(" "),
     class: "mono"},
  ], reply.events, "No BLE events yet."));
  const rows = [];
  for (const [source, listed] of Object.entries(reply.exchanges)) {
    for (const entry of listed.entries) {
      if (entry.kind === "exchange") rows.push([entry.t, exchangeRow(source, entry)]);
    }
  }
  rows.sort((a, b) => a[0] - b[0]);
  stickToBottom("ble-exchanges", () => $("ble-exchanges").replaceChildren(...(rows.length
    ? rows.map((r) => r[1])
    : [el("div", {class: "exchange note"}, el("span"), el("span", {class: "sent"}, "No dongle commands yet."))])));
}

setInterval(() => {
  if (!$("page-rf").hidden) loadRadio();
  if (!$("page-ble").hidden) loadBle();
}, 1000);

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

// The Event log page's filters (#148): instruments, kinds of event, a sensor, a test.
const KINDS = [["rf_rx", "RF frames received"], ["rf_tx", "RF frames sent"],
               ["ble_adv", "BLE adverts"], ["reading", "Readings"], ["runner", "Runner"],
               ["control", "Control"]];
const onlyKinds = new Set();
let eventsPaused = false;
let heldBack = [];

function tagsOf(record) { return record.tags || {kinds: [], sensor: null, test: null}; }

function shown(record) {
  if (hidden.has(record.source)) return false;
  const tags = tagsOf(record);
  if (onlyKinds.size && !tags.kinds.some((kind) => onlyKinds.has(kind))) return false;
  const sensor = $("events-sensor").value;
  if (sensor && tags.sensor !== sensor &&
      !String(record.text || "").toUpperCase().includes(sensor)) return false;
  const test = $("events-test").value;
  if (test && tags.test !== test) return false;
  return true;
}

function checkbox(label, checked, onchange) {
  const input = el("input", {type: "checkbox"});
  input.checked = checked;
  input.addEventListener("change", () => onchange(input.checked));
  return el("label", {}, input, label);
}

function renderFilters() {
  const sources = [...new Set(records.map((r) => r.source))].sort();
  const box = $("filters");
  if (box.dataset.sources !== sources.join(",")) {
    box.dataset.sources = sources.join(",");
    box.replaceChildren(...sources.map((source) => checkbox(source, !hidden.has(source), (on) => {
      if (on) hidden.delete(source); else hidden.add(source);
      renderEvents(true);
    })));
  }
  const kinds = $("kinds");
  if (!kinds.childElementCount) {
    kinds.replaceChildren(...KINDS.map(([kind, label]) => checkbox(label, false, (on) => {
      if (on) onlyKinds.add(kind); else onlyKinds.delete(kind);
      renderEvents(true);
    })));
  }
  const sensors = [...new Set(records.map((r) => tagsOf(r).sensor).filter(Boolean))].sort();
  const select = $("events-sensor");
  if (select.dataset.ids !== sensors.join(",")) {
    const chosen = select.value;
    select.dataset.ids = sensors.join(",");
    select.replaceChildren(el("option", {value: ""}, "No filter"),
      ...sensors.map((id) => el("option", {value: id}, id)));
    select.value = sensors.includes(chosen) ? chosen : "";
  }
  const tests = (state && state.tests) || [];
  $("events-test-box").hidden = tests.length < 2;
  const testSelect = $("events-test");
  if (testSelect.dataset.ids !== tests.join("|")) {
    const chosen = testSelect.value;
    testSelect.dataset.ids = tests.join("|");
    testSelect.replaceChildren(el("option", {value: ""}, "All tests"),
      ...tests.map((test) => el("option", {value: test}, test)));
    testSelect.value = tests.includes(chosen) ? chosen : "";
  }
}

function renderCount() {
  const showing = $("events").childElementCount;
  $("events-count").textContent = records.length + " record(s), " + showing + " shown" +
    (eventsPaused ? "; paused, " + heldBack.length + " new held back" : "");
  $("events-pause").textContent = eventsPaused ? "Resume" : "Pause";
  $("events-pause").setAttribute("aria-pressed", String(eventsPaused));
}

function renderEvents(full, added) {
  const box = $("events");
  const atBottom = box.scrollTop + box.clientHeight >= box.scrollHeight - 20;
  if (full) {
    box.replaceChildren(...records.filter(shown).map(eventRow));
  } else {
    for (const record of added) if (shown(record)) box.append(eventRow(record));
    while (box.childElementCount > MAX_EVENTS) box.firstElementChild.remove();
  }
  if (atBottom && !eventsPaused) box.scrollTop = box.scrollHeight;
  renderFilters();
  renderCount();
}

$("events-pause").addEventListener("click", () => {
  eventsPaused = !eventsPaused;
  if (!eventsPaused && heldBack.length) {
    const released = heldBack;
    heldBack = [];
    records.push(...released);
    if (records.length > MAX_EVENTS) records = records.slice(-MAX_EVENTS);
    renderEvents(false, released);
  }
  renderCount();
});
$("events-sensor").addEventListener("change", () => renderEvents(true));
$("events-test").addEventListener("change", () => renderEvents(true));

// ---------------------------------------------------------------- live stream
let pending = [];
let scheduled = false;
function flush() {
  scheduled = false;
  renderRun();
  if (pending.length && eventsPaused) {
    // Held, not lost: the list stays still while the operator reads it.
    heldBack.push(...pending);
    pending = [];
    renderCount();
  } else if (pending.length) {
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
  source.addEventListener("reset", () => {
    records = []; pending = []; heldBack = []; $("events").replaceChildren(); renderCount();
  });
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
