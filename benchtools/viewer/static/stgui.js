// benchtools test run viewer: the Embedded Test Bench monitor's ST GUI page (#157).
// Uses el, $, post and table helpers from app.js, loaded before this file.
"use strict";

const expanded = new Set();
let stClearedAt = 0;

function stRows(rows) {
  const body = [];
  for (const row of rows) {
    const tr = el("tr", {class: "clickable" + (row.changed ? " changed" : "")},
      el("td", {class: "mono id"}, row.address), el("td", {}, row.name),
      el("td", {class: "mono"}, row.value), el("td", {class: "mono"}, row.default));
    tr.addEventListener("click", () => {
      if (expanded.has(row.address)) expanded.delete(row.address); else expanded.add(row.address);
      loadStGui();
    });
    body.push(tr);
    if (expanded.has(row.address)) {
      for (const [name, value] of row.fields) {
        body.push(el("tr", {class: "field"}, el("td", {}, name), el("td", {}, String(value)),
                     el("td"), el("td")));
      }
    }
  }
  return el("table", {}, el("thead", {}, el("tr", {}, ...["Address", "Register", "Value", "Default"]
    .map((h) => el("th", {}, h)))), el("tbody", {}, ...body));
}

async function loadStGui() {
  const reply = await (await fetch("/api/stgui")).json();
  $("st-read").textContent = reply.read ? "Read at " + time(reply.read) : "Not read yet: press Refresh";
  fill("st-setup", [
    {label: "Section", value: (r) => r[0]},
    {label: "Setting", value: (r) => r[1]},
    {label: "Value", value: (r) => r[2]},
  ], reply.setup, "The run has not read the kit's setup yet.");
  if (reply.registers.length) {
    $("st-registers").replaceChildren(stRows(reply.registers));
    $("st-registers").dataset.addresses = reply.registers.map((r) => r.address).join(",");
  } else {
    $("st-registers").replaceChildren(el("div", {class: "note", style: "padding: 8px"}, "No registers read yet."));
  }
  if ($("st-pause").checked) return;
  const frames = reply.frames.filter((f) => (f.t || 0) > stClearedAt);
  $("st-count").textContent = "Packets: " + frames.length;
  const box = $("st-frames");
  box.replaceChildren(table([
    {label: "Timestamp", value: (f) => f.time},
    {label: "Bytes", value: (f) => f.bytes, class: "num"},
    {label: "RSSI", value: (f) => (f.rssi == null ? "" : Number(f.rssi).toFixed(1)), class: "num"},
    {label: "Data", value: (f) => f.data, class: "mono"},
  ], frames));
  box.querySelectorAll("tbody tr").forEach((tr, i) => { if (frames[i].lost) tr.classList.add("lost"); });
  if ($("st-follow").checked) box.scrollTop = box.scrollHeight;
}

$("st-refresh").addEventListener("click", async () => {
  const reply = await post("/api/stgui/refresh", {});
  $("st-note").textContent = reply.ok
    ? "Asked the run to read the kit's setup at its next step."
    : "Refused: " + reply.error;
});
$("st-expand").addEventListener("click", () => {
  for (const address of ($("st-registers").dataset.addresses || "").split(",")) {
    if (address) expanded.add(address);
  }
  loadStGui();
});
$("st-collapse").addEventListener("click", () => { expanded.clear(); loadStGui(); });
$("st-export").addEventListener("click", () => { location.href = "/api/stgui/regs"; });
$("st-clear").addEventListener("click", () => { stClearedAt = Date.now() / 1000; loadStGui(); });
