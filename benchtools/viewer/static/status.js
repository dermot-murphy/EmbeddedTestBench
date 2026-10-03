// benchtools test run viewer: the status bar on every page (#149).
// Uses el, $ and time from app.js, loaded before this file.
"use strict";

function duration(seconds) {
  if (seconds == null) return "";
  const s = Math.max(0, Math.round(seconds));
  if (s < 60) return s + " s";
  const m = Math.floor(s / 60);
  if (m < 60) return m + " min " + String(s % 60).padStart(2, "0") + " s";
  return Math.floor(m / 60) + " h " + String(m % 60).padStart(2, "0") + " min";
}

const STATE_TEXT = {ok: "ok", silent: "silent", warning: "warning", error: "error", closed: "closed"};

function renderStatus(status) {
  const p = status.progress;
  const run = status.paused && status.run === "RUNNING" ? "PAUSED" : status.run;
  const cells = [el("span", {class: "badge " + (run === "PAUSED" ? "paused" : statusClass(run))}, run)];
  if (p.test) {
    cells.push(el("span", {class: "cell"}, "Test " + p.test.number + " of " + p.test.of + ": ",
      el("b", {}, p.test.name), p.test.requirement ? " (" + p.test.requirement + ")" : ""));
  } else if (p.phase) {
    cells.push(el("span", {class: "cell"}, p.phase === "setup" ? "Setup" : p.phase === "teardown" ? "Teardown" : p.phase));
  } else if (status.suite) {
    cells.push(el("span", {class: "cell"}, status.suite));
  }
  if (p.steps_total) {
    cells.push(el("span", {class: "cell", title: "Steps run of the steps this run will execute"},
      "Steps " + p.steps_run + " / " + p.steps_total));
  }
  if (status.run === "RUNNING") {
    cells.push(el("span", {class: "cell", title: "Estimated from the durations of the steps run so far"},
      p.estimated ? "About " + duration(p.time_left_s) + " left" : "Time left: estimating"));
  }
  const chips = status.instruments.map((item) => el("span", {
    class: "chip st-" + item.state,
    title: item.source + ": " + STATE_TEXT[item.state] +
           (item.since_s != null ? ", last activity " + duration(item.since_s) + " ago" : "") +
           (item.text ? "\n" + item.text : "")},
    el("i", {class: "led"}), item.source,
    el("small", {}, item.state === "ok" ? (item.since_s != null ? duration(item.since_s) : "") : STATE_TEXT[item.state])));
  $("statusbar").replaceChildren(el("div", {class: "run"}, ...cells), el("div", {class: "chips"}, ...chips));
}

async function pollStatus() {
  try {
    renderStatus(await (await fetch("/api/status")).json());
  } catch (error) {
    $("statusbar").replaceChildren(el("span", {class: "note"}, "Status unavailable: " + error.message));
  }
}

pollStatus();
setInterval(pollStatus, 1000);
