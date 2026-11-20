import assert from "node:assert/strict";
import {execFileSync} from "node:child_process";
import {mkdtempSync, readFileSync, rmSync, writeFileSync} from "node:fs";
import {tmpdir} from "node:os";
import path from "node:path";
import test from "node:test";
import {fileURLToPath} from "node:url";
import {matchView} from "../scripts/dotfold_layers.mjs";

const leftFoot = [[0, 0], [1, 0], [2, 0], [0, 1]];
const rightFoot = [[0, 0], [1, 0], [2, 0], [2, 1]];
// The long row is at the top when the +Z side is viewed on a screen.
const face = [[0, 0], [1, 0], [1, 1], [3, 1], [3, 2], [0, 2]];

test("a fixed side can rotate and translate, but cannot mirror the ink", () => {
  const front = matchView([face], [true], leftFoot, false);
  assert.equal(front.quarterTurns, 0);
  assert.equal(front.difference, 0);
  assert.equal(matchView([face], [true], rightFoot, false), null);
  assert.equal(matchView([face], [true], leftFoot, true), null);
  assert.equal(matchView([face], [true], rightFoot, true).difference, 0);
  const turned = leftFoot.map(([x, y]) => [4 - y, 3 + x]);
  assert.equal(matchView([face], [true], turned, false).quarterTurns, 1);
});

test("a shear covering the pixel center has unit area but covers the wrong region", () => {
  const sheared = [[0, 0], [1, 0], [1.25, 1], [0.25, 1]];
  assert.equal(matchView([sheared], [true], [[0, 0]], false), null);
});

test("two paper cells can partition one fully inked pixel", () => {
  const triangles = [[[0, 0], [1, 0], [1, 1]], [[1, 1], [0, 1], [0, 0]]];
  assert.equal(matchView(triangles, [true, true], [[6, 4]], false).difference, 0);
  assert.equal(matchView(triangles, [true, false], [[6, 4]], false), null);
});

const flatFolder = process.env.FLAT_FOLDER_ROOT;
const script = fileURLToPath(new URL("../scripts/dotfold_layers.mjs", import.meta.url));

// One square tab hinged to the bottom of a five-square sheet. With its
// main face held front-up, a valley brings the tab on top of the lower
// middle cell, leaving a dark left-foot L. A mountain hides the tab from
// above; the L is then only visible mirrored on the back.
function tabFold(assignment) {
  return {
    vertices_coords: [[0, 0], [1, 0], [2, 0], [2, 1], [3, 1], [3, 2], [0, 2], [1, -1], [2, -1]],
    edges_vertices: [[0, 1], [1, 2], [2, 3], [3, 4], [4, 5], [5, 6], [6, 0], [1, 7], [7, 8], [8, 2]],
    edges_assignment: ["B", assignment, "B", "B", "B", "B", "B", "B", "B", "B"],
    faces_vertices: [[0, 1, 2, 3, 4, 5, 6], [1, 7, 8, 2]],
  };
}

function solve(cwd, fold, pixels, background = "#ffffff", size = 8) {
  const file = path.join(cwd, "source.fold");
  const target = path.join(cwd, "target.json");
  const result = path.join(cwd, "result.json");
  const grid = Array(size * size).fill("0");
  for (const [x, y] of pixels) grid[size * y + x] = "1";
  writeFileSync(file, JSON.stringify(fold));
  writeFileSync(target, JSON.stringify({bits: grid.join(""), background}));
  execFileSync(process.execPath, [script, flatFolder || cwd, file, target, result, "4"]);
  return JSON.parse(readFileSync(result, "utf8"));
}

function signedArea(fold, face) {
  const ring = fold.faces_vertices[face].map(i => fold.vertices_coords[i]);
  return ring.reduce((sum, [x, y], i) => {
    const [u, v] = ring[(i + 1) % ring.length];
    return sum + x * v - y * u;
  }, 0) / 2;
}

test("mountain and valley expose opposite handed images and round-trip as assigned",
  {skip: flatFolder ? false : "Set FLAT_FOLDER_ROOT to a Flat-Folder checkout"}, t => {
    const cwd = mkdtempSync(path.join(tmpdir(), "dotfold-tab-"));
    t.after(() => rmSync(cwd, {recursive: true, force: true}));
    for (const [mv, side, visible, other] of [
      ["V", "front", leftFoot, rightFoot],
      ["M", "back", rightFoot, leftFoot],
    ]) {
      const result = solve(cwd, tabFold(mv), visible);
      assert.equal(result.status, "exact", mv);
      assert.equal(result.side, side);
      assert.equal(result.inkOnBackOfSheet, side === "back");
      assert.equal(result.pixelDifferenceArea, 0);
      assert.deepEqual(result.graph.edges_assignment.filter(a => a !== "B"), [mv]);
      // In FOLD's [a,b,s], the comparison direction is the current normal
      // of b. Decode this independently of Flat-Folder's cell-stack arrays.
      assert.equal(result.folded.faceOrders.length, 1);
      const [[a, b, s]] = result.folded.faceOrders;
      const frontOfB = Math.sign(signedArea(result.folded, b));
      const faceAbove = s * frontOfB > 0 ? a : b;
      const tab = Math.abs(signedArea(result.graph, a)) === 1 ? a : b;
      assert.equal(faceAbove === tab, mv === "V");
      assert.equal(solve(cwd, result.graph, visible).status, "exact");
      assert.equal(solve(cwd, result.graph, other).status, "no_visible_match");
      // Exercise the lower-right quadrant of a 16-cell target with real
      // overlapping faces, including its row stride and visual handedness.
      const shifted = visible.map(([x, y]) => [x + 13, y + 14]);
      const larger = solve(cwd, result.graph, shifted, "#ffffff", 16);
      assert.equal(larger.status, "exact");
      assert.equal(larger.side, side);
      assert.equal(larger.pixelDifferenceArea, 0);
      // The tab occupies one of the background cells, so this same image
      // cannot be the silhouette of paper against a transparent background.
      assert.equal(solve(cwd, result.graph, visible, "transparent").status, "no_visible_match");
    }
  });

test("the uncreased 16×16 sheet has precisely one layer order", t => {
  const cwd = mkdtempSync(path.join(tmpdir(), "dotfold-single-"));
  t.after(() => rmSync(cwd, {recursive: true, force: true}));
  const sheet = {
    vertices_coords: [[0, 0], [16, 0], [16, 16], [0, 16]],
    faces_vertices: [[0, 1, 2, 3]],
    edges_vertices: [[0, 1], [1, 2], [2, 3], [3, 0]],
    edges_assignment: Array(4).fill("B"),
  };
  const mask = Array.from({length: 256}, (_, i) => [i % 16, Math.floor(i / 16)]);
  const result = solve(cwd, sheet, mask, "transparent", 16);
  assert.equal(result.status, "exact");
  assert.equal(result.layerMethod, "single_face");
  assert.equal(result.pixelDifferenceArea, 0);
  assert.deepEqual(result.cells[0].stack, [0]);
  assert.deepEqual(result.folded.faceOrders, []);
  assert.equal(solve(cwd, sheet, mask.slice(1), "transparent", 16).status, "no_visible_match");
});
