// benchtools test run viewer: the Graphs page (#140). SVG line charts, no library.
// Uses el, $, time and fetch helpers from app.js, loaded before this file.
"use strict";

const SVG = "http://www.w3.org/2000/svg";

function svg(tag, attrs, ...children) {
  const node = document.createElementNS(SVG, tag);
  for (const [key, value] of Object.entries(attrs || {})) node.setAttribute(key, value);
  for (const child of children) if (child !== null && child !== undefined) node.append(child);
  return node;
}

// Round numbers for an axis: about `count` ticks covering lo..hi.
function niceTicks(lo, hi, count) {
  if (!(hi > lo)) { const pad = Math.abs(lo) * 0.1 || 1; lo -= pad; hi += pad; }
  const raw = (hi - lo) / count;
  const power = Math.pow(10, Math.floor(Math.log10(raw)));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * power).find((s) => s >= raw);
  const first = Math.floor(lo / step);
  const last = Math.ceil(hi / step);
  const ticks = [];
  for (let k = first; k <= last; k++) ticks.push(k * step);
  return {ticks, lo: ticks[0], hi: ticks[ticks.length - 1], step};
}

function tickText(value, step) {
  const places = Math.max(0, -Math.floor(Math.log10(step)) + (step / Math.pow(10, Math.floor(Math.log10(step))) === 2.5 ? 1 : 0));
  return value.toFixed(Math.min(places, 6));
}

// A time of day; with *step* below a second, to the places the step needs.
function clock(t, step) {
  const d = new Date(t * 1000);
  const text = d.toLocaleTimeString([], {hour12: false});
  if (!(step < 1)) return text;
  const decimals = String(Number(step.toFixed(3))).split(".")[1] || "";
  const places = Math.max(1, decimals.length);
  return text + "." + String(d.getMilliseconds()).padStart(3, "0").slice(0, places);
}

// One chart: {id, title, unit, zero?, series: [{key, label, points: [[t, v]]}]}
// The x-axis label of a chart: a time of day, or seconds on the dongle's clock.
function xLabel(chart, t, step) {
  if (chart.x === "dongle") return Number(t.toFixed(3)) + " s";
  if (chart.xunit) return Number(t.toPrecision(6)) + " " + chart.xunit;
  return clock(t, step);
}

// Where the operator last hovered, in the time units of the charts: zoom centres there.
let hoverTime = null;

function lineChart(chart, span, markers, container) {
  const box = el("figure", {class: "chart"});
  // A point whose value is null is a gap: the line breaks there. Only points
  // within the span set the y range, so a zoomed chart fills its height.
  const x0 = span[0];
  const x1 = span[1] > span[0] ? span[1] : span[0] + 1;
  const points = chart.series.flatMap((s) => s.points)
    .filter((p) => p[1] != null && p[0] >= x0 && p[0] <= x1);
  const many = chart.series.length > 1;
  box.append(el("figcaption", {}, chart.title + (!many && chart.series[0] ? "  ·  " + chart.series[0].label : "") +
                                  (chart.x === "dongle" ? "  ·  time on the dongle's clock" : "")));
  if (many) {
    box.append(el("div", {class: "legend"}, ...chart.series.map((s, i) =>
      el("span", {}, el("i", {class: "swatch", style: "background: var(--series-" + (i % 8 + 1) + ")"}), s.label))));
  }
  if (!points.length) { box.append(el("div", {class: "note empty"}, "No data yet.")); return box; }

  const width = Math.max(320, ((container || $("graphs")).clientWidth || 800) - 2);
  const height = 220;
  const m = {left: 56, right: 12, top: 10, bottom: 26};
  const plotW = width - m.left - m.right;
  const plotH = height - m.top - m.bottom;
  let lo = Math.min(...points.map((p) => p[1]));
  let hi = Math.max(...points.map((p) => p[1]));
  if (chart.zero) { lo = Math.min(lo, 0); hi = Math.max(hi, 0); }
  const y = niceTicks(lo, hi, 4);
  const sx = (t) => m.left + (t - x0) / (x1 - x0) * plotW;
  const sy = (v) => m.top + (1 - (v - y.lo) / (y.hi - y.lo)) * plotH;

  const plot = svg("svg", {viewBox: "0 0 " + width + " " + height, width: width, height: height,
                           role: "img", "aria-label": chart.title});
  const clip = "clip-" + chart.id + "-" + Math.random().toString(36).slice(2, 8);
  plot.append(svg("clipPath", {id: clip}, svg("rect", {x: m.left, y: m.top - 4, width: plotW,
                                                       height: plotH + 8})));
  for (const v of y.ticks) {
    plot.append(svg("line", {x1: m.left, x2: width - m.right, y1: sy(v), y2: sy(v),
                             class: v === 0 && chart.zero ? "baseline" : "grid"}));
    plot.append(svg("text", {x: m.left - 6, y: sy(v) + 4, class: "tick", "text-anchor": "end"},
                    tickText(v, y.step)));
  }
  const xt = niceTicks(x0, x1, Math.max(2, Math.floor(plotW / 110)));
  for (const t of xt.ticks) {
    if (t < x0 || t > x1) continue;
    plot.append(svg("text", {x: sx(t), y: height - 8, class: "tick", "text-anchor": "middle"}, xLabel(chart, t, xt.step)));
  }
  for (const marker of markers) {
    if (marker.t < x0 || marker.t > x1) continue;
    plot.append(svg("line", {x1: sx(marker.t), x2: sx(marker.t), y1: m.top, y2: m.top + plotH,
                             class: "marker"}, svg("title", {}, clock(marker.t, 0.001) + "  " + marker.label)));
  }
  chart.series.forEach((s, i) => {
    if (!s.points.length) return;
    let pen = "M";
    const d = s.points.map((p) => {
      if (p[1] == null) { pen = "M"; return ""; }
      const step = pen + sx(p[0]).toFixed(1) + " " + sy(p[1]).toFixed(1);
      pen = "L";
      return step;
    }).join(" ");
    plot.append(svg("path", {d, class: "line", stroke: "var(--series-" + (i % 8 + 1) + ")",
                             "clip-path": "url(#" + clip + ")"}));
    if (s.points.length <= 60) {
      for (const p of s.points.filter((q) => q[1] != null && q[0] >= x0 && q[0] <= x1)) {
        plot.append(svg("circle", {cx: sx(p[0]), cy: sy(p[1]), r: 3, class: "point",
                                   fill: "var(--series-" + (i % 8 + 1) + ")"}));
      }
    }
  });

  // Hover: a crosshair and the nearest value of each series.
  const cross = svg("line", {y1: m.top, y2: m.top + plotH, class: "cross", visibility: "hidden"});
  plot.append(cross);
  const tip = el("div", {class: "tip", hidden: ""});
  plot.addEventListener("mousemove", (event) => {
    const rect = plot.getBoundingClientRect();
    const px = (event.clientX - rect.left) * width / rect.width;
    if (px < m.left || px > width - m.right) { cross.setAttribute("visibility", "hidden"); tip.hidden = true; return; }
    const t = x0 + (px - m.left) / plotW * (x1 - x0);
    hoverTime = t;
    cross.setAttribute("x1", px); cross.setAttribute("x2", px); cross.setAttribute("visibility", "visible");
    const lines = [xLabel(chart, t, 0.001)];
    chart.series.forEach((s) => {
      if (!s.points.length) return;
      const real = s.points.filter((p) => p[1] != null);
      if (!real.length) return;
      const near = real.reduce((a, b) => (Math.abs(b[0] - t) < Math.abs(a[0] - t) ? b : a));
      lines.push(s.label + ": " + Number(near[1].toPrecision(6)) + " " + chart.unit.replace("degC", "°C") +
                 (near.length > 2 ? "  (raw " + near[2] + ")" : ""));
    });
    tip.textContent = lines.join("\n");
    tip.hidden = false;
    tip.style.left = Math.min(px * rect.width / width + 12, rect.width - 220) + "px";
  });
  plot.addEventListener("mouseleave", () => { cross.setAttribute("visibility", "hidden"); tip.hidden = true; });
  box.append(el("div", {class: "plot"}, plot, tip));
  return box;
}

async function loadGraphs() {
  const query = "?ble=" + encodeURIComponent($("graph-ble").value) +
                "&expected_ms=" + encodeURIComponent($("graph-period").value.trim());
  const reply = await (await fetch("/api/graphs" + query)).json();
  if (!reply.charts) return;
  const select = $("graph-ble");
  const ids = reply.ble.devices.map((d) => d.addr);
  if (select.dataset.ids !== ids.join(",")) {
    select.dataset.ids = ids.join(",");
    select.replaceChildren(...reply.ble.devices.map((d) => el("option", {value: d.addr}, d.addr + " (" + d.adverts + ")")));
  }
  select.value = reply.ble.address;
  $("graph-period-note").textContent = reply.ble.period_ms == null ? "" :
    (reply.ble.expected ? "expected " : "median ") + reply.ble.period_ms.toFixed(1) + " ms";
  const charts = reply.charts.concat(reply.ble.address ? reply.ble.charts : []);
  // Charts on the host's clock share one time span and the step markers; the
  // advertising charts, on the dongle's clock, share theirs and have none.
  const spanOf = (group) => {
    const all = group.flatMap((c) => c.series.flatMap((s) => s.points.map((p) => p[0])));
    return all.length ? [Math.min(...all), Math.max(...all)] : [0, 1];
  };
  const host = spanOf(charts.filter((c) => c.x !== "dongle"));
  const dongle = spanOf(charts.filter((c) => c.x === "dongle"));
  $("graphs").replaceChildren(...(charts.length ? charts.map((c) => c.x === "dongle"
    ? lineChart(c, dongle, []) : lineChart(c, host, reply.markers))
    : [el("div", {class: "note"}, "No readings yet. Instruments log readings as a run measures them.")]));
}

$("graph-ble").addEventListener("change", loadGraphs);
$("graph-period").addEventListener("change", loadGraphs);
setInterval(() => { if (!$("page-graphs").hidden) loadGraphs(); }, 2000);
