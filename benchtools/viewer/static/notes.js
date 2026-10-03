// benchtools test run viewer: notes and the report export (#156).
// Uses $ and post from app.js, loaded before this file.
"use strict";

let notesLoadedFor = null;

async function loadNotes() {
  const log = state && state.event_log;
  if (log === notesLoadedFor) return;
  notesLoadedFor = log;
  const notes = await (await fetch("/api/notes")).json();
  $("notes-fault").value = notes.fault;
  $("notes-findings").value = notes.findings;
  $("notes-note").textContent = log ? (notes.updated ? "Saved " + notes.updated : "Not saved yet")
    : "Start or attach to a run: notes are saved beside its event log.";
}

async function saveNotes() {
  const reply = await post("/api/notes", {fault: $("notes-fault").value,
                                          findings: $("notes-findings").value});
  $("notes-note").textContent = reply.ok ? "Saved " + reply.updated : "Not saved: " + reply.error;
}

function reportAddress(download) {
  const sensor = $("rf-sensor") ? $("rf-sensor").value : "";
  return "/api/report?sensor=" + encodeURIComponent(sensor) + (download ? "&download=1" : "");
}

$("notes-save").addEventListener("click", saveNotes);
for (const box of [$("notes-fault"), $("notes-findings")]) box.addEventListener("change", saveNotes);
$("report-download").addEventListener("click", async () => {
  await saveNotes();
  location.href = reportAddress(true);
});
$("report-print").addEventListener("click", async () => {
  await saveNotes();
  const page = window.open(reportAddress(false), "_blank");
  if (page) page.addEventListener("load", () => page.print());
});
for (const tab of document.querySelectorAll("#tabs button")) {
  tab.addEventListener("click", () => { if (tab.dataset.page === "notes") { notesLoadedFor = undefined; loadNotes(); } });
}
setInterval(() => { if (!$("page-notes").hidden) loadNotes(); }, 2000);
