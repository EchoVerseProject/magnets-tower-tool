// magnet's Tower Tool — app shell, storage, import, and views.
import { STRATS, EVID, DRIVERS, makeGame, makeContext, evaluateAll, roadmap, gemPlan, uwPlan, cardPlan, UW_KEYS,
  fmtCoins, fmtHours, isWaves } from "./engine.js";
import { profileFromExport, profileFromRows, KILLED_BY } from "./parse.js";
import { lineChart, columnChart, hbars, installTooltips } from "./charts.js";

const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const $ = s => document.querySelector(s);
const store = {
  get(k, d) { try { const v = localStorage.getItem(k); return v == null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* storage unavailable */ } },
  del(k) { try { localStorage.removeItem(k); } catch { /* ignore */ } },
};
const K = { profile: "mtt.profile.v1", strategy: "mtt.strategy", snaps: "mtt.snapshots.v1" };
// Fields you set yourself; they survive a new import.
const MANUAL = ["farmEnd", "farmEvid", "tourEvid", "mileTier", "mileTarget", "mileEvid", "ext", "uwShares", "horizon",
  "cardSlotCost", "gemsDay", "stonesDay", "resMode", "relic", "speedup", "dmgRange", "uwChoices"];

let G, P, strategy = store.get(K.strategy, "Farming"), cache = null;

// ------------------------------------------------------------------ boot
async function boot() {
  installTooltips();
  const res = await fetch("data/game.json");
  G = makeGame(await res.json());
  P = store.get(K.profile, null);
  window.addEventListener("hashchange", render);
  renderStrategy();
  render();
}

function compute() {
  if (!P) return null;
  if (cache && cache.strategy === strategy && cache.P === P) return cache;
  const ctx = makeContext(G, P, strategy);
  const ev = evaluateAll(ctx);
  cache = { strategy, P, ctx, ev, rm: roadmap(ctx), gems: gemPlan(ctx, ev), uw: uwPlan(ctx), cards: cardPlan(ctx) };
  // remember what was actually recommended for this export, so the next import can show what you acted on
  const snaps = store.get(K.snaps, []);
  const last = snaps[snaps.length - 1];
  if (last && last.at === (P.exportedAt || P.importedAt) && ctx.ready) {
    last.recs = { strategy, buy: ev.workshop.filter(r => r.key > 0).slice(0, 5).map(r => r.id),
      labs: ev.labs.filter(r => r.key > 0).slice(0, 5).map(r => r.id) };
    store.set(K.snaps, snaps);
  }
  return cache;
}
function save() { cache = null; store.set(K.profile, P); }

// ------------------------------------------------------------------ import
async function importFile(file) {
  const text = await file.text();
  let json;
  try { json = JSON.parse(text.replace(/^﻿/, "")); } catch { return toast("That file is not valid JSON. Use tool_export.json from the game.", true); }
  let fresh;
  try { fresh = profileFromExport(G, json); } catch (e) { return toast(e.message, true); }
  const old = P || {};
  for (const k of MANUAL) if (old[k] != null) fresh[k] = old[k];
  // keep values you typed for fields the export lacks
  for (const k of ["cph", "farmTier", "farmWave", "tourWave"]) if (fresh[k] == null && old[k] != null) fresh[k] = old[k];
  fresh.importedAt = new Date().toISOString();
  snapshot(fresh);
  P = fresh;
  save();
  toast(`Imported ${fresh.userName ? fresh.userName + "'s " : ""}export${fresh.exportedAt ? " from " + new Date(fresh.exportedAt).toLocaleString() : ""}.`);
  location.hash = "#/";
  render();
}

async function loadSample(name) {
  const rows = await (await fetch(`data/samples/${name}.json`)).json();
  P = profileFromRows(G, rows);
  P.source = "sample";
  save();
  location.hash = "#/";
  render();
}

// ------------------------------------------------------------------ change tracking
function snapshot(prof) {
  const snaps = store.get(K.snaps, []);
  const at = prof.exportedAt || prof.importedAt;
  if (snaps.some(s => s.at === at)) return;
  let recs = null;
  try {
    const ctx = makeContext(G, prof, strategy);
    const ev = evaluateAll(ctx);
    recs = { strategy, buy: ev.workshop.filter(r => r.key > 0).slice(0, 5).map(r => r.id),
      labs: ev.labs.filter(r => r.key > 0).slice(0, 5).map(r => r.id) };
  } catch { /* incomplete profile */ }
  snaps.push({ at, coins: prof.coins, gems: prof.gems, stones: prof.stones, cph: prof.cph, ws: prof.ws, labs: prof.labs,
    enh: prof.enh, tierWave: prof.tierWave, uw: prof.uw, recs,
    lifetimeCoins: prof.lifetime?.coins });
  store.set(K.snaps, snaps.slice(-30));
}

function diffSnaps(a, b) {
  const out = { ws: [], labs: [], enh: [], waves: [], followed: [], uw: [] };
  const nameWS = id => G.ws[id]?.name || id, nameLab = id => G.lab[id]?.name || id, nameEn = id => G.enh[id]?.name || id;
  for (const [id, v] of Object.entries(b.ws || {})) if ((v || 0) > (a.ws?.[id] || 0)) out.ws.push({ id, name: nameWS(id), from: a.ws?.[id] || 0, to: v });
  for (const [id, v] of Object.entries(b.labs || {})) if ((v || 0) > (a.labs?.[id] || 0)) out.labs.push({ id, name: nameLab(id), from: a.labs?.[id] || 0, to: v });
  for (const [id, v] of Object.entries(b.enh || {})) if ((v || 0) > (a.enh?.[id] || 0)) out.enh.push({ id, name: nameEn(id), from: a.enh?.[id] || 0, to: v });
  for (const [t, w] of Object.entries(b.tierWave || {})) if (w > (a.tierWave?.[t] || 0)) out.waves.push({ tier: t, from: a.tierWave?.[t] || 0, to: w });
  for (const k of UW_KEYS) {
    const x = a.uw?.[k], y = b.uw?.[k];
    if (y?.owned && !x?.owned) out.uw.push(`${G.uw[k].name} unlocked`);
    else if (y?.owned) y.levels.forEach((l, j) => { if (l > (x?.levels?.[j] || 0)) out.uw.push(`${G.uw[k].name} · ${G.uw[k].stats[j].name} ${x?.levels?.[j] || 0} → ${l}`); });
  }
  if (a.recs) {
    const up = new Set([...out.ws, ...out.labs].map(x => x.id));
    out.followed = [...a.recs.buy, ...a.recs.labs].map(id => ({ id, name: G.ws[id]?.name || G.lab[id]?.name || G.enh[id]?.name || id, done: up.has(id) }));
  }
  return out;
}

// ------------------------------------------------------------------ chrome
function renderStrategy() {
  $("#strategy").innerHTML = STRATS.map(s => `<button type="button" aria-pressed="${s === strategy}" data-s="${s}">${s}</button>`).join("");
  $("#strategy").onclick = e => {
    const b = e.target.closest("button[data-s]"); if (!b) return;
    strategy = b.dataset.s; store.set(K.strategy, strategy); cache = null; renderStrategy(); render();
  };
}

const ROUTES = [["", "Dashboard"], ["workshop", "Workshop"], ["labs", "Labs"], ["roadmap", "Roadmap"], ["gems", "Gems"],
  ["uw", "Ultimate Weapons"], ["cards", "Cards & Modules"], ["history", "History"], ["profile", "Profile"], ["about", "Sources"]];

function render() {
  const route = (location.hash.replace(/^#\/?/, "").split("?")[0]) || "";
  $("#tabs").innerHTML = P ? ROUTES.map(([r, n]) => `<a href="#/${r}" class="${r === route ? "on" : ""}">${n}</a>`).join("") : "";
  $("#strategyBox").style.display = P ? "" : "none";
  const view = !P ? welcome : ({ "": dashboard, workshop, labs, roadmap: roadmapView, gems, uw: uwView, cards, history, profile, about })[route] || dashboard;
  $("#main").innerHTML = view();
  bindView(route);
  window.scrollTo({ top: 0 });
}

function toast(msg, bad = false) {
  const t = document.createElement("div");
  t.className = `banner ${bad ? "warn" : "ok"}`;
  t.style.cssText = "position:fixed;right:16px;bottom:16px;z-index:60;max-width:420px";
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 5000);
}

// ------------------------------------------------------------------ helpers
const tag = (t, cls = t) => t ? `<span class="tag ${esc(cls)}">${esc(t)}</span>` : "";
const bar = (f, v = false) => `<div class="bar${v ? " v" : ""}"><i style="width:${Math.max(0, Math.min(100, f * 100)).toFixed(1)}%"></i></div>`;
const unit = ctx => isWaves(ctx) ? "Extra waves" : ctx.strat === 1 ? "% more coins" : "% growth index";
const kpi = (l, v, s, cls = "") => `<div class="kpi ${cls}"><div class="l">${esc(l)}</div><div class="v" title="${esc(v)}">${esc(v)}</div><div class="s">${esc(s || "")}</div></div>`;
const panel = (title, body, cls = "", right = "") => `<section class="panel ${cls}"><div class="ph"><h2 class="${cls}">${title}</h2>${right}</div>${body}</section>`;
const goal = () => ({ Farming: "more coins & cells per hour", Tournament: "highest tournament wave",
  Milestones: "reach your next milestone", Balanced: "fastest overall account growth" })[strategy];

function banners(ctx) {
  const b = [];
  if (P.source === "sample") b.push(["warn", `${P.label || "Hypothetical sample"} is loaded so you can explore. Import your own tool_export.json to replace it.`]);
  if (!ctx.ready) b.push(["warn", "Workshop levels are missing - import your export or fill them on Profile. Recommendations stay hidden until then."]);
  else if (ctx.stratMsg) b.push(["warn", `${ctx.stratMsg} (Profile)`]);
  if (!P.farmEnd || !P.farmEvid) b.push(["info", "Tell the tool how your runs end (Profile → Run evidence). It decides whether damage or survival limits you."]);
  if (!ctx.cpd) b.push(["warn", "Coins per hour is missing: lab ranking by cost and the roadmap need it."]);
  return b.map(([c, t]) => `<div class="banner ${c}">${esc(t)}</div>`).join("");
}

// ------------------------------------------------------------------ welcome
function welcome() {
  return `<div class="drop" id="drop">
    <div class="hero">magnet's Tower Tool</div>
    <p class="sub">Workshop, Lab, Roadmap, Gems, Ultimate Weapons and Cards optimizer for <b>The Tower – Idle Tower Defense</b>.</p>
    <h2>Drop your <code>tool_export.json</code> here</h2>
    <p><label class="btn" for="file">Choose file…</label> <button class="btn ghost" data-sample="mid">Try a hypothetical sample</button></p>
    <ol class="steps">
      <li>In the game, tap your <b>Player ID five times</b> (first time only) to reveal the export.</li>
      <li>Go to <b>Settings → Toggles → External Tools Export → Manual Export</b>. Turn on <i>Auto Export</i> to keep it current.</li>
      <li>Android: the file is at <code>Android/data/com.TechTreeGames.TheTower/files/tool_export.json</code>. Copy it to this device and drop it here.</li>
      <li>Your data stays in this browser. Nothing is uploaded.</li>
    </ol></div>`;
}

// ------------------------------------------------------------------ dashboard
function dashboard() {
  const { ctx, ev, rm, gems: gp, uw } = compute();
  const wsel = [ctx.wdF, ctx.wdT, ctx.wdM, ctx.wdF][ctx.strat - 1];
  const bott = !P.farmEvid && ctx.strat !== 2 ? "UNKNOWN" : wsel === 1 ? "DAMAGE" : wsel === 0 ? "SURVIVAL" : "UNKNOWN";
  const sf = ev.saveFor;
  const saveTxt = !sf.best ? "Nothing to rank yet." : sf.verdict === "buy-best" ? `✔ No need to save: your top pick (${sf.best.name}) is affordable now.`
    : sf.verdict === "save" ? `◆ Save for ${sf.best.name}${sf.affordable ? ` instead of buying ${sf.affordable.name}` : ""}: ${fmtCoins(sf.best.cost - (P.coins || 0))} more coins${sf.best.hoursToAfford != null ? ` (~${fmtHours(sf.best.hoursToAfford)})` : ""}.`
      : `✔ Buy ${sf.affordable.name} now, then save for ${sf.best.name}: the delay it causes is worth less than its benefit.`;
  const top = ev.buyNow[0];
  const labsTop = ev.labs.filter(r => r.key > 0).slice(0, 5);
  const counter = ctx.strat === 1 && top && (top.driver === DRIVERS[1] || top.driver === DRIVERS[2]);
  const followed = lastDiff();
  return `${banners(ctx)}
  <div class="kpis">
    ${kpi("Available coins", fmtCoins(P.coins), P.cph ? `${fmtCoins(P.cph)} per hour` : "coins/hour not set")}
    ${kpi("Gems · Stones", `${P.gems ?? "—"} · ${P.stones ?? "—"}`, "gems · power stones", "violet")}
    ${kpi("Lab slots", ctx.slotsKnown ? `${ctx.free} free / ${ctx.slots}` : "—", ctx.free > 0 ? "fill idle slots first" : "all slots busy", "good")}
    ${kpi("Main bottleneck", bott, "from your run evidence", "bad")}
    ${kpi("Goal", strategy, goal(), "violet")}
    ${kpi("Unit of gain", unit(ctx), "how 'Gain' is measured", "warn")}
  </div>
  <div class="grid g2">
    ${panel("⚡ Buy now · Workshop & Enhancements", ev.buyNow.length ? `<div class="tw"><table><thead><tr><th>#</th><th>Upgrade</th><th class="num">Level</th><th class="num">Cost</th><th class="num">Gain</th><th>Efficiency</th><th class="c">Confidence</th></tr></thead><tbody>
      ${ev.buyNow.map((r, i) => `<tr><td class="rank">${i + 1}</td><td class="name">${esc(r.name)} ${r.kind === "EN" ? tag("Enhancement") : ""}</td><td class="num">${r.level} → ${r.level + 1}</td><td class="num">${fmtCoins(r.cost)}</td><td class="num">${esc(r.gain)}</td><td>${bar(r.effIndex / 100)}</td><td class="c">${tag(r.confidence)}</td></tr>`).join("")}
      </tbody></table></div><div class="why">Why #1: ${esc(top.reason)}</div>` : `<p class="empty">${!ctx.ready ? "Waiting for Workshop levels." : ctx.stratMsg || "Nothing affordable has a modeled gain for this goal."}</p>`)}
    ${panel("⚗ Research next · Laboratory", labsTop.length ? `<div class="tw"><table><thead><tr><th>#</th><th>Research</th><th class="num">Level</th><th class="num">Cost</th><th class="num">Time</th><th class="num">Gain</th><th class="c">Slot</th></tr></thead><tbody>
      ${labsTop.map((r, i) => `<tr><td class="rank v">${i + 1}</td><td class="name">${esc(r.name)}</td><td class="num">${r.level} → ${r.level + 1}</td><td class="num">${fmtCoins(r.cost)}</td><td class="num">${fmtHours(r.hours)}</td><td class="num">${esc(r.gain)}</td><td class="c">${i < ctx.free ? tag("▶ Start", "start") : '<span class="dim">queue</span>'}</td></tr>`).join("")}
      </tbody></table></div><div class="why">Why #1: ${esc(labsTop[0].reason)} Confidence: ${esc(labsTop[0].confidence)}.</div>` : `<p class="empty">${!ctx.ready ? "Waiting for profile data." : ctx.stratMsg || "No modeled lab gain for this goal (see Labs)."}</p>`, "violet")}
    ${panel("◆ Save for", `<div class="pb"><b>${esc(saveTxt)}</b></div>${sf.unaffordable.length ? `<div class="tw"><table><thead><tr><th>Worth saving for</th><th class="num">Need</th><th class="num">Time</th><th class="num">Gain</th><th class="c">Confidence</th></tr></thead><tbody>
      ${sf.unaffordable.map(r => `<tr><td class="name">${esc(r.name)}</td><td class="num">${fmtCoins(r.cost - (P.coins || 0))}</td><td class="num">${fmtHours(r.hoursToAfford)}</td><td class="num">${esc(r.gain)}</td><td class="c">${tag(r.confidence)}</td></tr>`).join("")}</tbody></table></div>` : ""}`, "amber")}
    ${panel("▲ Bottlenecks (from your evidence)", `<div class="pb"><ul class="list">
      ${[["Damage", wsel === 1 ? ["LIMITING", "bad"] : wsel === 0 ? ["not limiting", "good"] : ["unknown", "warn"], wsel === 1 ? "Runs end with enemies piling up: damage gains convert to waves." : wsel === 0 ? "Your evidence points to survival instead." : "Tell Profile what ends your runs."],
         ["Survivability", wsel === 0 ? ["LIMITING", "bad"] : wsel === 1 ? ["not limiting", "good"] : ["unknown", "warn"], wsel === 0 ? "Tower takes big hits: health/defense gains convert to waves." : wsel === 1 ? "Your evidence points to damage instead." : "Both weighted equally (low confidence)."],
         ["Economy", ctx.strat === 1 && !ctx.farmDeath && P.farmEnd ? ["LIMITING", "bad"] : ctx.cpd ? ["measured", "good"] : ["unknown", "warn"], ctx.cpd ? `${fmtCoins(ctx.cpd)} coins/day measured.` : "Enter coins per hour."],
         ["Research", !ctx.slotsKnown ? ["unknown", "warn"] : ctx.resTime ? ["TIME-LIMITED", "bad"] : ctx.free > 0 ? ["IDLE SLOT", "bad"] : ["coin-limited", "good"], ctx.resTime ? "All slots busy: Lab Speed and extra slots add value." : ctx.free > 0 ? `${ctx.free} slot(s) idle: start the top research now.` : "Research waits on coins."]]
        .map(([l, [s, c], w]) => `<li class="row"><span><b>${l}</b><br><span class="dim">${esc(w)}</span></span><span class="${c}" style="font-weight:800;white-space:nowrap">${s}</span></li>`).join("")}
      ${counter ? `<li class="warn">Farming is selected but the top buy is a combat stat: your runs end by death, so more waves earn more coins than the next economy upgrade.</li>` : ""}
      </ul></div>`, "red")}
    ${panel("➜ Roadmap · next 5 of 20", rm.steps.length ? `<div class="tw"><table><thead><tr><th>#</th><th>Investment</th><th>Type</th><th class="num">Cost</th><th>When</th><th class="num">Gain</th></tr></thead><tbody>
      ${rm.steps.slice(0, 5).map(s => `<tr><td class="rank">${s.k}</td><td class="name">${esc(s.name)} <span class="dim">${s.from} → ${s.to}</span></td><td>${tag({ WS: "Workshop", EN: "Enhancement", LAB: "Lab" }[s.kind])}</td><td class="num">${fmtCoins(s.cost)}</td><td class="dim">${esc(s.note)}</td><td class="num">${esc(s.gain)}</td></tr>`).join("")}
      </tbody></table></div>` : `<p class="empty">${esc(rm.reason || "No modeled gains left.")}</p>`, "", `<a class="btn ghost" href="#/roadmap">Full roadmap</a>`)}
    ${panel("◈ Gems · ⚔ Ultimate Weapons", `<div class="pb"><ul class="list">
      <li><b>Best gem buy:</b> ${gp.now ? `${esc(gp.now.name)} (${gp.now.gems} gems)` : "No quantified gem option is affordable."}</li>
      <li><b>Gems worth saving for:</b> ${gp.save ? `${esc(gp.save.name)} - ${gp.save.need} more gems` : "nothing beats the best affordable option"}</li>
      <li><b>New weapon:</b> ${uw.choices.length ? `${esc(uw.choices[0].name)} ranks first of the offered weapons` : uw.owned >= 9 ? "all owned" : `next costs ${uw.nextCost} stones - enter the 3 choices on Ultimate Weapons`}</li>
      <li><b>Stones:</b> ${esc(uw.ranked[0] ? `best upgrade ${uw.ranked[0].label} (+${((Math.exp(uw.ranked[0].gain) - 1) * 100).toFixed(2)}% coins for ${uw.ranked[0].cost})` : uw.owned ? (uw.econ ? "no stone upgrade has a computed coin gain yet (see Ultimate Weapons)" : "ranked by judgment for this goal (see Ultimate Weapons)") : uw.verdict)}</li>
      </ul></div>`, "violet")}
  </div>
  ${followed ? `<div style="margin-top:16px">${panel("↻ Since your last import", followed)}</div>` : ""}`;
}

function lastDiff() {
  const snaps = store.get(K.snaps, []);
  if (snaps.length < 2) return "";
  const a = snaps[snaps.length - 2], b = snaps[snaps.length - 1];
  const d = diffSnaps(a, b);
  const items = [...d.ws.map(x => `${x.name} ${x.from} → ${x.to}`), ...d.labs.map(x => `${x.name} (lab) ${x.from} → ${x.to}`),
    ...d.enh.map(x => `${x.name} ${x.from} → ${x.to}`), ...d.uw, ...d.waves.map(x => `Tier ${x.tier} best wave ${x.from} → ${x.to}`)];
  const fol = d.followed.filter(f => f.done).length;
  return `<div class="pb"><p class="dim">${new Date(a.at).toLocaleString()} → ${new Date(b.at).toLocaleString()}</p>
    ${items.length ? `<p>${items.slice(0, 12).map(esc).join(" · ")}${items.length > 12 ? ` · +${items.length - 12} more` : ""}</p>` : "<p class='dim'>No level changes.</p>"}
    ${d.followed.length ? `<p>You acted on <b>${fol} of ${d.followed.length}</b> recommendations from last time. <a href="#/history">Details</a></p>` : ""}</div>`;
}

// ------------------------------------------------------------------ workshop / labs
function filterBar(id, opts) {
  const cur = store.get(`mtt.filter.${id}`, opts[0][0]);
  return `<div class="seg" data-filter="${id}">${opts.map(([v, l]) => `<button type="button" data-v="${v}" aria-pressed="${v === cur}">${l}</button>`).join("")}</div>`;
}
const filt = (id, d) => store.get(`mtt.filter.${id}`, d);

function workshop() {
  const { ctx, ev } = compute();
  const f = filt("ws", "ranked");
  const rows = ev.workshop.filter(r => f === "all" || (f === "ranked" ? r.key > 0 : f === "nq" ? !r.modeled : r.kind === "EN"));
  return `<h1>Workshop optimizer</h1><p class="sub">All 48 upgrades and 18 enhancements, ranked for <b>${esc(strategy)}</b> by outcome per coin. Unit: ${esc(unit(ctx))}.</p>
  ${banners(ctx)}
  <div style="margin-bottom:10px">${filterBar("ws", [["ranked", "Ranked"], ["all", "All"], ["en", "Enhancements"], ["nq", "Not quantified"]])}</div>
  <section class="panel"><div class="tw"><table><thead><tr><th>#</th><th>Upgrade</th><th>Category</th><th class="num">Level</th><th>Progress</th><th class="num">Next cost</th><th class="num">+10 lv</th><th class="num">Buyable</th><th class="num">Gain</th><th>Efficiency</th><th class="num">Afford</th><th class="c">Confidence</th><th>Reason / note</th></tr></thead><tbody>
  ${rows.map(r => {
    const g = G.ws[r.id];
    let p10 = null, can = null;
    if (g && r.level < r.max) {
      p10 = (g.cum[Math.min(r.max, r.level + 10)] - g.cum[r.level]) * r.discF;
      can = 0; while (r.level + can < r.max && (g.cum[r.level + can + 1] - g.cum[r.level]) * r.discF <= (P.coins || 0)) can++;
    }
    return `<tr><td class="rank">${r.rank ?? "–"}</td><td class="name">${esc(r.name)} ${r.kind === "EN" ? tag("Enhancement") : ""}</td><td class="dim">${esc(r.category)}</td>
    <td class="num">${r.level} / ${r.max}</td><td>${bar(r.level / r.max)}</td><td class="num">${r.cost != null ? fmtCoins(r.cost) : "MAX"}</td>
    <td class="num dim">${p10 != null ? fmtCoins(p10) : ""}</td><td class="num">${can ?? ""}</td>
    <td class="num">${r.key > 0 ? esc(r.gain) : `<span class="dim">${esc(r.status)}</span>`}</td><td>${r.key > 0 ? bar(r.effIndex / 100) : ""}</td>
    <td class="num">${r.key > 0 ? (r.afford ? '<span class="good">✔</span>' : esc(fmtHours(r.hoursToAfford))) : ""}</td>
    <td class="c">${r.key > 0 || !r.modeled ? tag(r.confidence) : ""}</td><td class="reason">${esc(r.reason || "")}</td></tr>`;
  }).join("") || `<tr><td colspan="13" class="empty">Nothing in this view.</td></tr>`}
  </tbody></table></div></section>`;
}

function labs() {
  const { ctx, ev } = compute();
  const f = filt("lab", "ranked");
  const rows = ev.labs.filter(r => f === "all" || (f === "ranked" ? r.key > 0 : f === "available" ? r.unlocked && r.level < r.max : !r.modeled));
  return `<h1>Laboratory optimizer</h1><p class="sub">All ${ev.labs.length} labs, ranked for <b>${esc(strategy)}</b> by outcome per resource-day (coin cost in days of income + slot time). Long research is not penalised when its payoff justifies it.</p>
  ${banners(ctx)}
  <div class="kpis">${kpi("Lab slots", `${ctx.free} free / ${ctx.slots}`, "fill free slots first", "good")}${kpi("Research limited by", ctx.resTime ? "TIME" : "COINS / IDLE", ctx.resTime ? "Lab Speed adds value" : "Lab Speed adds little now", "violet")}
  ${kpi("Lab speed", `${ctx.labMult.toFixed(2)}x`, "lab x relic x boost")}${kpi("Coins / day", ctx.cpd ? fmtCoins(ctx.cpd) : "—", "prices coins vs slot time", "good")}
  ${kpi("Researching", (P.activeLabs || []).map(s => G.lab[s.lab]?.name).filter(Boolean).join(", ") || "none", (P.activeLabs || []).map(s => s.hours != null ? fmtHours(s.hours) + " left" : "").join(", "), "violet")}
  ${kpi("Unit", unit(ctx), "Gain column", "warn")}</div>
  <div style="margin-bottom:10px">${filterBar("lab", [["ranked", "Ranked"], ["available", "Available"], ["all", "All"], ["nq", "Not quantified"]])}</div>
  <section class="panel"><div class="tw"><table><thead><tr><th>#</th><th>Research</th><th>Category</th><th class="num">Level</th><th>Progress</th><th class="num">Next cost</th><th class="num">Time</th><th class="num">Gain</th><th class="num">Gain / day</th><th>Efficiency</th><th>Status</th><th class="c">Confidence</th><th>Reason / note</th></tr></thead><tbody>
  ${rows.map(r => `<tr><td class="rank v">${r.rank ?? "–"}</td><td class="name">${esc(r.name)}</td><td class="dim">${esc(r.category)}</td><td class="num">${r.level} / ${r.max}</td><td>${bar(r.level / r.max, true)}</td>
    <td class="num">${r.cost != null ? fmtCoins(r.cost) : "MAX"}</td><td class="num">${r.hours != null ? fmtHours(r.hours) : ""}</td>
    <td class="num">${r.key > 0 ? esc(r.gain) : ""}</td><td class="num dim">${r.key > 0 && r.perDay != null ? (isWaves(ctx) ? r.perDay.toFixed(3) + " w/d" : (r.perDay * 100).toPrecision(3) + "%/d") : ""}</td>
    <td>${r.key > 0 ? bar(r.effIndex / 100, true) : ""}</td>
    <td>${r.key > 0 && r.rank <= ctx.free ? tag("▶ Start now", "start") : `<span class="dim">${esc(r.key > 0 ? "Queue" : r.status)}</span>`}</td>
    <td class="c">${r.key > 0 || !r.modeled ? tag(r.confidence) : ""}</td><td class="reason">${esc(r.reason || "")}</td></tr>`).join("") || `<tr><td colspan="13" class="empty">Nothing in this view.</td></tr>`}
  </tbody></table></div></section>`;
}

// ------------------------------------------------------------------ roadmap
function roadmapView() {
  const { ctx, rm, uw } = compute();
  const steps = rm.steps;
  const total = steps.length ? steps[steps.length - 1].total : 0;
  const fmtTot = v => isWaves(ctx) ? `+${v.toFixed(1)} waves` : `+${((Math.exp(v) - 1) * 100).toFixed(2)}%`;
  return `<h1>20-investment roadmap</h1><p class="sub">Sequential plan for <b>${esc(strategy)}</b>: after each step the simulated account is updated, costs and prerequisites are rechecked, and the next best investment is chosen. Workshop steps bundle levels (up to one day of income, or until the runner-up becomes better). Labs respect slot capacity and finish before their next level.</p>
  ${banners(ctx)}
  <div class="kpis">${kpi("Status", steps.length ? `${steps.length} steps` : "not ready", rm.reason || "levels + income present")}
  ${kpi("Total coins", steps.length ? fmtCoins(steps[steps.length - 1].cum) : "—", "cumulative cost")}
  ${kpi("Fully funded in", steps.length ? fmtHours(Math.max(...steps.map(s => s.funded))) : "—", "at your coins/hour", "violet")}
  ${kpi("Total outcome", steps.length ? fmtTot(total) : "—", "after all steps", "good")}</div>
  ${panel("Investment steps", steps.length ? `<div class="tw"><table><thead><tr><th>#</th><th>Investment</th><th>Type</th><th class="num">Level</th><th class="num">Cost</th><th class="num">Cumulative</th><th>Funding / timing</th><th class="num">Gain</th><th>Driver</th><th class="c">Confidence</th><th class="num">Running total</th></tr></thead><tbody>
    ${steps.map(s => `<tr><td class="rank">${s.k}</td><td class="name">${esc(s.name)}</td><td>${tag({ WS: "Workshop", EN: "Enhancement", LAB: "Lab" }[s.kind])}</td><td class="num">${s.from} → ${s.to}</td><td class="num">${fmtCoins(s.cost)}</td><td class="num">${fmtCoins(s.cum)}</td><td class="dim">${esc(s.note)}</td><td class="num">${esc(s.gain)}</td><td class="dim">${esc(s.driver)}</td><td class="c">${tag(s.confidence)}</td><td class="num">${fmtTot(s.total)}</td></tr>`).join("")}
    </tbody></table></div>` : `<p class="empty">${esc(rm.reason || "No modeled gains left for this goal.")}</p>`)}
  ${steps.length ? `<div style="margin-top:16px">${panel("Cumulative outcome along the roadmap", `<div class="pb">${lineChart(steps.map(s => ({ x: s.k, y: isWaves(ctx) ? s.total : (Math.exp(s.total) - 1) * 100, tip: `<b>Step ${s.k}</b> ${esc(s.name)}<br>${fmtTot(s.total)} total` })), { yLabel: isWaves(ctx) ? "Extra waves" : "% gain" })}</div>`)}</div>` : ""}
  <div style="margin-top:16px">${panel("Power Stone track (separate stone budget)", uw.track.length ? `<div class="tw"><table><thead><tr><th>#</th><th>Stone upgrade</th><th class="num">Level</th><th class="num">Stones</th><th class="num">Cumulative</th><th>Funded</th><th class="num">Coin gain</th><th>Note</th></tr></thead><tbody>
    ${uw.track.map(t => `<tr><td class="rank v">${t.step}</td><td class="name">${esc(t.label)}</td><td class="num">${t.from} → ${t.to}</td><td class="num">${t.cost}</td><td class="num">${t.cum}</td><td>${esc(t.when)}</td><td class="num">+${((Math.exp(t.gain) - 1) * 100).toFixed(2)}%</td><td class="dim">${t.cooldown ? "Cooldown: sync effect included; irreversible - confirm first." : ""}</td></tr>`).join("")}
    </tbody></table></div>` : `<p class="empty">${uw.econ ? "No stone upgrade has a computed coin gain yet (own Golden Tower / Black Hole / Death Wave, or add kill-share estimates on Profile)." : "Stone upgrades are not computed for this goal - see Ultimate Weapons for judgment."}</p>`, "violet")}</div>`;
}

// ------------------------------------------------------------------ gems
function gems() {
  const { ctx, gems: gp } = compute();
  return `<h1>Gem investment planner</h1><p class="sub">Gem options valued for <b>${esc(strategy)}</b> as outcome × days enjoyed within your ${ctx.horizon}-day horizon${ctx.horizonDefault ? " (default - change on Profile)" : ""}.</p>
  <div class="kpis">${kpi("Available gems", P.gems ?? "—", "from your export")}${kpi("Gem income / day", P.gemsDay ?? "—", "set on Profile", "violet")}
  ${kpi("Best now", gp.now?.name || "—", "highest value per gem you can afford", "good")}${kpi("Worth saving for", gp.save?.name || "—", gp.save ? `${gp.save.need} more gems` : "nothing better is out of reach", "warn")}</div>
  ${panel("Options", `<div class="tw"><table><thead><tr><th>Gem option</th><th class="num">Gems</th><th class="c">Affordable</th><th class="num">Value</th><th class="num">Value / gem</th><th class="num">Still needed</th><th>Explanation</th></tr></thead><tbody>
  ${gp.opts.map(o => `<tr style="${o === gp.now ? "background:#10221a" : o === gp.save ? "background:#1f1a10" : ""}"><td class="name">${esc(o.name)}</td><td class="num">${o.gems ?? "—"}</td><td class="c">${o.gems == null ? "" : o.afford ? '<span class="good">✔</span>' : '<span class="dim">✖</span>'}</td>
    <td class="num">${o.quantified ? (o.value == null ? "—" : o.value.toFixed(3)) : tag("Judgment")}</td><td class="num">${o.perGem ? o.perGem.toExponential(2) : ""}</td>
    <td class="num">${o.need != null ? o.need + (o.days != null ? ` (${o.days.toFixed(1)} d)` : "") : ""}</td><td class="reason">${esc(o.why)}</td></tr>`).join("")}
  </tbody></table></div>
  <div class="why">${gp.now ? `Best now: ${esc(gp.now.name)}.` : "No quantified option is affordable."} ${gp.opportunity != null ? `Opportunity cost: about ${gp.opportunity.toFixed(3)} outcome-days from the next-best option with the same gems.` : ""} Value = improvement × days it is enjoyed within your horizon.</div>`)}`;
}

// ------------------------------------------------------------------ ultimate weapons
function uwView() {
  const { ctx, uw } = compute();
  const names = UW_KEYS.map(k => G.uw[k].name);
  const ch = P.uwChoices || [];
  return `<h1>Ultimate Weapons & Power Stones</h1><p class="sub">Coin effects (Golden Tower, Black Hole, Death Wave and cooldown sync) are computed; the combat value of weapons is strategy judgment and labelled as such.</p>
  <div class="kpis">${kpi("Power Stones", P.stones ?? "—", "available")}${kpi("Weapons owned", `${uw.owned} / 9`, "", "violet")}
  ${kpi("Next weapon", uw.nextCost != null ? `${uw.nextCost} stones` : "all owned", "price rises per weapon")}${kpi("UW coin multiplier", `${uw.cur.mult.toFixed(3)}x`, "average", "good")}
  ${kpi("Sync", uw.cur.syncB ? "GT+BH synced" : "not synced", "equal cooldowns stack multipliers", "warn")}${kpi("Stone income", P.stonesDay ? `${P.stonesDay}/day` : "—", "set on Profile", "violet")}</div>
  <div class="grid g2">
  ${panel("New weapon: the three choices offered", `<div class="pb"><p class="dim">The game offers three random weapons. Pick them here:</p>
    <div class="grid g3">${[0, 1, 2].map(i => `<select data-uwchoice="${i}"><option value="">— choice ${i + 1} —</option>${names.map(n => `<option ${ch[i] === n ? "selected" : ""}>${esc(n)}</option>`).join("")}</select>`).join("")}</div></div>
    ${uw.choices.length ? `<div class="tw"><table><thead><tr><th>#</th><th>Weapon</th><th>Role</th><th>Coin gain</th><th>Fits</th><th>Why</th></tr></thead><tbody>
    ${uw.choices.map((c, i) => `<tr><td class="rank">${c.score >= 0 ? i + 1 : "–"}</td><td class="name">${esc(c.name)}</td><td class="dim">${esc(c.role)}</td><td>${c.gain > 0 ? `+${((Math.exp(c.gain) - 1) * 100).toFixed(1)}%` : '<span class="dim">no coin effect</span>'}</td><td>${esc(c.fit)}</td><td class="reason">${esc(c.why)}</td></tr>`).join("")}
    </tbody></table></div>` : ""}<div class="why">${esc(uw.verdict)}</div>`)}
  ${panel("Cooldown sync", `<div class="pb"><ul class="list">
    <li class="row"><span>Golden Tower</span><span class="dim">${P.uw?.golden_tower?.owned ? `x${uw.cur.M.toFixed(1)} for ${uw.cur.Dg}s every ${uw.cur.CDg}s (uptime ${(uw.cur.ug * 100).toFixed(1)}%)` : "not owned"}</span></li>
    <li class="row"><span>Black Hole</span><span class="dim">${P.uw?.black_hole?.owned ? `${uw.cur.Db}s every ${uw.cur.CDb}s · coin bonus x${uw.cur.B.toFixed(2)}` : "not owned"}</span></li>
    <li class="row"><span>Death Wave</span><span class="dim">${P.uw?.death_wave?.owned ? `x${uw.cur.Qd} every ${uw.cur.CDd}s · coin bonus x${uw.cur.W.toFixed(2)}` : "not owned"}</span></li>
    <li>${uw.cur.syncB ? "✔ GT and BH cooldowns are equal: Black Hole kills land inside Golden Tower and get both multipliers. Keep cooldown upgrades paired." : "Equal GT/BH cooldowns would stack their coin multipliers. Upgrades that create or break a sync are flagged below."}</li>
    </ul></div>`, "amber")}
  </div>
  <div style="margin-top:16px">${panel("Upgrade next: every stone upgrade on weapons you own", `<div class="tw"><table><thead><tr><th>#</th><th>Weapon · stat</th><th class="num">Level</th><th class="num">Stones</th><th>Value</th><th class="num">Coin gain</th><th>Sync</th><th>Assessment</th></tr></thead><tbody>
    ${uw.ups.filter(u => u.owned).map(u => `<tr><td class="rank v">${u.rank ?? "–"}</td><td class="name">${esc(u.label)}</td><td class="num">${u.level >= u.max ? "MAX" : `${u.level} → ${u.level + 1}`}</td><td class="num">${u.cost ?? ""}</td><td class="dim">${u.from ? `${esc(u.from)} → ${esc(u.to)}` : ""}</td>
      <td class="num">${u.needsShare ? '<span class="dim">needs share input</span>' : u.gain != null ? `${u.gain >= 0 ? "+" : ""}${((Math.exp(u.gain) - 1) * 100).toFixed(2)}%` : '<span class="dim">not computed</span>'}</td>
      <td class="${String(u.sync).startsWith("⚠") ? "bad" : "good"}">${esc(u.sync || "")}</td><td class="reason">${u.level >= u.max ? "Maxed." : u.rank ? "Computed coin gain." : u.gain != null && ctx.strat % 3 === 1 ? "No coin gain now - do not buy for coins." : `Judgment: ${esc(u.judgment)} (combat effect not computed).`}</td></tr>`).join("") || `<tr><td colspan="8" class="empty">You don't own a weapon yet. Pick the three offered weapons above.</td></tr>`}
    </tbody></table></div>`, "violet")}</div>`;
}

// ------------------------------------------------------------------ cards & modules
function cards() {
  const { ctx, cards: cp } = compute();
  const m = P.modules || {};
  return `<h1>Cards & Modules</h1><p class="sub">Card values are computed for cards whose effect the engine models (Damage, Attack Speed, Health, Range, Coins, Critical Chance, Extra Defense); the rest are listed for your judgment.</p>
  <div class="kpis">${kpi("Card slots", cp.slots || "—", "from your export")}${kpi("Cards owned", cp.rows.length, "unlocked", "violet")}
  ${kpi("Modeled picks", cp.rows.filter(r => r.recommended).length, "best for this goal", "good")}${kpi("Your choice", cp.freeAfterModeled, "slots left for judgment cards", "warn")}
  ${kpi("Modules", m.inventory ?? 0, `${m.equipped ?? 0} equipped`, "violet")}${kpi("Module pity counter", m.pity ?? "—", "as stored in your export")}</div>
  ${panel("Card loadout for " + esc(strategy), `<div class="tw"><table><thead><tr><th>Card</th><th>Rarity</th><th class="num">Level</th><th class="num">Effect</th><th class="num">Value of equipping</th><th class="c">Equipped</th><th class="c">Recommended</th><th>Notes</th></tr></thead><tbody>
    ${cp.rows.map(r => `<tr><td class="name">${esc(r.name)}</td><td class="dim">${esc(r.rarity)}</td><td class="num">${r.level}</td><td class="num">${esc(r.effect)}</td>
      <td class="num">${r.modeled ? (r.V > 1e-12 ? esc(r.gain) : '<span class="dim">no gain for this goal</span>') : tag("Judgment")}</td>
      <td class="c">${r.equipped ? "✔" : ""}</td><td class="c">${r.recommended ? '<span class="good">✔ equip</span>' : ""}</td><td class="reason">${esc(r.desc)}</td></tr>`).join("") || `<tr><td colspan="8" class="empty">No cards found in your export.</td></tr>`}
    </tbody></table></div>
    <div class="why">${cp.freeAfterModeled > 0 ? `Equip the ✔ cards, then fill ${cp.freeAfterModeled} slot(s) with judgment cards that suit your goal (e.g. Cash for in-run economy, Demon Mode / Second Wind for survival pushes).` : "All slots are taken by modeled cards with a computed gain."}
    ${cp.swaps.length ? ` Consider unequipping: ${cp.swaps.map(s => esc(s.name)).join(", ")}.` : ""} Card levels come from random copies, so the advice is about which owned cards to equip.</div>`)}
  <div style="margin-top:16px">${panel("Modules", `<div class="pb"><p>${m.inventory ? `${m.inventory} modules owned, ${m.equipped} equipped.` : "No modules in your export yet. Modules unlock later in the game."}</p>
    <p class="dim">Module advice is judgment only: their value depends on rarities, substats and merges that the verified model does not cover. Module pulls cost 20 gems; 2.5% epic chance; pity at 150 pulls (your export's pity counter: ${m.pity ?? "—"}; its exact meaning is not documented).</p></div>`, "violet")}</div>`;
}

// ------------------------------------------------------------------ history
function history() {
  const runs = P.runs || [];
  const farm = runs.filter(r => r.realTime > 0);
  const kb = {};
  runs.forEach(r => { const n = r.killedBy == null ? "Unknown" : KILLED_BY[r.killedBy] || (r.killedBy < 0 || r.killedBy >= 99 ? "None / quit" : `Type ${r.killedBy}`); kb[n] = (kb[n] || 0) + 1; });
  const snaps = store.get(K.snaps, []);
  const dt = d => new Date(d).toLocaleDateString(undefined, { month: "short", day: "numeric" });
  return `<h1>Run history & progress</h1><p class="sub">From the Battle History in your latest export (the game keeps your recent runs), plus every export you've imported in this browser.</p>
  <div class="kpis">${kpi("Runs in export", runs.length, `${runs.filter(r => r.tour).length} tournament`)}
  ${kpi("Best wave", runs.length ? Math.max(...runs.map(r => r.wave || 0)) : "—", runs.length ? `tier ${runs.reduce((a, r) => (r.wave > a.wave ? r : a), runs[0]).tier}` : "", "violet")}
  ${kpi("Coins / hour", P.cph ? fmtCoins(P.cph) : "—", P.derived ? `last ${P.derived.cphRuns} farming runs` : "", "good")}
  ${kpi("Lifetime coins", P.lifetime?.coins ? fmtCoins(P.lifetime.coins) : "—", "earned", "warn")}
  ${kpi("Imports saved", snaps.length, "in this browser", "violet")}${kpi("Playing since", P.lifetime?.started ? dt(P.lifetime.started) : "—", "")}</div>
  <div class="grid g2">
  ${panel("Wave reached per run", `<div class="pb">${lineChart(runs.map(r => ({ x: dt(r.date), y: r.wave || 0, alt: r.tour, tip: `<b>${dt(r.date)}</b> · tier ${r.tier}${r.tour ? " · tournament" : ""}<br>wave ${r.wave} · ${fmtHours(r.realTime / 3600)} · killed by ${esc(KILLED_BY[r.killedBy] || "?")}` })), { yLabel: "Farming runs", altLabel: "Tournament" })}</div>`)}
  ${panel("Coins per hour per run", `<div class="pb">${columnChart(farm.map(r => ({ x: dt(r.date), y: r.coins / (r.realTime / 3600), alt: r.tour, tip: `<b>${dt(r.date)}</b> · tier ${r.tier}<br>${fmtCoins(r.coins / (r.realTime / 3600))} coins/h (${fmtCoins(r.coins)} in ${fmtHours(r.realTime / 3600)})` })), { label: "Coins per hour" })}</div>`)}
  ${panel("What killed the tower", `<div class="pb">${hbars(Object.entries(kb).sort((a, b) => b[1] - a[1]).map(([k, v]) => ({ label: k, value: v, tip: `${v} of ${runs.length} runs` })))}
    <p class="dim">Fact from your runs, shown as context. The enemy type that lands the last hit does not by itself prove a damage or survival bottleneck, so it doesn't change your run evidence.</p></div>`, "red")}
  ${panel("Recommendations you followed", followedTable(snaps), "violet")}
  </div>
  <div style="margin-top:16px">${panel("Runs", `<div class="tw"><table><thead><tr><th>Date</th><th class="num">Tier</th><th class="num">Wave</th><th class="num">Real time</th><th class="num">Coins</th><th class="num">Coins/h</th><th>Killed by</th><th class="num">Damage taken</th><th class="num">Regen</th><th class="c">Tournament</th></tr></thead><tbody>
    ${[...runs].reverse().map(r => `<tr><td>${new Date(r.date).toLocaleString()}</td><td class="num">${r.tier}</td><td class="num">${r.wave}</td><td class="num">${fmtHours(r.realTime / 3600)}</td><td class="num">${fmtCoins(r.coins)}</td><td class="num">${r.realTime ? fmtCoins(r.coins / (r.realTime / 3600)) : ""}</td><td>${esc(KILLED_BY[r.killedBy] || "—")}</td><td class="num">${fmtCoins(r.damageTaken)}</td><td class="num">${fmtCoins(r.regen)}</td><td class="c">${r.tour ? "✔" : ""}</td></tr>`).join("") || `<tr><td colspan="10" class="empty">No runs in this export.</td></tr>`}
    </tbody></table></div>`)}</div>`;
}

function followedTable(snaps) {
  if (snaps.length < 2) return `<p class="empty">Import a newer export later and this shows what changed and which recommendations you acted on.</p>`;
  const rows = [];
  for (let i = snaps.length - 1; i > 0 && rows.length < 6; i--) {
    const d = diffSnaps(snaps[i - 1], snaps[i]);
    const done = d.followed.filter(f => f.done).length;
    rows.push(`<tr><td>${new Date(snaps[i].at).toLocaleDateString()}</td><td class="num">${d.ws.length + d.labs.length + d.enh.length}</td><td class="num">${d.followed.length ? `${done} / ${d.followed.length}` : "—"}</td><td class="reason">${esc(d.followed.filter(f => f.done).map(f => f.name).join(", ") || "—")}</td></tr>`);
  }
  return `<div class="tw"><table><thead><tr><th>Import</th><th class="num">Items levelled</th><th class="num">Recs followed</th><th>Followed</th></tr></thead><tbody>${rows.join("")}</tbody></table></div>`;
}

// ------------------------------------------------------------------ profile
const F = (key, label, type, hint, opts) => ({ key, label, type, hint, opts });
const FIELDS = [
  ["Run evidence (decides your bottleneck)", [
    F("farmEnd", "How do farming runs end?", "select", "'Tower dies' means more survival or damage gives longer, richer runs.", ["", "Tower dies", "I end the run"]),
    F("farmEvid", "At the end of a run, what limits you?", "select", "Enemies pile up = damage-limited; big hits with few enemies = survival-limited.", ["", ...EVID]),
    F("tourEvid", "In tournaments, what limits you?", "select", "Used by the Tournament goal.", ["", ...EVID]),
    F("mileEvid", "When pushing milestones, what limits you?", "select", "Defaults to your farming answer.", ["Same as farming", ...EVID])]],
  ["Farming & targets", [
    F("cph", "Coins per hour", "number", "Imported from your recent farming runs; override if you know better."),
    F("farmTier", "Farming tier", "number", "Imported from recent runs."), F("farmWave", "Typical farming wave", "number", "Median of recent runs."),
    F("killShare", "Share of coins from kills (0-1)", "number", "Imported from lifetime totals."),
    F("tourWave", "Typical tournament wave", "number", "Imported from tournament runs."),
    F("mileTier", "Milestone tier you are pushing", "number", ""), F("mileTarget", "Next milestone wave on that tier", "number", "From the Milestones screen.")]],
  ["Currencies (imported) & income", [
    F("coins", "Available coins", "number", ""), F("gems", "Available gems", "number", ""), F("stones", "Power stones", "number", ""),
    F("gemsDay", "Gem income per day", "number", "Optional; for savings estimates."), F("stonesDay", "Stone income per day", "number", "Optional.")]],
  ["Laboratory", [
    F("slots", "Lab slots", "number", "Imported."), F("relic", "Lab speed from relics (fraction)", "number", "e.g. 0.05"),
    F("speedup", "Lab boost you keep active (x)", "number", "1 = none."),
    F("resMode", "What limits your research?", "select", "Auto reads your slots.", ["Auto (from lab slots)", "Coins limit my research", "Time limits my research"])]],
  ["Modifiers not in the export", [
    F("ext.cc", "Extra critical chance (fraction)", "number", "Modules/relics. Equipped cards are applied automatically."),
    F("ext.scc", "Extra super crit chance (fraction)", "number", ""), F("ext.def", "Extra defense % (fraction)", "number", ""),
    F("ext.cf", "Critical factor multiplier", "number", "1 = none."), F("ext.hp", "Health multiplier", "number", ""), F("ext.da", "Defense absolute multiplier", "number", ""),
    F("dmgRange", "Share of damage dealt at range (0-1)", "number", "Blank = 25% (Effective Paths default, flagged)."),
    F("ext.wsVault", "Extra Workshop discount (fraction)", "number", "Vault."), F("ext.enhVault", "Extra Enhancement discount (fraction)", "number", "Vault.")]],
  ["Ultimate Weapon coin estimates (optional)", [
    F("uwShares.bh", "Share of kills inside Black Hole", "number", "Your estimate, 0-1. Enables Black Hole coin values."),
    F("uwShares.dw", "Share of kills hit by Death Wave", "number", "0-1."), F("uwShares.sl", "Share of kills inside Spotlight", "number", "0-1."),
    F("uwShares.gtu", "Golden Tower uptime (if not owned in export)", "number", ""), F("uwShares.gtb", "Golden Tower bonus (if not owned in export)", "number", "")]],
  ["Gem planner", [F("horizon", "Planning horizon (days)", "number", "Blank = 30 (flagged)."), F("cardSlotCost", "Gem cost of your next card slot", "number", "Shown in game.")]],
];
const getPath = (o, p) => p.split(".").reduce((a, k) => (a == null ? a : a[k]), o);
function setPath(o, p, v) { const ks = p.split("."); let t = o; ks.slice(0, -1).forEach(k => { t[k] = t[k] || {}; t = t[k]; }); t[ks.at(-1)] = v; }

function profile() {
  const lvl = (kind, id, v, max) => `<input class="lv" type="number" min="0" max="${max}" data-level="${kind}:${id}" value="${v ?? ""}" aria-label="level">`;
  return `<h1>Profile</h1><p class="sub">${P.source === "export" ? `Imported ${esc(P.userName || "")} export ${P.exportedAt ? "from " + new Date(P.exportedAt).toLocaleString() : ""}.` : esc(P.label || "Manual profile")} Edits save instantly in this browser; a new import keeps your evidence and modifiers.</p>
  <p><label class="btn" for="file">⇪ Import a newer export</label> <button class="btn ghost" id="reset">Clear all data</button></p>
  <section class="panel"><div class="pb"><div class="form">${FIELDS.map(([h, fs]) => `<h3>${esc(h)}</h3>${fs.map(f => {
    const v = getPath(P, f.key);
    const input = f.type === "select" ? `<select data-field="${f.key}">${f.opts.map(o => `<option ${o === (v ?? "") ? "selected" : ""} value="${esc(o)}">${esc(o || "— choose —")}</option>`).join("")}</select>`
      : `<input type="number" step="any" data-field="${f.key}" value="${v ?? ""}">`;
    return `<label for="">${esc(f.label)}</label>${input}<span class="hint">${esc(f.hint)}</span>`;
  }).join("")}`).join("")}</div></div></section>
  <details class="sec"><summary>Workshop levels (${G.raw.workshop.length})</summary><div><div class="tw"><table><thead><tr><th>Upgrade</th><th>Category</th><th class="num">Level</th><th class="num">Max</th><th class="c">Unlocked</th></tr></thead><tbody>
    ${G.raw.workshop.map(w => `<tr><td class="name">${esc(w.name)}</td><td class="dim">${w.category}</td><td class="num">${lvl("ws", w.id, P.ws?.[w.id], w.maxLevel)}</td><td class="num dim">${w.maxLevel}</td>
      <td class="c">${w.unlockGroup === "Base" ? '<span class="dim">base</span>' : `<input type="checkbox" data-unlock="${w.id}" ${P.wsUnlocked?.[w.id] || (P.ws?.[w.id] > 0) ? "checked" : ""}>`}</td></tr>`).join("")}</tbody></table></div></div></details>
  <details class="sec"><summary>Enhancements (${G.raw.enhancements.length})</summary><div><div class="tw"><table><thead><tr><th>Enhancement</th><th class="num">Level</th><th class="num">Max</th></tr></thead><tbody>
    ${G.raw.enhancements.map(e => `<tr><td class="name">${esc(e.name)}</td><td class="num">${lvl("enh", e.id, P.enh?.[e.id], e.maxLevel)}</td><td class="num dim">${e.maxLevel}</td></tr>`).join("")}</tbody></table></div></div></details>
  <details class="sec"><summary>Lab levels (${G.raw.labs.length})</summary><div><div class="tw"><table><thead><tr><th>Research</th><th>Category</th><th class="num">Level</th><th class="num">Max</th></tr></thead><tbody>
    ${G.raw.labs.map(l => `<tr><td class="name">${esc(l.name)}</td><td class="dim">${esc(l.category)}</td><td class="num">${lvl("labs", l.id, P.labs?.[l.id], l.maxLevel)}</td><td class="num dim">${l.maxLevel}</td></tr>`).join("")}</tbody></table></div></div></details>
  <details class="sec"><summary>Ultimate Weapons</summary><div><div class="tw"><table><thead><tr><th>Weapon</th><th class="c">Owned</th><th class="num">Stat 1</th><th class="num">Stat 2</th><th class="num">Stat 3</th></tr></thead><tbody>
    ${UW_KEYS.map(k => `<tr><td class="name">${esc(G.uw[k].name)}</td><td class="c"><input type="checkbox" data-uwown="${k}" ${P.uw?.[k]?.owned ? "checked" : ""}></td>
      ${[0, 1, 2].map(j => `<td class="num" title="${esc(G.uw[k].stats[j].name)}"><input class="lv" type="number" min="0" data-uwlv="${k}:${j}" value="${P.uw?.[k]?.levels?.[j] ?? 0}"></td>`).join("")}</tr>`).join("")}</tbody></table></div></div></details>`;
}

// ------------------------------------------------------------------ about
function about() {
  const m = G.raw.meta;
  return `<h1>Sources & model</h1><p class="sub">What the numbers rest on and what is still uncertain.</p>
  <div class="grid g2">
  ${panel("Data", `<div class="pb"><ul class="list">
    <li><b>Game data:</b> <a href="${esc(m.sdk)}" rel="noopener">TheTowerSDK</a> (MIT, ${esc(m.license)}), commit ${esc(m.sdkCommit.slice(0, 10))} (${esc(m.sdkDate)}), game ${esc(m.gameVersion)}.</li>
    <li><b>Cross-checked:</b> ${G.raw.xcheck.labs.tot.toLocaleString()} lab costs/times vs the Effective Paths sheet (${G.raw.xcheck.labs.cbad} cost / ${G.raw.xcheck.labs.dbad} time mismatches); ${G.raw.xcheck.workshopLevels.toLocaleString()} workshop values; Wall Health costs vs the v29.1.3 game binary; 739 UW ladder rows.</li>
    <li><b>Enemy scaling</b> matches in-game anchors (Tier 10: ${Math.round(G.raw.anchors.hp_w8_t10).toLocaleString()} HP at wave 8, ${Math.round(G.raw.anchors.dmg_w10_t10).toLocaleString()} damage at wave 10).</li>
    <li><b>Engine</b> is verified against the original Excel engine in 9 scenarios (every cost, time, outcome and 20-step roadmap match).</li></ul></div>`)}
  ${panel("How recommendations are made", `<div class="pb"><ul class="list">
    <li>Strategies are goals: Farming = % more coins, Tournament / Milestones = extra waves, Balanced = income + discounts + research speed + progress.</li>
    <li>Damage & health gains → extra waves: ln(1 + gain) ÷ enemy growth per wave at your wave.</li>
    <li>Your bottleneck comes from your run evidence; "Not sure" weights both and marks picks Low confidence.</li>
    <li>Save-for decisions use an exact sequencing rule; labs are ranked per resource-day (coins as days of income + slot time).</li></ul></div>`, "violet")}
  ${panel("Not quantified (shown for judgment)", `<div class="pb"><p>Health Regen, Thorns, Lifesteal, Orbs, Shockwave, Land Mines, Knockback, Death Defy, Wall Rebuild, Rend Armor, Enemy Level Skip, in-run cash stats, most Ultimate Weapon / card mastery / module / bot / perk / enemy labs, combat value of Ultimate Weapons, most cards, modules, cells.</p></div>`, "amber")}
  ${panel("Approximations & discrepancies", `<div class="pb"><ul class="list">
    <li>Wave conversion is first-order; roadmap bundles are capped at one day of income.</li>
    <li>Farming survival value assumes each extra wave yields at least an average wave's coins.</li>
    <li>Rapid fire ignores the frame-rate cap; tournament scaling excludes league battle conditions.</li>
    <li>Damage enhancement: cost table has 600 levels vs 400 in SDK notes. Card slot prices are not in a verified source.</li></ul></div>`, "red")}
  </div><p class="dim" style="margin-top:16px">Unofficial fan tool, not affiliated with Tech Tree Games. Your data never leaves this browser.</p>`;
}

// ------------------------------------------------------------------ events
function bindView(route) {
  const drop = $("#drop");
  if (drop) {
    ["dragenter", "dragover"].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.add("over"); }));
    ["dragleave", "drop"].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.remove("over"); }));
    drop.addEventListener("drop", e => { const f = e.dataTransfer.files[0]; if (f) importFile(f); });
  }
  document.querySelectorAll("[data-sample]").forEach(b => { b.onclick = () => loadSample(b.dataset.sample); });
  document.querySelectorAll("[data-filter]").forEach(seg => {
    seg.onclick = e => { const b = e.target.closest("button[data-v]"); if (!b) return; store.set(`mtt.filter.${seg.dataset.filter}`, b.dataset.v); render(); };
  });
  const numOrNull = v => (v === "" ? null : Number(v));
  document.querySelectorAll("[data-field]").forEach(el => {
    el.onchange = () => { setPath(P, el.dataset.field, el.tagName === "SELECT" ? (el.value || null) : numOrNull(el.value)); save(); };
  });
  document.querySelectorAll("[data-level]").forEach(el => {
    el.onchange = () => { const [k, id] = el.dataset.level.split(":"); P[k] = P[k] || {}; P[k][id] = numOrNull(el.value); save(); };
  });
  document.querySelectorAll("[data-unlock]").forEach(el => { el.onchange = () => { P.wsUnlocked = P.wsUnlocked || {}; P.wsUnlocked[el.dataset.unlock] = el.checked; save(); }; });
  document.querySelectorAll("[data-uwown]").forEach(el => { el.onchange = () => { const k = el.dataset.uwown; P.uw[k] = P.uw[k] || { levels: [0, 0, 0] }; P.uw[k].owned = el.checked; save(); }; });
  document.querySelectorAll("[data-uwlv]").forEach(el => { el.onchange = () => { const [k, j] = el.dataset.uwlv.split(":"); P.uw[k] = P.uw[k] || { levels: [0, 0, 0] }; P.uw[k].levels[j] = Number(el.value) || 0; save(); }; });
  document.querySelectorAll("[data-uwchoice]").forEach(el => { el.onchange = () => { P.uwChoices = P.uwChoices || []; P.uwChoices[el.dataset.uwchoice] = el.value || null; save(); render(); }; });
  const reset = $("#reset");
  if (reset) reset.onclick = () => { if (confirm("Delete your profile and import history from this browser?")) { store.del(K.profile); store.del(K.snaps); P = null; cache = null; location.hash = "#/"; render(); } };
  void route;
}

document.addEventListener("change", e => { if (e.target.id === "file" && e.target.files[0]) { importFile(e.target.files[0]); e.target.value = ""; } });
boot().catch(err => { $("#main").innerHTML = `<div class="banner warn">Could not start: ${esc(err.message)}</div>`; });
