// Cross-validates the JavaScript engine against the independently built Excel engine
// (values computed by a full LibreOffice recalculation of the legacy workbook, 9 scenarios).
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { makeGame, makeContext, evaluateAll, roadmap, labRushGems, fmtCoins } from "../js/engine.js";
import { profileFromRows } from "../js/parse.js";

const G = makeGame(JSON.parse(readFileSync(new URL("../data/game.json", import.meta.url))));
const X = JSON.parse(readFileSync(new URL("./fixtures/excel_scenarios.json", import.meta.url)));
const close = (a, b, rel = 1e-6, abs = 1e-9) => Math.abs(a - b) <= Math.max(abs, rel * Math.max(Math.abs(a), Math.abs(b)));
const kindOf = { Workshop: "WS", Enhancement: "EN", Lab: "LAB" };

for (const [name, sc] of Object.entries(X)) {
  test(`matches Excel engine: ${name}`, () => {
    const P = profileFromRows(G, sc.import);
    const ctx = makeContext(G, P, sc.strategy, { useCards: false });
    const ev = evaluateAll(ctx);
    const js = new Map([...ev.workshop, ...ev.labs].map(r => [`${r.kind}:${r.id}`, r]));
    let compared = 0;
    for (const [k, xl] of Object.entries(sc.candidates)) {
      const [type, id] = [k.slice(0, k.indexOf(":")), k.slice(k.indexOf(":") + 1)];
      const r = js.get(`${kindOf[type]}:${id}`);
      assert.ok(r, `missing ${k}`);
      if (typeof xl.Cost === "number") assert.ok(close(r.cost, xl.Cost, 1e-9, 0.5), `${name} ${k} cost js=${r.cost} xl=${xl.Cost}`);
      if (typeof xl.Hours === "number") assert.ok(close(r.hours, xl.Hours), `${name} ${k} hours js=${r.hours} xl=${xl.Hours}`);
      if (typeof xl.V === "number") {
        assert.ok(close(r.V, xl.V, 1e-6, 1e-12), `${name} ${k} V js=${r.V} xl=${xl.V}`);
        for (const [a, b] of [["econ", "cEcon"], ["dmg", "cDmg"], ["surv", "cSurv"], ["pp", "cPP"], ["res", "cRes"]])
          assert.ok(close(r[a], xl[b], 1e-6, 1e-12), `${name} ${k} ${a} js=${r[a]} xl=${xl[b]}`);
        compared++;
      }
      if (typeof xl.Rank === "number" && xl.Rank <= 10 && r.key > 0) assert.equal(r.rank, xl.Rank, `${name} ${k} rank`);
    }
    assert.ok(compared >= 10, `only ${compared} valued candidates compared`);
    const rm = roadmap(ctx).steps;
    assert.equal(rm.length, sc.roadmap.length, `${name} roadmap length`);
    sc.roadmap.forEach((x, i) => {
      assert.equal(rm[i].role, x["Pick role"], `${name} step ${i + 1} pick`);
      assert.equal(rm[i].to, x.To, `${name} step ${i + 1} to-level`);
      assert.ok(close(rm[i].cost, x.Cost, 1e-6, 1), `${name} step ${i + 1} cost js=${rm[i].cost} xl=${x.Cost}`);
    });
  });
}

test("lab rush price anchors (SDK computeLabGems)", () => {
  assert.equal(labRushGems(24), 163);
  assert.equal(labRushGems(168), 1000);
});

test("Tower number format", () => {
  assert.equal(fmtCoins(320e9), "320.00B");
  assert.equal(fmtCoins(999), "999");
  assert.equal(fmtCoins(1.5e15), "1.50q");
});
