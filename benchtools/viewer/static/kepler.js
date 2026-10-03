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

async function loadKepler() {
  if (rfView === "frames") return;
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
