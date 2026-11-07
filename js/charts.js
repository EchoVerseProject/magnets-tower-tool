// Small inline-SVG charts: thin marks, hairline grid, hover tooltips, single hue per series.
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

function niceMax(v) {
  if (v <= 0) return 1;
  const p = 10 ** Math.floor(Math.log10(v));
  return [1, 2, 2.5, 5, 10].map(m => m * p).find(m => m >= v);
}
const compact = v => (v >= 1e6 ? `${+(v / 1e6).toFixed(1)}M` : v >= 1e4 ? `${+(v / 1e3).toFixed(0)}K` : v.toLocaleString("en-US", { maximumFractionDigits: 1 }));

// points: [{x: label, y: number, tip: html, alt: bool}] — alt points use the second hue (e.g. tournaments)
export function lineChart(points, { height = 220, yLabel = "", altLabel = "" } = {}) {
  const W = 760, H = height, m = { l: 48, r: 14, t: 12, b: 26 };
  if (!points.length) return `<p class="empty">No data yet.</p>`;
  const max = niceMax(Math.max(...points.map(p => p.y)));
  const x = i => m.l + (points.length === 1 ? (W - m.l - m.r) / 2 : i * (W - m.l - m.r) / (points.length - 1));
  const y = v => H - m.b - v / max * (H - m.t - m.b);
  const ticks = [0, .25, .5, .75, 1].map(f => f * max);
  const main = points.map((p, i) => [p, i]).filter(([p]) => !p.alt);
  const path = main.map(([p, i], k) => `${k ? "L" : "M"}${x(i).toFixed(1)},${y(p.y).toFixed(1)}`).join("");
  const step = Math.max(1, Math.ceil(points.length / 8));
  return `<svg class="chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(yLabel)}">
  <g class="grid">${ticks.map(t => `<line x1="${m.l}" x2="${W - m.r}" y1="${y(t)}" y2="${y(t)}"/><text x="${m.l - 6}" y="${y(t) + 4}" text-anchor="end">${compact(t)}</text>`).join("")}</g>
  ${points.map((p, i) => (i % step === 0 || (i === points.length - 1 && i % step >= step / 2)) ? `<text x="${x(i)}" y="${H - 8}" text-anchor="middle">${esc(p.x)}</text>` : "").join("")}
  <path d="${path}" fill="none" stroke="var(--chart-a)" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>
  ${points.map((p, i) => `<circle cx="${x(i)}" cy="${y(p.y)}" r="${p.alt ? 5 : 4}" fill="${p.alt ? "var(--chart-b)" : "var(--chart-a)"}" stroke="var(--panel)" stroke-width="2"/>`).join("")}
  ${points.map((p, i) => `<rect class="hit" x="${x(i) - 10}" y="${m.t}" width="20" height="${H - m.t - m.b}" data-tip="${esc(p.tip || `${p.x}: ${p.y}`)}"/>`).join("")}
  </svg>${altLabel ? `<div class="legend"><span><i style="background:var(--chart-a)"></i>${esc(yLabel)}</span><span><i style="background:var(--chart-b)"></i>${esc(altLabel)}</span></div>` : ""}`;
}

// bars: [{x, y, tip}] vertical columns from a single baseline
export function columnChart(bars, { height = 200, label = "" } = {}) {
  const W = 760, H = height, m = { l: 48, r: 14, t: 16, b: 26 };
  if (!bars.length) return `<p class="empty">No data yet.</p>`;
  const max = niceMax(Math.max(...bars.map(b => b.y)));
  const band = (W - m.l - m.r) / bars.length;
  const bw = Math.min(24, band - 2);
  const y = v => H - m.b - v / max * (H - m.t - m.b);
  const ticks = [0, .5, 1].map(f => f * max);
  const step = Math.max(1, Math.ceil(bars.length / 8));
  return `<svg class="chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(label)}">
  <g class="grid">${ticks.map(t => `<line x1="${m.l}" x2="${W - m.r}" y1="${y(t)}" y2="${y(t)}"/><text x="${m.l - 6}" y="${y(t) + 4}" text-anchor="end">${compact(t)}</text>`).join("")}</g>
  ${bars.map((b, i) => {
    const cx = m.l + band * i + band / 2, top = y(b.y), h = H - m.b - top;
    const r = Math.min(4, h, bw / 2);
    const d = h <= 0 ? "" : `M${cx - bw / 2},${H - m.b}V${top + r}Q${cx - bw / 2},${top} ${cx - bw / 2 + r},${top}H${cx + bw / 2 - r}Q${cx + bw / 2},${top} ${cx + bw / 2},${top + r}V${H - m.b}Z`;
    return `<path d="${d}" fill="${b.alt ? "var(--chart-b)" : "var(--chart-a)"}"/>
    ${(i % step === 0 || (i === bars.length - 1 && i % step >= step / 2)) ? `<text x="${cx}" y="${H - 8}" text-anchor="middle">${esc(b.x)}</text>` : ""}
    <rect class="hit" x="${cx - band / 2}" y="${m.t}" width="${band}" height="${H - m.t - m.b}" data-tip="${esc(b.tip || `${b.x}: ${b.y}`)}"/>`;
  }).join("")}
  </svg>`;
}

// horizontal bars with value labels at the tip: [{label, value, tip}]
export function hbars(items, { fmt = v => v } = {}) {
  if (!items.length) return `<p class="empty">No data yet.</p>`;
  const max = Math.max(...items.map(i => i.value)) || 1;
  return `<table><tbody>${items.map(i => `<tr data-tip="${esc(i.tip || "")}"><td style="width:34%">${esc(i.label)}</td>
    <td><div class="bar"><i style="width:${(i.value / max * 100).toFixed(1)}%"></i></div></td><td class="num" style="width:70px">${esc(fmt(i.value))}</td></tr>`).join("")}</tbody></table>`;
}

export function installTooltips(root = document) {
  let tip = document.querySelector(".tip");
  if (!tip) { tip = document.createElement("div"); tip.className = "tip"; document.body.appendChild(tip); }
  root.addEventListener("mousemove", e => {
    const t = e.target.closest?.("[data-tip]");
    if (!t || !t.dataset.tip) { tip.style.display = "none"; return; }
    tip.innerHTML = t.dataset.tip;
    tip.style.display = "block";
    const x = Math.min(e.clientX + 14, window.innerWidth - tip.offsetWidth - 8);
    tip.style.left = `${x}px`;
    tip.style.top = `${e.clientY + 14}px`;
  });
  root.addEventListener("mouseleave", () => { tip.style.display = "none"; });
}
