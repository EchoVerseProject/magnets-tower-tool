// magnet's Tower Tool — optimization engine (pure ES module; runs in the browser and in Node).
//
// The model is a direct port of the verified Excel engine (see docs/MODEL.md):
//   1. A "state" is a set of levels. stats(state) computes every modeled stat and six
//      ln-outcomes: eDamage, eHP, coin income, UW coin multiplier, real game speed,
//      purchasing power and research speed.
//   2. A candidate (next level of an upgrade/lab/enhancement) is valued by recomputing the
//      state with that level +1 and turning the outcome deltas into the selected goal:
//      Farming = % coins, Tournament / Milestones = extra waves, Balanced = growth index.
//   3. Damage / health gains become waves via   waves = ln(1+gain) / enemy growth per wave.

export const STRATS = ["Farming", "Tournament", "Milestones", "Balanced"];
export const EVID = ["Enemies pile up at the tower", "Tower takes big hits with few enemies near", "Not sure"];
export const DRIVERS = ["Coin income", "Damage → more waves", "Survivability → more waves",
  "Purchasing power (discounts)", "Research speed"];

const C = {
  wsDiscStep: 0.005, wsDiscMax: 0.495, enhDiscStep: 0.003, enhDiscMax: 0.30, enhStep: 0.01,
  defCap: 0.98, rangeDefault: 0.25, labCoinStep: 0.003,
};
const BPS_KEYS = [0, 2, 2.5, 3, 3.5, 4, 4.5, 5, 5.5, 6, 6.5, 7, 7.5, 8, 8.5, 9, 9.5, 10, 11, 12, 13, 14, 15];
const BPS_RATES = [1, 0.96, 0.93, 0.9, 0.87, 0.84, 0.81, 0.79, 0.77, 0.75, 0.73, 0.71, 0.69, 0.67, 0.65, 0.63, 0.61,
  0.58, 0.56, 0.54, 0.53, 0.52, 0.51];
const SPD_KEYS = [0, 2, 2.5, 3, 3.5, 4, 4.5, 5];
const SPD_SCALE = [1.07, 1, 0.95, 0.92, 0.88, 0.84, 0.82, 0.8];

export const WS_VARS = ["DMG", "AS", "CC", "CF", "RANGE", "DPM", "MSC", "MST", "RFC", "RFD", "BSC", "BST", "SCC",
  "SCM", "HP", "DEFP", "DA", "WALL", "RECMAX", "CPK", "CPW"];
export const EN_VARS = ["E_DMG", "E_CF", "E_DPM", "E_SCM", "E_AS", "E_HP", "E_DA", "E_WALL", "E_COIN", "E_RECMAX"];
export const LB_VARS = ["L_DMG", "L_AS", "L_CF", "L_RANGE", "L_DPM", "L_SCC", "L_SCM", "L_HP", "L_DA", "L_DEFP",
  "L_WALL", "L_RECMAX", "L_CPK", "L_CPW", "L_DISC_ATK", "L_DISC_DEF", "L_DISC_UTL", "L_LABDISC", "L_LABSPEED",
  "L_GAMESPEED", "L_GT", "L_BH", "L_DW", "L_SL"];
export const VARS = [...WS_VARS, ...EN_VARS, ...LB_VARS];

const lookup = (x, keys, vals) => { let i = keys.length - 1; while (i > 0 && keys[i] > x) i--; return vals[i]; };
const clamp = (x, a, b) => Math.max(a, Math.min(b, x));
const num = (x, d = 0) => (typeof x === "number" && isFinite(x) ? x : d);

// ---------------------------------------------------------------- game data
export function makeGame(raw) {
  const G = { raw, ws: {}, wsRole: {}, lab: {}, labRole: {}, enh: {}, enhRole: {}, uw: raw.uw, cards: raw.cards };
  for (const w of raw.workshop) {
    const cum = [0];
    for (let i = 0; i < w.levels.length - 1; i++) cum.push(cum[i] + w.levels[i][1]);
    G.ws[w.id] = { ...w, cum };
    if (w.role !== "NQ") G.wsRole[w.role] = G.ws[w.id];
  }
  for (const l of raw.labs) {
    const cum = [0];
    for (let i = 1; i < l.levels.length; i++) cum.push(cum[i - 1] + l.levels[i][2]);
    G.lab[l.id] = { ...l, cum };
    if (l.role !== "NQ") G.labRole[l.role] = G.lab[l.id];
  }
  for (const e of raw.enhancements) {
    const cum = [0];
    for (let i = 0; i < e.costs.length - 1; i++) cum.push(cum[i] + e.costs[i]);
    G.enh[e.id] = { ...e, cum };
    if (e.role !== "NQ") G.enhRole[e.role] = G.enh[e.id];
  }
  G.enemy = raw.enemy;
  return G;
}

const wsv = (G, role, L) => { const w = G.wsRole[role]; return w.levels[clamp(Math.floor(L), 0, w.maxLevel)][0]; };
const le = (G, role, L) => {
  const l = G.labRole[role]; const row = l.levels[clamp(Math.floor(L), 0, l.maxLevel)];
  return num(row[1], 0);
};
export const labEffect = (G, id, L) => { const l = G.lab[id]; return num(l.levels[clamp(L, 0, l.maxLevel)][1], 0); };
export const uwValue = (G, key, j, L) => { const s = G.uw[key].stats[j]; return s.levels[clamp(L, 0, s.levels.length - 1)][2]; };
export const uwMax = (G, key, j) => G.uw[key].stats[j].levels.length - 1;

function growth(G, kind, tier, wave, tour) {
  const i = clamp(Math.round(wave / 50), 1, G.enemy.waves.length) - 1;
  if (tour) return G.enemy[kind === "hp" ? "hp_tour" : "dmg_tour"][i];
  return G.enemy[kind][String(clamp(tier, 1, 24))][i];
}

// ---------------------------------------------------------------- context (evidence, modifiers)
export function makeContext(G, P, strategy = "Farming", opts = {}) {
  const ctx = { G, P, strat: Math.max(1, STRATS.indexOf(strategy) + 1), strategy };
  const ex = P.ext || {};
  const cardFx = opts.useCards === false ? {} : cardEffects(G, P);
  ctx.cardFx = cardFx;
  ctx.ext = {
    cc: num(ex.cc) + num(cardFx.critChance), scc: num(ex.scc), def: num(ex.def) + num(cardFx.defense),
    wsVault: num(ex.wsVault), enhVault: num(ex.enhVault),
    cf: num(ex.cf, 0) > 0 ? ex.cf : 1, as: (num(ex.as, 0) > 0 ? ex.as : 1) * num(cardFx.attackSpeed, 1),
    hp: (num(ex.hp, 0) > 0 ? ex.hp : 1) * num(cardFx.health, 1), da: num(ex.da, 0) > 0 ? ex.da : 1,
    range: num(cardFx.range, 1), dmg: num(cardFx.damage, 1), coins: num(cardFx.coins, 1),
  };
  ctx.dmgRange = P.dmgRange == null || P.dmgRange === "" ? C.rangeDefault : P.dmgRange;
  ctx.dmgRangeDefault = P.dmgRange == null || P.dmgRange === "";
  ctx.k = P.killShare == null || P.killShare === "" ? 1 : P.killShare;
  ctx.kDefault = P.killShare == null || P.killShare === "";
  const wOf = e => (e === EVID[0] ? 1 : e === EVID[1] ? 0 : 0.5);
  ctx.farmOK = num(P.farmWave) > 0 && num(P.farmTier) >= 1 && num(P.farmTier) <= 24;
  ctx.farmDeath = P.farmEnd === "Tower dies" ? 1 : 0;
  ctx.farmEndKnown = !!P.farmEnd;
  ctx.wdF = wOf(P.farmEvid);
  ctx.wdT = wOf(P.tourEvid);
  ctx.wdM = !P.mileEvid || P.mileEvid === "Same as farming" ? ctx.wdF : wOf(P.mileEvid);
  ctx.Wf = num(P.farmWave);
  if (ctx.farmOK) { ctx.rHf = growth(G, "hp", P.farmTier, ctx.Wf); ctx.rDf = growth(G, "dmg", P.farmTier, ctx.Wf); }
  ctx.tourOK = num(P.tourWave) > 0;
  if (ctx.tourOK) { ctx.rHt = growth(G, "hp", 1, P.tourWave, true); ctx.rDt = growth(G, "dmg", 1, P.tourWave, true); }
  const mt = num(P.mileTier);
  ctx.Wm = mt >= 1 && mt <= 24 ? (num((P.tierWave || {})[mt]) > 0 ? P.tierWave[mt] : num(P.mileTarget)) : 0;
  ctx.mileOK = ctx.Wm > 0 && mt >= 1;
  ctx.mileGap = ctx.mileOK && num(P.mileTarget) > 0 ? Math.max(0, P.mileTarget - ctx.Wm) : null;
  if (ctx.mileOK) { ctx.rHm = growth(G, "hp", mt, ctx.Wm); ctx.rDm = growth(G, "dmg", mt, ctx.Wm); }
  ctx.cpd = num(P.cph) > 0 ? P.cph * 24 : null;
  ctx.slots = clamp(num(P.slots) || 1, 1, 5);
  ctx.slotsKnown = num(P.slots) > 0;
  ctx.busy = (P.activeLabs || []).filter(s => s && s.lab).length || num(P.busy);
  ctx.free = Math.max(0, ctx.slots - ctx.busy);
  ctx.resTime = P.resMode === "Time limits my research" ? 1 : P.resMode === "Coins limit my research" ? 0 :
    (ctx.busy >= ctx.slots ? 1 : 0);
  ctx.speedup = num(P.speedup, 0) > 0 ? P.speedup : 1;
  ctx.relic = num(P.relic);
  // UW-derived Golden Tower inputs (falls back to manual)
  const uw = uwCoinState(G, P);
  ctx.uw = uw;
  ctx.gtu = uw.cur.ug > 0 ? uw.cur.ug : num((P.uwShares || {}).gtu);
  ctx.gtb = (P.uw?.golden_tower?.owned) ? uw.cur.M : num((P.uwShares || {}).gtb);
  ctx.gtOK = ctx.gtu > 0 && ctx.gtb > 1;
  const sh = P.uwShares || {};
  ctx.bhS = num(sh.bh); ctx.dwS = num(sh.dw); ctx.slS = num(sh.sl);
  ctx.horizon = num(P.horizon) > 0 ? P.horizon : 30;
  ctx.horizonDefault = !(num(P.horizon) > 0);
  // levels
  ctx.L0 = levelsFromProfile(G, P);
  ctx.unl = {};
  for (const r of WS_VARS) ctx.unl[r] = wsUnlocked(G, P, G.wsRole[r].id) ? 1 : 0;
  ctx.missWS = WS_VARS.filter(r => ctx.unl[r] && (P.ws || {})[G.wsRole[r].id] == null).length;
  ctx.missLab = LB_VARS.filter(r => (P.labs || {})[G.labRole[r].id] == null).length;
  ctx.ready = ctx.missWS === 0 && Object.keys(P.ws || {}).length > 0;
  ctx.labStartGT = num((P.labs || {})["golden_tower_bonus"]);
  // spending shares (base coins spent so far)
  let sA = 0, sD = 0, sU = 0, sEn = 0, sLab = 0;
  for (const w of G.raw.workshop) {
    const v = G.ws[w.id].cum[clamp(num((P.ws || {})[w.id]), 0, w.maxLevel)];
    if (w.category === "Attack") sA += v; else if (w.category === "Defense") sD += v; else sU += v;
  }
  for (const e of G.raw.enhancements) sEn += G.enh[e.id].cum[clamp(num((P.enh || {})[e.id]), 0, e.maxLevel)];
  for (const l of G.raw.labs) sLab += G.lab[l.id].cum[clamp(num((P.labs || {})[l.id]), 0, G.lab[l.id].cum.length - 1)];
  const tot = Math.max(1, sA + sD + sU + sEn + sLab);
  Object.assign(ctx, { spend: { ws: sA + sD + sU, en: sEn, lab: sLab }, sA: sA / tot, sD: sD / tot, sU: sU / tot, sL: sLab / tot });
  ctx.labMult = le(G, "L_LABSPEED", ctx.L0.L_LABSPEED) * (1 + ctx.relic) * ctx.speedup;
  const s0 = baseStats(ctx, ctx.L0, true);
  ctx.CPK0 = s0.CPK; ctx.CPW0 = s0.CPW;
  ctx.S0 = stats(ctx, ctx.L0);
  ctx.stratMsg = [!ctx.farmOK && P.farmEnd === "Tower dies" ? "Enter your farming tier and wave." : "",
    ctx.tourOK ? "" : "Enter your typical tournament wave.", ctx.mileOK ? "" : "Enter your milestone tier and target wave.",
    ""][ctx.strat - 1];
  return ctx;
}

export function wsUnlocked(G, P, id) {
  const w = G.ws[id];
  if (w.unlockGroup === "Base") return true;
  const flag = (P.wsUnlocked || {})[id];
  if (flag === false) return false;
  return flag === true || num((P.ws || {})[id]) > 0;
}

export function levelsFromProfile(G, P) {
  const L = {};
  for (const r of WS_VARS) L[r] = num((P.ws || {})[G.wsRole[r].id]);
  for (const r of EN_VARS) L[r] = num((P.enh || {})[G.enhRole[r].id]);
  for (const r of LB_VARS) L[r] = num((P.labs || {})[G.labRole[r].id]);
  return L;
}

// ---------------------------------------------------------------- stats
function baseStats(ctx, L) {
  const { G, ext, unl } = ctx;
  const E = v => 1 + C.enhStep * v;
  return {
    AS: wsv(G, "AS", L.AS) * le(G, "L_AS", L.L_AS) * E(L.E_AS) * ext.as,
    RFC: unl.RFC * wsv(G, "RFC", L.RFC) / 100,
    RFD: wsv(G, "RFD", L.RFD),
    CC: Math.min(1, wsv(G, "CC", L.CC) / 100 + ext.cc),
    CF: wsv(G, "CF", L.CF) * le(G, "L_CF", L.L_CF) * E(L.E_CF) * ext.cf,
    SCC: unl.SCC * Math.min(1, wsv(G, "SCC", L.SCC) / 100 + le(G, "L_SCC", L.L_SCC) / 100 + ext.scc),
    SCM: wsv(G, "SCM", L.SCM) * le(G, "L_SCM", L.L_SCM) * E(L.E_SCM),
    MSC: unl.MSC * wsv(G, "MSC", L.MSC) / 100,
    MST: wsv(G, "MST", L.MST),
    BSC: unl.BSC * Math.min(1, wsv(G, "BSC", L.BSC) / 100),
    BST: wsv(G, "BST", L.BST),
    RNG: wsv(G, "RANGE", L.RANGE) * 10 * le(G, "L_RANGE", L.L_RANGE) * ext.range,
    DPMV: unl.DPM * wsv(G, "DPM", L.DPM) / 1000 * le(G, "L_DPM", L.L_DPM) * E(L.E_DPM),
    DMGF: wsv(G, "DMG", L.DMG) * le(G, "L_DMG", L.L_DMG) * E(L.E_DMG) * ext.dmg,
    H: wsv(G, "HP", L.HP) * le(G, "L_HP", L.L_HP) * E(L.E_HP) * ext.hp,
    DABS: unl.DA * wsv(G, "DA", L.DA) * le(G, "L_DA", L.L_DA) * E(L.E_DA) * ext.da,
    DP: Math.min(C.defCap, unl.DEFP * wsv(G, "DEFP", L.DEFP) / 100 + le(G, "L_DEFP", L.L_DEFP) / 100 + ext.def),
    WALL: unl.WALL * (wsv(G, "WALL", L.WALL) / 100 + le(G, "L_WALL", L.L_WALL) / 100) * E(L.E_WALL),
    REC: unl.RECMAX * (wsv(G, "RECMAX", L.RECMAX) + le(G, "L_RECMAX", L.L_RECMAX)) * E(L.E_RECMAX),
    CPK: wsv(G, "CPK", L.CPK) * le(G, "L_CPK", L.L_CPK) * E(L.E_COIN) ** 2 * ext.coins,
    CPW: wsv(G, "CPW", L.CPW) * le(G, "L_CPW", L.L_CPW) * ext.coins,
    GTM: ctx.gtOK ? 1 + ctx.gtu * (ctx.gtb + le(G, "L_GT", L.L_GT) - le(G, "L_GT", ctx.labStartGT) - 1) : 1,
    BHM: ctx.bhS > 0 ? 1 + ctx.bhS * (le(G, "L_BH", L.L_BH) - 1) : 1,
    DWM: ctx.dwS > 0 ? 1 + ctx.dwS * (le(G, "L_DW", L.L_DW) - 1) : 1,
    SLM: ctx.slS > 0 ? 1 + ctx.slS * (le(G, "L_SL", L.L_SL) - 1) : 1,
    SPD: le(G, "L_GAMESPEED", L.L_GAMESPEED),
    DSA: Math.min(0.99, Math.min(C.wsDiscMax, le(G, "L_DISC_ATK", L.L_DISC_ATK) / 100) + ctx.ext.wsVault),
    DSD: Math.min(0.99, Math.min(C.wsDiscMax, le(G, "L_DISC_DEF", L.L_DISC_DEF) / 100) + ctx.ext.wsVault),
    DSU: Math.min(0.99, Math.min(C.wsDiscMax, le(G, "L_DISC_UTL", L.L_DISC_UTL) / 100) + ctx.ext.wsVault),
    DSL: le(G, "L_LABDISC", L.L_LABDISC) / 100,
    RS: le(G, "L_LABSPEED", L.L_LABSPEED),
  };
}

export function stats(ctx, L) {
  const s = baseStats(ctx, L);
  const AS = s.AS;
  s.BPS = AS * (AS >= 42 ? 0.375 : AS >= 16 ? 0.505 - 0.005 * Math.floor(AS - 16) : lookup(AS, BPS_KEYS, BPS_RATES));
  const m = AS < 2.3 ? 3.75 : AS < 4 ? 3.65 : AS < 8 ? 3.5 : 3.35;
  s.RF = s.RFC <= 0 || s.RFD <= 0 ? 1 : 1 + (0.9 * s.RFD / (0.9 * s.RFD + 0.75 + 1 / (s.RFC * s.BPS))) * (m - 1);
  s.CRIT = (1 - s.CC) + s.CC * s.CF * (1 - s.SCC) + s.CC * s.CF * s.SCC * s.SCM;
  s.MS = 1 + s.MSC * (s.MST - 1);
  s.BNC = s.BSC >= 1 ? 1 + s.BST : s.BSC <= 0 ? 1 : 1 + s.BSC * (1 - s.BSC ** s.BST) / (1 - s.BSC);
  const r4 = x => Math.round(x * 1e4) / 1e4;
  s.RNGE = s.RNG * (1 - r4(r4(Math.max(Math.min(s.RNG, 220) - 80, 0) / 140) * 0.16));
  s.RDMG = 1 + s.RNGE * s.DPMV * ctx.dmgRange;
  s.lnEDMG = Math.log(s.DMGF) + Math.log(s.BPS * s.RF) + Math.log(s.CRIT) + Math.log(s.MS) + Math.log(s.BNC) + Math.log(s.RDMG);
  s.POOL = Math.max(s.WALL + s.REC, 1);
  s.lnEHP = Math.log((s.H * s.POOL + s.DABS) / (1 - s.DP));
  const cpk0 = ctx.CPK0 ?? s.CPK, cpw0 = ctx.CPW0 ?? s.CPW;
  s.lnECON = Math.log(ctx.k * s.CPK / cpk0 + (1 - ctx.k) * s.CPW / cpw0);
  s.lnUW = Math.log(s.GTM) + Math.log(s.BHM) + Math.log(s.DWM) + Math.log(s.SLM);
  s.lnSPD = Math.log(s.SPD * lookup(s.SPD, SPD_KEYS, SPD_SCALE));
  s.lnPP = -ctx.sA * Math.log(1 - s.DSA) - ctx.sD * Math.log(1 - s.DSD) - ctx.sU * Math.log(1 - s.DSU) - ctx.sL * Math.log(1 - s.DSL);
  s.lnRES = Math.log(s.RS);
  return s;
}

// Outcome components of moving from state a to state b, for the selected strategy.
export function components(ctx, a, b) {
  const d = k => b[k] - a[k];
  const dE = d("lnECON") + d("lnUW") + d("lnSPD");
  const dD = d("lnEDMG"), dH = d("lnEHP");
  const farmD = ctx.farmOK ? ctx.farmDeath * ctx.wdF * dD / ctx.rHf / ctx.Wf : 0;
  const farmH = ctx.farmOK ? ctx.farmDeath * (1 - ctx.wdF) * dH / ctx.rDf / ctx.Wf : 0;
  const mileD = ctx.mileOK ? ctx.wdM * dD / ctx.rHm : 0, mileH = ctx.mileOK ? (1 - ctx.wdM) * dH / ctx.rDm : 0;
  const tourD = ctx.tourOK ? ctx.wdT * dD / ctx.rHt : 0, tourH = ctx.tourOK ? (1 - ctx.wdT) * dH / ctx.rDt : 0;
  const s = ctx.strat;
  const c = {
    econ: s === 1 || s === 4 ? dE : 0,
    dmg: [farmD, tourD, mileD, farmD + (ctx.mileOK ? mileD / ctx.Wm : 0)][s - 1],
    surv: [farmH, tourH, mileH, farmH + (ctx.mileOK ? mileH / ctx.Wm : 0)][s - 1],
    pp: s === 4 ? d("lnPP") : 0,
    res: s === 4 ? ctx.resTime * d("lnRES") : 0,
  };
  c.V = c.econ + c.dmg + c.surv + c.pp + c.res;
  return c;
}

export const isWaves = ctx => ctx.strat === 2 || ctx.strat === 3;

export function gainText(ctx, V) {
  if (!isFinite(V)) return "";
  if (isWaves(ctx)) return `${V >= 0 ? "+" : ""}${V.toFixed(2)} waves`;
  const pct = (Math.exp(V) - 1) * 100;
  return `+${pct.toFixed(Math.abs(pct) < 10 ? 3 : 2)}% ${ctx.strat === 1 ? "coins" : "growth"}`;
}

// ---------------------------------------------------------------- candidates
function itemsOf(G) {
  return [...G.raw.workshop.map(x => ({ kind: "WS", item: G.ws[x.id] })),
    ...G.raw.enhancements.map(x => ({ kind: "EN", item: G.enh[x.id] })),
    ...G.raw.labs.map(x => ({ kind: "LAB", item: G.lab[x.id] }))];
}

function profileLevel(P, kind, id) {
  const src = kind === "WS" ? P.ws : kind === "EN" ? P.enh : P.labs;
  return (src || {})[id];
}

function enhUnlocked(G, P, id) {
  const lab = num((P.labs || {}).workshop_enhancements) >= 1;
  const flag = (P.enhUnlocked || {})[id];
  if (flag === false) return false;
  return lab && (flag === true || num((P.enh || {})[id]) > 0);
}

export function labUnlocked(G, P, id) {
  const l = G.lab[id];
  if (num((P.labs || {})[id]) > 0) return true;
  if (l.unlockTier === 0) return true;
  if (typeof l.unlockTier === "number") return num((P.tierWave || {})[l.unlockTier]) >= l.unlockWave;
  return false;
}

function inProgress(P, id) { return (P.activeLabs || []).some(s => s && s.lab === id); }

// Evaluate one candidate from state L (levels) and its stats S.
export function evalCandidate(ctx, kind, item, L, S, { roadmap = false } = {}) {
  const { G, P } = ctx;
  const role = item.role;
  const modeled = role !== "NQ";
  const level = modeled ? L[role] : num(profileLevel(P, kind, item.id));
  const max = item.maxLevel;
  const r = { kind, id: item.id, name: item.name, role, category: item.category, level, max, modeled };
  if (kind === "WS") {
    r.unlocked = wsUnlocked(G, P, item.id);
    r.eligible = r.unlocked && profileLevel(P, kind, item.id) != null && level < max;
    const disc = { Attack: S.DSA, Defense: S.DSD, Utility: S.DSU }[item.category];
    r.discF = 1 - disc;
    r.cost = level < max ? Math.round(item.levels[level][1] * r.discF) : null;
  } else if (kind === "EN") {
    r.unlocked = enhUnlocked(G, P, item.id);
    r.eligible = r.unlocked && level < max;
    const dl = { Attack: "enhancement_attack_coin_discount", Defense: "enhancement_defense_coin_discount",
      Utility: "enhancement_utility_coin_discount" }[item.category];
    r.discF = Math.max(0, 1 - Math.min(C.enhDiscMax, C.enhDiscStep * num((P.labs || {})[dl])) - ctx.ext.enhVault);
    r.cost = level < max ? item.costs[level] * r.discF : null;
  } else {
    r.unlocked = labUnlocked(G, P, item.id);
    r.researching = inProgress(P, item.id);
    r.eligible = r.unlocked && level < max && !r.researching;
    r.discF = 1 - S.DSL;
    const row = item.levels[level + 1 - (item.minLevel > 0 ? 0 : 0)];
    const nxt = item.levels.find(x => x[0] === level + 1);
    r.cost = level < max && nxt ? nxt[2] * r.discF : null;
    r.hours = level < max && nxt ? nxt[3] / (S.RS * (1 + ctx.relic) * ctx.speedup) : null;
    void row;
  }
  if (r.cost != null) {
    r.budgetDays = kind === "LAB" ? (ctx.cpd ? r.cost / ctx.cpd : 0) + r.hours / 24 / ctx.slots
      : ctx.cpd ? r.cost / ctx.cpd : null;
  }
  if (modeled && r.unlocked && level < max) {
    const L2 = { ...L, [role]: Math.min(level + 1, max) };
    const S2 = stats(ctx, L2);
    const c = components(ctx, S, S2);
    Object.assign(r, c);
    if (kind === "LAB" || roadmap) r.eff = r.budgetDays > 0 ? r.V / r.budgetDays : null;
    else r.eff = r.cost > 0 ? r.V / r.cost : null;
    r.key = ctx.ready && r.eligible && r.eff != null && r.V > 1e-12 ? r.eff : -1;
    r.gain = gainText(ctx, r.V);
    const comps = [c.econ, c.dmg, c.surv, c.pp, c.res];
    const mx = Math.max(...comps);
    r.driver = mx <= 0 ? "No gain" : DRIVERS[comps.indexOf(mx)];
    const est = (["RANGE", "DPM", "L_RANGE", "L_DPM", "E_DPM"].includes(role) && ctx.dmgRangeDefault)
      || (["CPK", "CPW", "L_CPK", "L_CPW", "E_COIN"].includes(role) && ctx.kDefault)
      || ["L_GT", "L_BH", "L_DW", "L_SL", "E_COIN"].includes(role);
    const wsel = [ctx.wdF, ctx.wdT, ctx.wdM, ctx.wdF][ctx.strat - 1];
    const low = (r.driver === DRIVERS[1] || r.driver === DRIVERS[2]) && wsel === 0.5;
    r.confidence = low ? "Low" : est || ctx.missLab > 0 ? "Medium" : "High";
    if (r.V <= 1e-12) r.reason = "Does not move this goal with your current evidence (e.g. it improves a stat that is not your bottleneck).";
    else {
      r.reason = `${r.driver}: ${r.gain} for ${fmtCoins(r.cost)} coins${r.hours != null ? ` and ${fmtHours(r.hours)}` : ""}.`;
      if (ctx.strat === 1 && (r.driver === DRIVERS[1] || r.driver === DRIVERS[2]))
        r.reason += ` Recommended for Farming because your farming runs end by death and ${r.driver === DRIVERS[1] ? "damage" : "survivability"} limits your waves; the extra waves add more coins per run than the next economy option.`;
    }
  } else {
    r.key = -1;
    if (!modeled) { r.driver = "Not quantified"; r.reason = item.nqReason || ""; r.confidence = "Judgment"; }
  }
  if (!roadmap) {
    r.afford = r.cost != null && P.coins != null && r.cost <= P.coins;
    r.hoursToAfford = r.cost != null && num(P.cph) > 0 ? Math.max(0, (r.cost - num(P.coins)) / P.cph) : null;
    r.status = statusOf(r);
  }
  return r;
}

function statusOf(r) {
  if (r.key > 0) return "Ranked";
  if (r.level >= r.max) return "Maxed";
  if (r.researching) return "Researching";
  if (!r.unlocked) return r.kind === "EN" ? "Locked (needs Workshop Enhancements)" : "Locked";
  if (!r.modeled) return "Not quantified";
  return "No gain for this goal";
}

function rank(list) {
  const order = [...list].sort((a, b) => b.key - a.key);
  order.forEach((r, i) => { r.rank = r.key > 0 ? i + 1 : null; });
  return order;
}

export function evaluateAll(ctx) {
  const L = ctx.L0, S = ctx.S0;
  const all = itemsOf(ctx.G).map(({ kind, item }) => evalCandidate(ctx, kind, item, L, S));
  const workshop = rank(all.filter(r => r.kind !== "LAB"));
  const labs = rank(all.filter(r => r.kind === "LAB"));
  const maxWS = Math.max(0, ...workshop.map(r => r.key));
  const maxLab = Math.max(0, ...labs.map(r => r.key));
  for (const r of workshop) r.effIndex = r.key > 0 ? r.key / maxWS * 100 : null;
  for (const r of labs) {
    r.effIndex = r.key > 0 ? r.key / maxLab * 100 : null;
    r.perDay = r.V != null && r.hours > 0 ? r.V / (r.hours / 24) : null;
  }
  const buyNow = workshop.filter(r => r.key > 0 && r.afford).slice(0, 5);
  return { workshop, labs, buyNow, saveFor: saveFor(ctx, workshop) };
}

// Exact sequencing rule (Smith's rule with current coins): buy cheaper A first only if
// V_A * (C_A + C_B - coins) > V_B * C_A.
function saveFor(ctx, ws) {
  const ranked = ws.filter(r => r.key > 0);
  const B = ranked[0];
  const A = ranked.find(r => r.afford);
  const out = { best: B, affordable: A, unaffordable: ranked.filter(r => !r.afford).slice(0, 3) };
  if (!B) out.verdict = "nothing";
  else if (B.afford) out.verdict = "buy-best";
  else if (!A) out.verdict = "save";
  else out.verdict = B.V * A.cost > A.V * (A.cost + B.cost - num(ctx.P.coins)) ? "save" : "buy-a-first";
  return out;
}

// ---------------------------------------------------------------- roadmap (sequential)
export function roadmap(ctx, steps = 20) {
  if (!ctx.ready || !ctx.cpd) return { steps: [], reason: !ctx.ready ? "Workshop levels missing" : "Enter coins per hour" };
  const { G, P } = ctx;
  let L = { ...ctx.L0 };
  let S = ctx.S0;
  const slots = [0, 1, 2, 3, 4].map(j => (j < ctx.slots ? num((P.activeLabs || [])[j]?.hours) : 1e9));
  const labDone = {};
  let cum = 0;
  const out = [];
  const items = VARS.map(v => ({ v, kind: WS_VARS.includes(v) ? "WS" : EN_VARS.includes(v) ? "EN" : "LAB",
    item: G.wsRole[v] || G.enhRole[v] || G.labRole[v] }));
  for (let k = 0; k < steps; k++) {
    const cands = items.map(({ kind, item }) => evalCandidate(ctx, kind, item, L, S, { roadmap: true }))
      .filter(r => r.key > 0).sort((a, b) => b.key - a.key);
    if (!cands.length) break;
    const pick = cands[0], runner = cands[1]?.key || 0;
    let n = 1, cost = pick.cost;
    if (pick.kind !== "LAB") {
      const cumArr = pick.kind === "WS" ? G.wsRole[pick.role].cum : G.enhRole[pick.role].cum;
      const costs = pick.kind === "WS" ? G.wsRole[pick.role].levels.map(x => x[1]) : G.enhRole[pick.role].costs;
      const room = pick.max - pick.level;
      // bundle: buy levels until the per-level cost reaches the point where the runner-up wins,
      // capped at one day of income
      const cstar = runner > 0 ? pick.V * ctx.cpd / runner / pick.discF : Infinity;
      let byRunner = 0;
      while (byRunner < room && costs[pick.level + byRunner] <= cstar) byRunner++;
      let byDay = 0;
      while (byDay < room && cumArr[pick.level + byDay + 1] - cumArr[pick.level] <= ctx.cpd / pick.discF) byDay++;
      n = Math.max(1, Math.min(room, byDay, runner > 0 ? Math.max(1, byRunner) : 100));
      cost = pick.kind === "WS" ? (cumArr[pick.level + n] - cumArr[pick.level]) * pick.discF
        : (cumArr[pick.level + n] - cumArr[pick.level]) * pick.discF;
    }
    cum += cost;
    const funded = Math.max(0, (cum - num(P.coins)) / P.cph);
    const L2 = { ...L, [pick.role]: L[pick.role] + n };
    const S2 = stats(ctx, L2);
    const step = { k: k + 1, ...pick, from: pick.level, to: pick.level + n, n, cost, cum, funded };
    step.outcome = components(ctx, S, S2).V;
    step.total = components(ctx, ctx.S0, S2).V;
    step.gain = gainText(ctx, step.outcome);
    if (pick.kind === "LAB") {
      const j = slots.indexOf(Math.min(...slots));
      step.slot = j + 1;
      step.start = Math.max(funded, slots[j], labDone[pick.role] || 0);
      step.done = step.start + pick.hours;
      slots[j] = step.done;
      labDone[pick.role] = step.done;
      step.note = `Start in ${fmtHours(step.start)}, done in ${fmtHours(step.done)}`;
      if (step.start > funded + 0.01) step.note += " (waits for a free lab slot)";
    } else {
      step.note = funded > 0 ? `Save ${fmtCoins(cum - num(P.coins))} more (about ${fmtHours(funded)})` : "Affordable now";
    }
    out.push(step);
    L = L2; S = S2;
  }
  return { steps: out };
}

// ---------------------------------------------------------------- gems
export function labRushGems(hours) {
  const s = hours * 3600;
  const v = s > 31104000 ? 25000 : s > 7776000 ? (17000 / 23328000) * (s - 7776000) + 8000
    : s > 2592000 ? (4450 / 5184000) * (s - 2592000) + 3550 : s > 604800 ? (2550 / 1987200) * (s - 604800) + 1000
      : s > 86400 ? (837 / 518400) * (s - 86400) + 163 : s > 3600 ? (155.5 / 82800) * (s - 3600) + 7.5
        : s > 60 ? (7.375 / 3540) * (s - 60) + 0.125 : s > 1 ? (0.122917 / 59) * (s - 1) + 0.002083 : 0;
  return Math.ceil(v - 1e-9);
}

export function gemPlan(ctx, ev) {
  const { G, P } = ctx;
  const H = ctx.horizon;
  const best = ev.labs.find(r => r.key > 0);
  const rate = Math.max(0, ...ev.labs.filter(r => r.key > 0 && r.hours > 0).map(r => r.V / (r.hours / 24)));
  const slotCosts = G.raw.gems.labSlotCost.value;
  const opts = [];
  const add = o => opts.push({ quantified: true, ...o });
  add({ name: "Next lab slot", gems: ctx.slots >= 5 ? null : slotCosts[ctx.slots],
    value: ctx.slots >= 5 || rate <= 0 ? null : ctx.free > 0 || !ctx.resTime ? 0 : rate * H * H / 2,
    why: ctx.slots >= 5 ? "All 5 slots owned." : ctx.free > 0 ? `You already have ${ctx.free} idle slot(s): fill them before buying more.`
      : ctx.resTime ? `Adds a research stream at your best lab rate (${best?.name || "—"}) for the whole horizon.`
        : "Your research is coin-limited, so an extra slot would sit idle." });
  (P.activeLabs || []).forEach((s, i) => {
    if (!s || !s.lab || !(num(s.hours) > 0)) return;
    const r = ev.labs.find(x => x.id === s.lab);
    const v = num(r?.V) * s.hours / 24 + rate * s.hours / 24 * Math.max(0, H - s.hours / 24);
    add({ name: `Rush slot ${i + 1}: ${G.lab[s.lab]?.name || s.lab}`, gems: labRushGems(s.hours), value: v,
      why: `Finishes ${s.hours.toFixed(1)} h early: its benefit arrives sooner and the slot frees for your next research.` });
  });
  if (best) add({ name: `Start + rush best lab: ${best.name}`, gems: labRushGems(best.hours),
    value: best.V * best.hours / 24 + rate * best.hours / 24 * Math.max(0, H - best.hours / 24),
    why: "Only sensible when a slot is free: instant completion of your top-ranked research." });
  opts.push({ name: "Next card slot", gems: num(P.cardSlotCost) > 0 ? P.cardSlotCost : null, value: null, quantified: false,
    why: "Not quantified: value depends on the card you would equip (see Cards). Enter the in-game price; 22 gem slots cost 58,400 in total." });
  opts.push({ name: "Buy a card", gems: G.raw.gems.cardGems.value, value: null, quantified: false,
    why: "Not quantified: random card (80% common / 17% rare / 3% epic)." });
  opts.push({ name: "Module pull", gems: G.raw.gems.modulePullGems.value, value: null, quantified: false,
    why: "Not quantified: 2.5% epic per pull; pity at 150 pulls (3,000 gems; pity not independently verified)." });
  for (const o of opts) {
    o.afford = o.gems != null && num(P.gems) >= o.gems;
    o.perGem = o.quantified && o.value > 0 && o.gems > 0 ? o.value / o.gems : null;
    o.need = o.gems != null && !o.afford ? o.gems - num(P.gems) : null;
    o.days = o.need != null && num(P.gemsDay) > 0 ? o.need / P.gemsDay : null;
  }
  const q = opts.filter(o => o.perGem);
  const now = q.filter(o => o.afford).sort((a, b) => b.perGem - a.perGem)[0] || null;
  const sv = q.filter(o => !o.afford && o.perGem > (now?.perGem || 0)).sort((a, b) => b.perGem - a.perGem)[0] || null;
  const second = q.filter(o => o !== now).sort((a, b) => b.perGem - a.perGem)[0];
  return { opts, now, save: sv, rate, opportunity: now && second ? now.gems * second.perGem : null };
}

// ---------------------------------------------------------------- ultimate weapons
const UWK = ["chain_lightning", "smart_missiles", "death_wave", "chrono_field", "inner_land_mines", "golden_tower",
  "poison_swamp", "black_hole", "spotlight"];
export const UW_KEYS = UWK;

function uwScenario(G, P, lv, own, base) {
  const labs = P.labs || {}, sh = P.uwShares || {};
  const M = uwValue(G, "golden_tower", 0, lv("golden_tower", 0)) + labEffect(G, "golden_tower_bonus", num(labs.golden_tower_bonus));
  const Dg = uwValue(G, "golden_tower", 1, lv("golden_tower", 1)) + labEffect(G, "golden_tower_duration", num(labs.golden_tower_duration));
  const CDg = uwValue(G, "golden_tower", 2, lv("golden_tower", 2));
  const ug = own("golden_tower") * Math.min(1, Dg / CDg);
  const Db = uwValue(G, "black_hole", 1, lv("black_hole", 1)), CDb = uwValue(G, "black_hole", 2, lv("black_hole", 2));
  const ub = Math.min(1, Db / CDb);
  const B = labEffect(G, "black_hole_coin_bonus", num(labs.black_hole_coin_bonus));
  const sb = num(sh.bh) > 0 && own("black_hole") && base?.ub0 > 0 ? Math.min(1, sh.bh * ub / base.ub0) : 0;
  const Qd = uwValue(G, "death_wave", 1, lv("death_wave", 1)), CDd = uwValue(G, "death_wave", 2, lv("death_wave", 2));
  const W = labEffect(G, "death_wave_coin_bonus", num(labs.death_wave_coin_bonus));
  const sd = num(sh.dw) > 0 && own("death_wave") && base?.dw0 > 0 ? Math.min(1, sh.dw * (Qd / CDd) / base.dw0) : 0;
  const syncB = !!(own("golden_tower") && own("black_hole") && CDg === CDb && Db <= Dg);
  const syncD = !!(own("golden_tower") && own("death_wave") && CDg === CDd);
  const mult = ((1 + ug * (M - 1)) + (syncB ? Math.min(sb, ug) * M * (B - 1) : 0) + (syncD ? Math.min(sd, ug) * M * (W - 1) : 0))
    * (syncB ? 1 : 1 + sb * (B - 1)) * (syncD ? 1 : 1 + sd * (W - 1));
  return { M, Dg, CDg, ug, Db, CDb, ub, B, sb, Qd, CDd, W, sd, syncB, syncD, mult };
}

export function uwCoinState(G, P) {
  const U = P.uw || {};
  const own = k => (U[k]?.owned ? 1 : 0);
  const lv = (k, j) => (U[k]?.owned ? num(U[k].levels?.[j]) : 0);
  const ub0 = own("black_hole") ? Math.min(1, uwValue(G, "black_hole", 1, lv("black_hole", 1)) / uwValue(G, "black_hole", 2, lv("black_hole", 2))) : 0;
  const dw0 = own("death_wave") ? uwValue(G, "death_wave", 1, lv("death_wave", 1)) / uwValue(G, "death_wave", 2, lv("death_wave", 2)) : 0;
  const base = { ub0, dw0, own, lv };
  base.cur = uwScenario(G, P, lv, own, base);
  return base;
}

const ECON_STATS = [["golden_tower", 0], ["golden_tower", 1], ["golden_tower", 2], ["black_hole", 1], ["black_hole", 2],
  ["death_wave", 1], ["death_wave", 2]];

export function uwPlan(ctx) {
  const { G, P } = ctx;
  const U = P.uw || {};
  const base = ctx.uw;
  const econ = ctx.strat === 1 || ctx.strat === 4;
  const owned = UWK.filter(k => U[k]?.owned).length;
  const nextCost = owned >= 9 ? null : G.raw.uwUnlockStones[owned];
  const wsel = [ctx.wdF, ctx.wdT, ctx.wdM, ctx.wdF][ctx.strat - 1];
  const choices = (P.uwChoices || []).filter(Boolean).map(name => {
    const k = UWK.find(x => G.uw[x].name === name);
    const role = G.uw[k].role;
    let gain = null;
    if (["golden_tower", "black_hole", "death_wave"].includes(k) && !U[k]?.owned) {
      const sc = uwScenario(G, P, (kk, j) => (kk === k ? 0 : base.lv(kk, j)), kk => (kk === k ? 1 : base.own(kk)), base);
      gain = Math.log(sc.mult) - Math.log(base.cur.mult);
    }
    const fit = /Economy/.test(role) ? (econ ? "Yes (coins)" : "No")
      : wsel === 1 ? (/Damage/.test(role) ? "Yes (damage-limited)" : "Partly")
        : wsel === 0 ? (/Control/.test(role) ? "Yes (survival-limited)" : "Partly") : "Unknown bottleneck";
    const score = U[k]?.owned ? -1 : (econ && gain > 0 ? 1000 + gain : 0) + (fit.startsWith("Yes") ? 10 : fit === "Partly" ? 5 : 0);
    const why = U[k]?.owned ? "You already own this weapon - check the entry." :
      [econ && gain > 0 ? `Computed: +${((Math.exp(gain) - 1) * 100).toFixed(1)}% coins on average.` : "",
        fit.startsWith("Yes") ? `Matches your ${econ ? "goal" : "bottleneck"}.` : "",
        !(econ && gain > 0) ? `Combat value is a strategy judgment (not computed): ${role}.` : ""].filter(Boolean).join(" ");
    return { key: k, name, role, gain, fit, score, why, cost: nextCost, owned: !!U[k]?.owned };
  }).sort((a, b) => b.score - a.score);
  // stone upgrades
  const ups = [];
  for (const k of UWK) for (let j = 0; j < 3; j++) {
    const s = G.uw[k].stats[j];
    const o = { key: k, j, label: `${G.uw[k].name} · ${s.name}`, owned: !!U[k]?.owned };
    if (o.owned) {
      o.level = num(U[k].levels?.[j]); o.max = uwMax(G, k, j);
      if (o.level < o.max) {
        o.cost = s.levels[o.level + 1][3];
        o.from = s.levels[o.level][1]; o.to = s.levels[o.level + 1][1];
        const isEcon = ECON_STATS.some(([a, b]) => a === k && b === j);
        if (isEcon) {
          const sc = uwScenario(G, P, (kk, jj) => (kk === k && jj === j ? o.level + 1 : base.lv(kk, jj)), base.own, base);
          o.gain = Math.log(sc.mult) - Math.log(base.cur.mult);
          if (s.name === "Cooldown") {
            if (base.cur.syncB && !sc.syncB) o.sync = "⚠ breaks GT/BH sync";
            else if (!base.cur.syncB && sc.syncB) o.sync = "✔ creates GT/BH sync";
            else if (base.cur.syncD && !sc.syncD) o.sync = "⚠ breaks GT/DW sync";
            else if (!base.cur.syncD && sc.syncD) o.sync = "✔ creates GT/DW sync";
          }
          if ((k === "black_hole" && !(num(P.uwShares?.bh) > 0)) || (k === "death_wave" && !(num(P.uwShares?.dw) > 0))) o.needsShare = true;
          o.perStone = econ && o.gain > 1e-9 ? o.gain / o.cost : null;
        }
        o.judgment = /Damage/.test(G.uw[k].role) ? (wsel === 1 ? "relevant - your runs are damage-limited" : "lower priority unless damage limits you")
          : /Control/.test(G.uw[k].role) ? (wsel === 0 ? "relevant - your runs are survival-limited" : "lower priority unless survival limits you") : "economy weapon";
      }
    }
    ups.push(o);
  }
  const ranked = ups.filter(u => u.perStone).sort((a, b) => b.perStone - a.perStone);
  ranked.forEach((u, i) => { u.rank = i + 1; });
  // verdict
  const bestUp = ranked[0], bestCh = choices.find(c => c.score >= 0);
  let verdict;
  if (econ && bestCh?.gain > 0 && bestUp) verdict = (Math.exp(bestCh.gain) - 1) / bestCh.cost > (Math.exp(bestUp.gain) - 1) / bestUp.cost
    ? "BUY the new weapon - it returns more coins per stone than the best upgrade." : "UPGRADE first - the best upgrade returns more coins per stone than the new weapon.";
  else if (econ && bestUp) verdict = "UPGRADE first for coins - none of the offered weapons has a computed coin effect (their combat value is a judgment call).";
  else if (bestCh) verdict = "No computed comparison for this goal - weigh the new weapon's role against your bottleneck (judgment).";
  else verdict = "Enter the weapons the game offers to compare buying with upgrading.";
  // sequential stone track
  const track = [];
  if (econ) {
    const lv = {}; for (const [k, j] of ECON_STATS) lv[`${k}:${j}`] = base.lv(k, j);
    let cum = 0;
    let cur = uwScenario(G, P, (kk, jj) => lv[`${kk}:${jj}`] ?? base.lv(kk, jj), base.own, base);
    for (let step = 0; step < 10; step++) {
      let best = null;
      for (const [k, j] of ECON_STATS) {
        if (!base.own(k)) continue;
        const L = lv[`${k}:${j}`]; if (L >= uwMax(G, k, j)) continue;
        const sc = uwScenario(G, P, (kk, jj) => (kk === k && jj === j ? L + 1 : lv[`${kk}:${jj}`] ?? base.lv(kk, jj)), base.own, base);
        const g = Math.log(sc.mult) - Math.log(cur.mult), cost = G.uw[k].stats[j].levels[L + 1][3];
        if (g > 1e-9 && (!best || g / cost > best.g / best.cost)) best = { k, j, L, g, cost, sc };
      }
      if (!best) break;
      cum += best.cost;
      track.push({ step: step + 1, label: `${G.uw[best.k].name} · ${G.uw[best.k].stats[best.j].name}`, from: best.L, to: best.L + 1,
        cost: best.cost, cum, gain: best.g, when: cum <= num(P.stones) ? "now" : num(P.stonesDay) > 0 ? `${((cum - num(P.stones)) / P.stonesDay).toFixed(1)} days` : `save ${Math.round(cum - num(P.stones))}`,
        cooldown: G.uw[best.k].stats[best.j].name === "Cooldown" });
      lv[`${best.k}:${best.j}`] = best.L + 1; cur = best.sc;
    }
  }
  return { owned, nextCost, choices, ups, ranked, verdict, track, cur: base.cur, econ };
}

// ---------------------------------------------------------------- cards
export function cardEffects(G, P) {
  const fx = {};
  for (const c of G.cards || []) {
    if (!c.model || !(P.cards?.[c.id]?.equipped)) continue;
    const lvl = clamp(num(P.cards[c.id].level, 1), 1, c.values.length);
    const v = c.values[lvl - 1];
    if (c.model === "critChance" || c.model === "defense") fx[c.model] = num(fx[c.model]) + v / 100;
    else fx[c.model] = num(fx[c.model], 1) * v;
  }
  return fx;
}

// Value of each owned card for the goal: equip it alone (on top of the others) vs not.
export function cardPlan(ctx) {
  const { G, P } = ctx;
  const owned = (G.cards || []).filter(c => P.cards?.[c.id]?.unlocked);
  const slots = num(P.cardSlots);
  const value = c => {
    if (!c.model) return null;
    const with_ = { ...P, cards: { ...P.cards, [c.id]: { ...P.cards[c.id], equipped: true } } };
    const without = { ...P, cards: { ...P.cards, [c.id]: { ...P.cards[c.id], equipped: false } } };
    const a = makeContext(G, without, ctx.strategy), b = makeContext(G, with_, ctx.strategy);
    // compare outcome of the same levels under the two modifier sets, measured from "without"
    const Sb = stats({ ...a, ext: b.ext }, a.L0);
    return components(a, a.S0, Sb).V;
  };
  const rows = owned.map(c => {
    const lvl = num(P.cards[c.id].level, 1);
    const v = value(c);
    return { id: c.id, name: c.name, rarity: c.rarity, level: lvl, equipped: !!P.cards[c.id].equipped,
      effect: c.values[clamp(lvl, 1, c.values.length) - 1], desc: c.desc, modeled: !!c.model, V: v,
      gain: v != null ? gainText(ctx, v) : null };
  });
  const modeledRanked = rows.filter(r => r.modeled && r.V > 1e-12).sort((a, b) => b.V - a.V);
  const recommend = new Set(modeledRanked.slice(0, slots).map(r => r.id));
  for (const r of rows) r.recommended = recommend.has(r.id);
  const freeAfterModeled = Math.max(0, slots - recommend.size);
  return { rows: rows.sort((a, b) => (b.V ?? -1) - (a.V ?? -1)), slots, freeAfterModeled,
    swaps: rows.filter(r => r.equipped && r.modeled && !r.recommended && modeledRanked.length > slots) };
}

// ---------------------------------------------------------------- formatting
export function fmtCoins(x) {
  if (x == null || !isFinite(x)) return "—";
  if (x < 1000) return String(Math.round(x));
  const e = Math.min(11, Math.floor(Math.log10(x) / 3));
  return (x / 10 ** (3 * e)).toFixed(2) + "KMBTqQsSOND"[e - 1];
}
export function fmtHours(h) {
  if (h == null || !isFinite(h)) return "—";
  if (h < 1 / 60) return "<1m";
  if (h < 1) return `${Math.round(h * 60)}m`;
  if (h < 48) return `${h.toFixed(1)}h`;
  return `${(h / 24).toFixed(1)}d`;
}
