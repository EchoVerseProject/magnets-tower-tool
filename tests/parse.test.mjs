// The export parser must read both key casings and agree with the legacy Import rows.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { makeGame } from "../js/engine.js";
import { profileFromExport, profileFromRows } from "../js/parse.js";

const G = makeGame(JSON.parse(readFileSync(new URL("../data/game.json", import.meta.url))));
const rows = JSON.parse(readFileSync(new URL("../data/samples/mid.json", import.meta.url)));
const camel = JSON.parse(readFileSync(new URL("./fixtures/hypothetical_export_camelcase.json", import.meta.url)));
const pascal = Object.fromEntries(Object.entries(camel).map(([k, v]) => [k[0].toUpperCase() + k.slice(1), v]));

for (const [label, json] of [["camelCase", camel], ["PascalCase", pascal]]) {
  test(`parses ${label} exports like the legacy importer`, () => {
    const a = profileFromExport(G, json), b = profileFromRows(G, rows);
    for (const id of Object.keys(b.ws)) assert.equal(a.ws[id], b.ws[id], `ws ${id}`);
    for (const id of Object.keys(b.wsUnlocked)) assert.equal(a.wsUnlocked[id], b.wsUnlocked[id], `unlock ${id}`);
    for (const [id, v] of Object.entries(b.labs)) {
      const l = G.lab[id];
      if (l.saveIndex != null && l.saveIndex < 250) assert.equal(a.labs[id], v, `lab ${id}`);
    }
    for (const [t, w] of Object.entries(b.tierWave)) assert.equal(a.tierWave[t], w, `tier ${t}`);
    for (const [k, u] of Object.entries(b.uw)) { assert.equal(a.uw[k].owned, u.owned, `uw ${k}`); assert.deepEqual(a.uw[k].levels, u.levels); }
    assert.deepEqual(a.activeLabs.map(s => s.lab), b.activeLabs.map(s => s.lab));
  });
}

test("rejects files that are not exports", () => {
  assert.throws(() => profileFromExport(G, { hello: 1 }), /No Workshop or Lab data/);
});
