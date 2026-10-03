// benchtools test run viewer: rf_monitor's Latest Data, Config and Identification (#152).
// Uses el, $, time, fill and format from app.js, loaded before this file.
"use strict";

let rfView = "frames";
let latestPaused = false;
let latestHeld = null;

for (const button of document.querySelectorAll("#rf-views button")) {
  button.addEventListener("click", () => {
    rfView = button.dataset.view;
    for (const other of document.querySelectorAll("#rf-views button")) {
      other.setAttribute("aria-selected", String(other === button));
    }
    for (const view of ["frames", "latest", "config", "identification"]) {
      $("rf-" + view + "-view").hidden = view !== rfView;
    }
    $("rf-twf-view").hidden = rfView !== "twf";
    $("rf-diagnostics-view").hidden = rfView !== "diagnostics";
    $("rf-sync-view").hidden = rfView !== "sync";
    const graphs = ["environment", "short", "ticks"].includes(rfView);
    $("rf-graphs-view").hidden = !graphs;
    $("rf-axis-box").hidden = rfView !== "short";
    zoomSpan = null;
    loadKepler();
  });
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
  const reply = await (await fetch("/api/sensor?sensor=" + encodeURIComponent($("rf-sensor").value) +
                                   "&axis=" + axis)).json();
  const charts = rfView === "environment" ? reply.environment
    : rfView === "short" ? reply.short_interval : reply.ticks;
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
  const reply = await (await fetch("/api/twf?sensor=" + encodeURIComponent($("rf-sensor").value) +
                                   "&buffer=" + buffer + "&axis=" + axis)).json();
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
  const reply = await (await fetch("/api/diagnostics?sensor=" +
                                   encodeURIComponent($("rf-sensor").value))).json();
  const d = reply.diagnostics;
  const o = d.overall;
  $("diag-overall").textContent = (d.sensor ? "Sensor 0x" + d.sensor + ".  " : "") +
    "Overall success " + (o.success_pct == null ? "-" : o.success_pct + "%") +
    "  (" + o.received + " / " + o.expected + " copies, dropped " + o.dropped + ")";
  if (rfView === "diagnostics") {
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
  await post("/api/diagnostics/reset", {sensor: $("rf-sensor").value});
  loadDiagnostics();
});

async function loadKepler() {
  if (rfView === "frames") return;
  if (rfView === "diagnostics" || rfView === "sync") { loadDiagnostics(); return; }
  if (rfView === "twf") { loadTwf(); return; }
  if (["environment", "short", "ticks"].includes(rfView)) { loadSensorGraphs(); return; }
  const sensor = $("rf-sensor").value;
  const reply = await (await fetch("/api/kepler?sensor=" + encodeURIComponent(sensor))).json();
  if (rfView === "latest") {
    if (latestPaused) { latestHeld = reply; $("rf-latest-pause").textContent = "Resume"; return; }
    renderLatest(reply);
  } else if (rfView === "config") {
    renderConfig(reply);
  } else {
    renderIdentification(reply);
  }
}

$("rf-latest-pause").addEventListener("click", () => {
  latestPaused = !latestPaused;
  $("rf-latest-pause").textContent = latestPaused ? "Resume" : "Pause";
  if (!latestPaused && latestHeld) { renderLatest(latestHeld); latestHeld = null; }
});
$("rf-sensor").addEventListener("change", loadKepler);
setInterval(() => { if (!$("page-rf").hidden) loadKepler(); }, 1000);
