// Kepler's viewer panel (#152 .. #155, #303): rf_monitor's Latest Data, Config,
// Identification, Environment, Short Interval, Ticks, TWF, Diagnostics and Sync,
// each a tab on the viewer's RF page. The page adds the tabs the panel lists in
// /api/plugins; this script builds what each shows, registers it with
// registerRfView, and asks /api/panel?name=kepler&tab=... for its data.
// Uses el, $, time, fill, post, lineChart, hoverTime and registerRfView from
// the viewer's own scripts, loaded before this file.
"use strict";

const keplerBase = new URL(".", document.currentScript.src).href;
let keplerTab = "latest";
let latestPaused = false;
let latestHeld = null;

(function keplerBuild() {
  const style = document.createElement("link");
  style.rel = "stylesheet";
  style.href = keplerBase + "kepler.css";
  document.head.append(style);
  const box = document.createElement("div");
  box.id = "kepler-views";
  box.innerHTML = `
    <div id="rf-latest-view" hidden>
      <div class="toolbar"><button id="rf-latest-pause" type="button">Pause</button>
        <span class="note">Newest first; the last 50 frames of the sensor chosen above.</span></div>
      <div id="rf-latest" class="latest"></div>
    </div>
    <div id="rf-config-view" hidden>
      <div class="note" id="rf-config-sensor"></div>
      <div id="rf-config-groups" class="panels"></div>
      <div id="rf-config" class="table config"></div>
    </div>
    <div id="rf-identification-view" hidden>
      <div id="rf-identification" class="panel"></div>
    </div>
    <div id="rf-twf-view" hidden>
      <div class="toolbar">
        <span>Buffer
          <label><input type="radio" name="twf-buffer" value="A" checked> TWFA</label>
          <label><input type="radio" name="twf-buffer" value="B"> TWFB</label></span>
        <span>Axis
          <label><input type="radio" name="twf-axis" value="X" checked> X</label>
          <label><input type="radio" name="twf-axis" value="Y"> Y</label>
          <label><input type="radio" name="twf-axis" value="Z"> Z</label></span>
        <button type="button" id="twf-zoom-in">Zoom in</button>
        <button type="button" id="twf-zoom-out">Zoom out</button>
        <button type="button" id="twf-zoom-reset">Reset</button>
      </div>
      <div id="twf-status" class="note"></div>
      <div id="twf-diagnostics" class="note"></div>
      <div id="twf-graphs" class="graphs"></div>
    </div>
    <div id="rf-diagnostics-view" hidden>
      <div class="toolbar">
        <span id="diag-overall" class="note"></span>
        <button type="button" id="diag-reset">Reset</button>
        <button type="button" id="diag-hold" aria-pressed="false">Auto</button>
      </div>
      <h2 class="section">Period statistics</h2>
      <div id="diag-table" class="table"></div>
      <h2 class="section" id="diag-detail-title">Last 10 frames</h2>
      <div id="diag-detail" class="table"></div>
    </div>
    <div id="rf-sync-view" hidden>
      <div class="note">Every sensor's sync with the gateway, from CMD and RESPONSE frames; not filtered to a sensor.</div>
      <div id="sync-table" class="table"></div>
    </div>
    <div id="rf-graphs-view" hidden>
      <div class="toolbar">
        <span id="rf-axis-box" hidden>Axis
          <label><input type="radio" name="rf-axis" value="X"> X</label>
          <label><input type="radio" name="rf-axis" value="Y"> Y</label>
          <label><input type="radio" name="rf-axis" value="Z" checked> Z</label>
        </span>
        <button type="button" id="rf-zoom-in">Zoom in</button>
        <button type="button" id="rf-zoom-out">Zoom out</button>
        <button type="button" id="rf-zoom-reset">Reset</button>
        <span class="note">Hover a chart for the values at a time; zoom centres on the last point hovered.</span>
      </div>
      <div id="rf-graphs" class="graphs"></div>
    </div>`;
  $("page-rf").append(...box.children);
})();

function keplerPanel(tab, extra) {
  return fetch("/api/panel?name=kepler&tab=" + tab + "&sensor=" +
               encodeURIComponent($("rf-sensor").value) + (extra || "")).then((r) => r.json());
}

function rawBytes(hex, roles) {
  const out = el("div", {class: "raw"});
  for (let i = 0; i < hex.length; i += 2) {
    out.append(el("span", {class: "byte r-" + (roles[i / 2] || "payload")}, hex.slice(i, i + 2)));
  }
  return out;
}

function rows(pairs) {
  return el("table", {class: "kv"}, el("tbody", {}, ...pairs.map(([name, value]) =>
    el("tr", {}, el("th", {}, name), el("td", {}, value)))));
}

function latestBlock(frame) {
  return el("article", {class: "frame t-" + (frame.type || "UNKNOWN")},
    el("header", {}, time(frame.t) + "   Sensor 0x" + (frame.sensor_id || "?") + "   " +
       (frame.type || "undecoded") + (frame.rssi_dbm != null ? "   " + frame.rssi_dbm + " dBm" : "")),
    el("div", {class: "note"}, "Raw (" + frame.hex.length / 2 + " bytes)"),
    rawBytes(frame.hex, frame.roles),
    frame.problem ? el("div", {class: "detail error"}, frame.problem) : null,
    frame.header.length ? el("h4", {}, "Packet header") : null,
    frame.header.length ? rows(frame.header) : null,
    frame.payload.length ? el("h4", {}, "Payload") : null,
    frame.payload.length ? rows(frame.payload) : null);
}

function renderLatest(reply) {
  const box = $("rf-latest");
  box.replaceChildren(...(reply.latest.length ? reply.latest.slice().reverse().map(latestBlock)
    : [el("div", {class: "note"}, "No frames yet.")]));
}

function renderConfig(reply) {
  $("rf-config-sensor").textContent = reply.sensor ? "Sensor 0x" + reply.sensor : "No CONFIG frames yet";
  const columns = [
    {label: "Block", value: (r) => r.block, class: "num"},
    {label: "Param", value: (r) => r.parameter, class: "num"},
    {label: "Name", value: (r) => r.name},
    {label: "Value", value: (r) => r.shown == null ? "-" : r.shown},
    {label: "Units", value: (r) => r.unit},
    {label: "Last update", value: (r) => (r.t ? time(r.t) : "")},
  ];
  fill("rf-config", columns, reply.config, "No CONFIG frames yet.");
  for (const [index, row] of reply.config.entries()) {
    const tr = $("rf-config").querySelectorAll("tbody tr")[index];
    if (tr && row.disabled) tr.classList.add("disabled");
    if (tr && row.shown == null) tr.classList.add("unknown");
  }
  $("rf-config-groups").replaceChildren(...reply.groups.map((group) =>
    el("div", {class: "panel"}, el("h3", {}, group.title),
       rows(group.rows.map((r) => [r.name, r.shown == null ? "-" : r.shown + (r.unit ? " " + r.unit : "")])))));
}

function renderIdentification(reply) {
  const id = reply.identification;
  if (!id) { $("rf-identification").replaceChildren(el("div", {class: "note"}, "No VERSION frame received yet.")); return; }
  $("rf-identification").replaceChildren(rows([
    ["Received", time(id.t) + (id.rssi_dbm != null ? "  (" + id.rssi_dbm + " dBm)" : "")],
    ["Sensor ID / product", "0x" + id.sensor_id + " / " + id.product],
    ["FW version", id.version], ["SHA", id.sha],
    ["Capabilities", "RF " + id.rf_capability + ", HW " + id.hw_capability + ", FW " + id.fw_capability +
     ", type " + id.type_capability + ", PCB " + id.pcb],
    ["Temperature / battery", id.temperature_c + " °C / " + id.battery_loaded_mv + " mV loaded"],
    ["Ticks", String(id.ticks)],
    ["Reset reason", (id.reset_reasons || []).join(", ") + "  (0x" + Number(id.reset_reason).toString(16).padStart(8, "0") + ")"],
  ]));
}

// rf_monitor's Environment, Short Interval and Ticks (#153), on the shared chart.
let zoomSpan = null;
let lastSpan = null;

async function loadSensorGraphs() {
  const axis = document.querySelector("input[name=rf-axis]:checked").value;
  const reply = await keplerPanel(keplerTab, "&axis=" + axis);
  const charts = keplerTab === "environment" ? reply.environment
    : keplerTab === "short" ? reply.short_interval : reply.ticks;
  const times = charts.flatMap((c) => c.series.flatMap((s) => s.points.map((p) => p[0])));
  lastSpan = times.length ? [Math.min(...times), Math.max(...times)] : [0, 1];
  const span = zoomSpan || lastSpan;
  const box = $("rf-graphs");
  box.replaceChildren(...(reply.sensor ? charts.map((c) => lineChart(c, span, [], box))
    : [el("div", {class: "note"}, "No ALIVE, TWF or VERSION frames yet.")]));
}

function zoom(factor) {
  const span = zoomSpan || lastSpan;
  if (!span) return;
  const centre = hoverTime != null && hoverTime >= span[0] && hoverTime <= span[1]
    ? hoverTime : span[1];
  const half = Math.max((span[1] - span[0]) * factor / 2, 0.5);
  zoomSpan = [centre - half, centre + half];
  loadSensorGraphs();
}
$("rf-zoom-in").addEventListener("click", () => zoom(0.5));
$("rf-zoom-out").addEventListener("click", () => zoom(2));
$("rf-zoom-reset").addEventListener("click", () => { zoomSpan = null; loadSensorGraphs(); });
for (const radio of document.querySelectorAll("input[name=rf-axis]")) {
  radio.addEventListener("change", loadSensorGraphs);
}

// rf_monitor's TWF screen (#154): the waveform and its spectrum.
async function loadTwf() {
  const buffer = document.querySelector("input[name=twf-buffer]:checked").value;
  const axis = document.querySelector("input[name=twf-axis]:checked").value;
  const reply = await keplerPanel("twf", "&buffer=" + buffer + "&axis=" + axis);
  const box = $("twf-graphs");
  const c = reply.capture;
  if (!c) {
    $("twf-status").textContent = "No TWF frames for this sensor, buffer and axis yet.";
    $("twf-diagnostics").textContent = "";
    box.replaceChildren();
    return;
  }
  const name = "TWF" + reply.buffer + "  " + reply.axis + "-axis";
  $("twf-status").textContent = c.complete
    ? name + " complete   ODR " + c.odr_hz + " Hz   ±" + c.full_scale_mg + " mg   " + c.samples +
      " samples   " + c.duration_ms.toFixed(1) + " ms   permutation " + c.method
    : "Receiving " + name + "   ODR " + c.odr_hz + " Hz   packets " + c.packets + " / " +
      c.total_packets + " (" + c.percent + "%)";
  $("twf-diagnostics").textContent = (c.complete ? "Complete" : "Partial") + "  |  received " +
    c.packets + " / " + c.total_packets + " (" + c.percent + "%)  |  missed " + c.missed +
    "  |  signal " + c.signal;
  const wave = {id: "twf", title: name + " waveform (mg)", unit: "mg", xunit: "ms",
                series: [{key: "twf", label: reply.sensor, points: reply.waveform}]};
  const fft = {id: "fft", title: "Spectrum (mg)  ·  resolution " + c.resolution_hz + " Hz/bin",
               unit: "mg", xunit: "Hz", zero: true,
               series: [{key: "fft", label: reply.sensor, points: reply.spectrum}]};
  const span = (points) => points.length ? [points[0][0], points[points.length - 1][0]] : [0, 1];
  twfFull = span(reply.waveform);
  box.replaceChildren(lineChart(wave, twfZoom || twfFull, [], box),
                      lineChart(fft, span(reply.spectrum), [], box));
}

// Zoom on the waveform: halve or double the span about the time last hovered,
// kept within the capture, never narrower than a millisecond - as rf_monitor.
let twfZoom = null;
let twfFull = null;
function zoomTwf(factor) {
  const span = twfZoom || twfFull;
  if (!span) return;
  const centre = hoverTime != null && hoverTime >= span[0] && hoverTime <= span[1]
    ? hoverTime : (span[0] + span[1]) / 2;
  const half = Math.max((span[1] - span[0]) * factor / 2, 0.5);
  twfZoom = [Math.max(twfFull[0], centre - half), Math.min(twfFull[1], centre + half)];
  loadTwf();
}
$("twf-zoom-in").addEventListener("click", () => zoomTwf(0.5));
$("twf-zoom-out").addEventListener("click", () => zoomTwf(2));
$("twf-zoom-reset").addEventListener("click", () => { twfZoom = null; loadTwf(); });
for (const radio of document.querySelectorAll("input[name=twf-buffer], input[name=twf-axis]")) {
  radio.addEventListener("change", loadTwf);
}

// rf_monitor's Diagnostics and Sync (#155).
let diagType = null;
let diagHold = false;

function seconds(value) {
  return value == null ? "-" : Number(value).toFixed(3);
}

async function loadDiagnostics() {
  const reply = await keplerPanel("diagnostics");
  const d = reply.diagnostics;
  const o = d.overall;
  $("diag-overall").textContent = (d.sensor ? "Sensor 0x" + d.sensor + ".  " : "") +
    "Overall success " + (o.success_pct == null ? "-" : o.success_pct + "%") +
    "  (" + o.received + " / " + o.expected + " copies, dropped " + o.dropped + ")";
  if (keplerTab === "diagnostics") {
    if (!diagHold || !d.types.some((t) => t.type === diagType)) {
      const latest = d.types.slice().sort((a, b) => (b.last_seen || 0) - (a.last_seen || 0))[0];
      if (!diagHold) diagType = latest ? latest.type : null;
    }
    fill("diag-table", [
      {label: "Frame type", value: (t) => t.type},
      {label: "Frames", value: (t) => t.frames, class: "num"},
      {label: "Packets", value: (t) => t.packets, class: "num"},
      {label: "Dropped", value: (t) => (t.expected ? t.dropped : "-"), class: "num"},
      {label: "Success %", value: (t) => (t.success_pct == null ? "-" : t.success_pct), class: "num"},
      {label: "Mean s", value: (t) => seconds(t.mean_s), class: "num"},
      {label: "Std dev s", value: (t) => seconds(t.std_s), class: "num"},
      {label: "Min s", value: (t) => seconds(t.min_s), class: "num"},
      {label: "Max s", value: (t) => seconds(t.max_s), class: "num"},
      {label: "Last seen", value: (t) => time(t.last_seen)},
    ], d.types, "No frames from this sensor yet.", (row) => {
      diagType = row.type; diagHold = true; updateHold(); loadDiagnostics();
    });
    const rowsShown = $("diag-table").querySelectorAll("tbody tr");
    d.types.forEach((t, i) => {
      if (rowsShown[i] && t.type === diagType) rowsShown[i].classList.add("chosen");
      if (rowsShown[i] && t.min_between) {
        rowsShown[i].title = "Shortest period between " + time(t.min_between[0]) + " and " +
          time(t.min_between[1]) + "; longest between " + time(t.max_between[0]) + " and " +
          time(t.max_between[1]);
      }
    });
    const chosen = d.types.find((t) => t.type === diagType);
    $("diag-detail-title").textContent = "Last 10 frames" + (diagType ? " - " + diagType : "") +
      (diagHold ? " [hold]" : "");
    fill("diag-detail", [
      {label: "Time", value: (r) => time(r.t)},
      {label: "Delta s", value: (r) => seconds(r.delta_s), class: "num"},
    ], chosen ? chosen.recent : [], "None.");
  } else {
    const rows = reply.sync.sensors;
    fill("sync-table", [
      {label: "Sensor ID", value: (r) => "0x" + r.sensor_id, class: "mono id"},
      {label: "Slot", value: (r) => (r.slot == null ? "-" : r.slot), class: "num"},
      {label: "Phase", value: (r) => r.phase},
      {label: "Retry", value: (r) => (r.retry == null ? "-" : r.retry), class: "num"},
      {label: "LORES remaining", value: (r) => r.lores_remaining_s == null ? "-"
        : r.lores_remaining_s <= 0 ? "0:00 (expired)"
        : Math.floor(r.lores_remaining_s / 60) + ":" + String(Math.floor(r.lores_remaining_s % 60)).padStart(2, "0")},
      {label: "HIRES remaining", value: (r) => r.hires_remaining_s == null ? "-"
        : r.hires_remaining_s <= 0 ? "0.000 s (fired)" : r.hires_remaining_s.toFixed(3) + " s"},
      {label: "Last seen", value: (r) => time(r.last_seen)},
    ], rows, "No CMD or RESPONSE frames yet.");
    const shown = $("sync-table").querySelectorAll("tbody tr");
    rows.forEach((r, i) => { if (shown[i] && r.state) shown[i].classList.add("st-" + r.state); });
  }
}

function updateHold() {
  $("diag-hold").textContent = diagHold ? "Hold" : "Auto";
  $("diag-hold").setAttribute("aria-pressed", String(diagHold));
}
$("diag-hold").addEventListener("click", () => { diagHold = !diagHold; updateHold(); loadDiagnostics(); });
$("diag-reset").addEventListener("click", async () => {
  await post("/api/panel", {name: "kepler", action: "reset", sensor: $("rf-sensor").value});
  loadDiagnostics();
});

async function loadScreens() {
  const reply = await keplerPanel(keplerTab);
  if (keplerTab === "latest") {
    if (latestPaused) { latestHeld = reply; $("rf-latest-pause").textContent = "Resume"; return; }
    renderLatest(reply);
  } else if (keplerTab === "config") {
    renderConfig(reply);
  } else {
    renderIdentification(reply);
  }
}

// Each tab: the element it shows and how it loads; the tabs that share an
// element (the graphs; Diagnostics and Sync share a loader) say which they are.
for (const [tab, element, load] of [
  ["latest", "rf-latest-view", loadScreens], ["config", "rf-config-view", loadScreens],
  ["identification", "rf-identification-view", loadScreens],
  ["environment", "rf-graphs-view", loadSensorGraphs], ["short", "rf-graphs-view", loadSensorGraphs],
  ["ticks", "rf-graphs-view", loadSensorGraphs], ["twf", "rf-twf-view", loadTwf],
  ["diagnostics", "rf-diagnostics-view", loadDiagnostics], ["sync", "rf-sync-view", loadDiagnostics],
]) {
  registerRfView("kepler." + tab, {element: $(element), load: (entered) => {
    keplerTab = tab;
    if (entered) {
      zoomSpan = null;
      $("rf-axis-box").hidden = tab !== "short";
    }
    return load();
  }});
}

$("rf-latest-pause").addEventListener("click", () => {
  latestPaused = !latestPaused;
  $("rf-latest-pause").textContent = latestPaused ? "Resume" : "Pause";
  if (!latestPaused && latestHeld) { renderLatest(latestHeld); latestHeld = null; }
});
