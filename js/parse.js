// Parse The Tower's official External Tools export (tool_export.json) into a profile.
// Handles both key casings (older docs: camelCase; current exports: PascalCase).

const num = (x, d = null) => (typeof x === "number" && isFinite(x) ? x : typeof x === "boolean" ? (x ? 1 : 0) : d);

function getter(root) {
  const lower = new Map(Object.keys(root).map(k => [k.toLowerCase(), k]));
  return key => {
    if (key in root) return root[key];
    const k = lower.get(key.toLowerCase());
    return k === undefined ? undefined : root[k];
  };
}
const asArr = v => (Array.isArray(v) ? v : v && Array.isArray(v._items) ? v._items : []);

export const KILLED_BY = ["Basic", "Fast", "Tank", "Boss", "Ranged", "Protector", "Vampire", "Scatter", "Scatter", "Ray",
  "Saboteur", "Commander", "Overcharge"];

export function profileFromExport(G, json) {
  if (!json || typeof json !== "object") throw new Error("This file is not a tool_export.json");
  const get = getter(json);
  const arr = k => asArr(get(k));
  if (!arr("researchLevel").length && !arr("upgradeWorkshopLevel").length)
    throw new Error("No Workshop or Lab data found. Use the official External Tools export (tool_export.json).");
  const P = { source: "export", exportedAt: get("ExportedAt") || null, userName: get("UserName") || null,
    ws: {}, wsUnlocked: {}, enh: {}, enhUnlocked: {}, labs: {}, tierWave: {}, activeLabs: [], uw: {}, cards: {},
    warnings: [] };
  // workshop
  const cats = { Attack: ["upgradeWorkshopLevel", "presetUpgradeWorkshopLevel", "upgradeTierUnlocked"],
    Defense: ["upgradeWorkshopDefenseLevel", "presetUpgradeWorkshopDefenseLevel", "upgradeDefenseTierUnlocked"],
    Utility: ["upgradeWorkshopUtilityLevel", "presetUpgradeWorkshopUtilityLevel", "upgradeUtilityTierUnlocked"] };
  const preset = num(get("currentWorkshopPreset"), 0);
  for (const [cat, [k, pk, uk]] of Object.entries(cats)) {
    const items = G.raw.workshop.filter(w => w.category === cat).sort((a, b) => a.saveIndex - b.saveIndex);
    const n = items.length;
    let lv = arr(k).slice(0, n).map(x => num(x, 0));
    if (!lv.some(x => x > 0)) {
      const flat = arr(pk).map(x => num(x, 0)).slice(preset * n, preset * n + n);
      if (flat.some(x => x > 0)) lv = flat;
    }
    const unl = arr(uk);
    for (const w of items) {
      if (w.saveIndex < lv.length) P.ws[w.id] = lv[w.saveIndex];
      if (w.unlockGroup !== "Base") {
        const g = Number(w.unlockGroup.split("G")[1]);
        if (g < unl.length) P.wsUnlocked[w.id] = unl[g] === true || unl[g] === 1;
      }
    }
  }
  // enhancements
  const ek = { Attack: "enhancementLevel", Defense: "enhancementDefenseLevel", Utility: "enhancementUtilityLevel" };
  for (const e of G.raw.enhancements) {
    const a = arr(ek[e.category]);
    if (e.saveIndex < a.length) P.enh[e.id] = num(a[e.saveIndex], 0);
  }
  // labs
  const rl = arr("researchLevel");
  const byIdx = new Map(G.raw.labs.filter(l => l.saveIndex != null).map(l => [l.saveIndex, l]));
  rl.forEach((v, i) => { const l = byIdx.get(i); if (l) P.labs[l.id] = num(v, 0); });
  const ints = arr("labResearchInt"), act = arr("labActiveBool"), done = arr("ResearchCompleteDate");
  const at = Date.parse(get("ExportedAt") || "");
  ints.forEach((ri, s) => {
    if (act[s] !== true) return;
    const l = byIdx.get(num(ri, -1));
    if (!l) return;
    let hours = null;
    const d = Date.parse(done[num(ri)] || "");
    if (isFinite(d) && isFinite(at)) hours = Math.max(0, Math.round((d - at) / 36e5 * 10) / 10);
    P.activeLabs.push({ lab: l.id, hours });
  });
  P.slots = num(get("labsUnlocked"));
  P.busy = P.activeLabs.length;
  // balances & player
  P.coins = num(get("Coins")); P.gems = num(get("Gems")); P.stones = num(get("Stones"));
  const tw = arr("highestWaveThisTier");
  tw.forEach((w, t) => { if (t >= 1 && num(w, 0) > 0) P.tierWave[t] = w; });
  const fk = num(get("TotalCoinsEarnedFromKills")), fw = num(get("TotalCoinsEarnedFromWaves"));
  if (fk != null && fw != null && fk + fw > 0) P.killShare = Math.round(fk / (fk + fw) * 1e4) / 1e4;
  P.league = num(get("LeagueID"));
  // battle history
  P.runs = asArr(get("battleHistory")).filter(r => r && typeof r === "object").map(r => {
    const g = getter(r);
    return { date: g("BattleDate"), tier: num(g("Tier")), wave: num(g("Wave")), tour: g("IsTournament") === true,
      realTime: num(g("RealTime"), 0), gameTime: num(g("GameTime"), 0), coins: num(g("CoinsEarned"), 0),
      cells: num(g("CellsEarned"), 0), killedBy: num(g("KilledBy")), damageTaken: num(g("DamageTaken"), 0),
      damageDealt: num(g("DamageDealt"), 0), regen: num(g("TowerHealthRegen"), 0) };
  }).sort((a, b) => String(a.date).localeCompare(String(b.date)));
  const farm = P.runs.filter(r => !r.tour && r.coins > 0 && r.realTime > 0);
  if (farm.length) {
    const recent = farm.slice(-8);
    const counts = {};
    recent.forEach(r => { counts[r.tier] = (counts[r.tier] || 0) + 1; });
    const tier = Number(Object.entries(counts).sort((a, b) => b[1] - a[1] || 0)[0][0]);
    const sel = recent.filter(r => r.tier === tier).slice(-5);
    P.cph = Math.round(sel.reduce((s, r) => s + r.coins, 0) / sel.reduce((s, r) => s + r.realTime, 0) * 3600);
    P.farmTier = tier;
    const waves = sel.map(r => r.wave).sort((a, b) => a - b);
    P.farmWave = waves[Math.floor(waves.length / 2)];
    P.derived = { cphRuns: sel.length, cphHours: sel.reduce((s, r) => s + r.realTime, 0) / 3600 };
  } else {
    P.farmTier = num(get("currentTier"));
  }
  const tours = P.runs.filter(r => r.tour && r.wave);
  if (tours.length) P.tourWave = Math.max(...tours.slice(-3).map(r => r.wave));
  // ultimate weapons
  const uu = arr("ultimateWeaponUnlocked"), ul = arr("ultimateWeaponLevel");
  for (const [k, u] of Object.entries(G.uw)) {
    const i = u.exportIndex;
    P.uw[k] = { owned: uu[i] === true || uu[i] === 1, levels: [0, 1, 2].map(j => num(ul[i * 3 + j], 0)) };
  }
  // cards
  const cl = arr("cardLevel"), cu = arr("cardUnlocked"), ca = arr("cardActive"), cc = arr("cardCount");
  for (const c of G.cards || []) {
    const i = c.saveIndex;
    if (i == null || i >= cl.length) continue;
    P.cards[c.id] = { level: num(cl[i], 1), unlocked: cu[i] === true, equipped: ca[i] === true, copies: num(cc[i], 0) };
  }
  P.cardSlots = num(get("slotsUnlocked"));
  // modules (shown for judgment)
  P.modules = { inventory: asArr(get("ModuleInventory")).length, equipped: asArr(get("ModuleEquipped")).filter(Boolean).length,
    shards: ["ModuleCannonShards", "ModuleArmorShards", "ModuleGeneratorShards", "ModuleCoreShards"].map(k => num(get(k), 0)),
    pity: num(get("ModulePity")) };
  P.lifetime = { coins: num(get("TotalCoinsEarned")), enemies: num(get("TotalEnemiesDestroyed")),
    waves: num(get("TotalWavesCompleted")), started: get("GameStartedDate") || null };
  return P;
}

// Legacy Import-sheet rows (key, value) from the Excel tool / sample CSVs.
export function profileFromRows(G, rows) {
  const P = { ws: {}, wsUnlocked: {}, enh: {}, labs: {}, tierWave: {}, activeLabs: [], uw: {}, cards: {}, uwShares: {} };
  const byIdx = {}; for (const [k, u] of Object.entries(G.uw)) byIdx[u.exportIndex] = k;
  const shareKeys = { pGTu: "gtu", pGTB: "gtb", pBHs: "bh", pDWs: "dw", pSLs: "sl" };
  for (const [key, raw] of rows) {
    const v = raw === "" || raw == null ? null : isNaN(Number(raw)) ? raw : Number(raw);
    const [a, b, c] = key.split("|");
    if (a === "WS") P.ws[b] = v;
    else if (a === "WSU") P.wsUnlocked[b] = v === 1;
    else if (a === "EN") P.enh[b] = v;
    else if (a === "LAB") P.labs[b] = v;
    else if (a === "TW") P.tierWave[b] = v;
    else if (a === "SLOT") { const s = Number(b) - 1; P.activeLabs[s] = P.activeLabs[s] || {}; P.activeLabs[s][c === "lab" ? "lab" : "hours"] = v; }
    else if (a === "UWU") { const k = byIdx[b]; P.uw[k] = P.uw[k] || { levels: [0, 0, 0] }; P.uw[k].owned = v === 1; }
    else if (a === "UWL") { const k = byIdx[Math.floor(b / 3)]; P.uw[k] = P.uw[k] || { levels: [0, 0, 0] }; P.uw[k].levels[b % 3] = v; }
    else if (a === "P") {
      if (shareKeys[b]) P.uwShares[shareKeys[b]] = v;
      else if (b.startsWith("pUWChoice")) (P.uwChoices = P.uwChoices || [])[Number(b.slice(9)) - 1] = v;
      else P[b[1].toLowerCase() + b.slice(2)] = v;
    } else if (a === "META") P.label = v;
  }
  P.activeLabs = P.activeLabs.filter(Boolean);
  P.cph = P.cPH; delete P.cPH;
  return P;
}
