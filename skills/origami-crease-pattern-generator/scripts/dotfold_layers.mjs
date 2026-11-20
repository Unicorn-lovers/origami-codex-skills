// Match a visible side of an actual Flat-Folder layer state to the pixel mask.
import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";

const tolerance = 1e-7;
const area = (ring) => Math.abs(ring.reduce((sum, [x, y], i) => {
  const [u, v] = ring[(i + 1) % ring.length];
  return sum + x * v - y * u;
}, 0)) / 2;

function clip(ring, axis, bound, sign) {
  const result = [];
  for (let i = 0; i < ring.length; i++) {
    const p = ring[i], q = ring[(i + 1) % ring.length];
    const pin = sign * (p[axis] - bound) >= 0, qin = sign * (q[axis] - bound) >= 0;
    if (pin) result.push(p);
    if (pin !== qin) {
      const t = (bound - p[axis]) / (q[axis] - p[axis]);
      result.push(p.map((v, j) => v + t * (q[j] - v)));
    }
  }
  return result;
}

function intersectionArea(ring, [x, y]) {
  let clipped = clip(ring, 0, x, 1);
  clipped = clip(clipped, 0, x + 1, -1);
  clipped = clip(clipped, 1, y, 1);
  return area(clip(clipped, 1, y + 1, -1));
}

function orient([x, y], back, quarterTurns) {
  if (back) x = -x;
  y = -y; // Cartesian FOLD to top-down image coordinates
  for (let i = 0; i < quarterTurns; i++) [x, y] = [-y, x];
  return [x, y];
}

export function matchView(rings, foreground, pixels, back) {
  const ink = rings.filter((_, i) => foreground[i]);
  const inkArea = ink.reduce((n, ring) => n + area(ring), 0);
  if (!pixels.length || Math.abs(inkArea - pixels.length) > tolerance) return null;
  const x0 = Math.min(...pixels.map(p => p[0])), y0 = Math.min(...pixels.map(p => p[1]));
  for (let turns = 0; turns < 4; turns++) {
    const points = ink.flat().map(p => orient(p, back, turns));
    const dx = x0 - Math.min(...points.map(p => p[0])), dy = y0 - Math.min(...points.map(p => p[1]));
    const placed = rings.map(ring => ring.map(p => {
      const [x, y] = orient(p, back, turns);
      return [x + dx, y + dy];
    }));
    let overlap = 0;
    for (let i = 0; i < placed.length; i++) {
      if (foreground[i]) for (const p of pixels) overlap += intersectionArea(placed[i], p);
    }
    // Disjoint layer cells. Includes ink outside the 8x8 frame and partial pixels.
    const difference = Math.max(0, inkArea + pixels.length - 2 * overlap);
    if (difference < tolerance) return {placed, quarterTurns: turns, translation: [dx, dy], difference};
  }
  return null;
}

function assignments(fold, orders) {
  const directed = new Set(orders.map(([a, b]) => a + "," + b));
  return fold.EF.map(faces => {
    if (faces.length === 1) return "B";
    const [a, b] = [...faces].sort((x, y) => x - y);
    if (faces.length !== 2 || fold.Ff[a] === fold.Ff[b] ||
        !directed.has(a + "," + b) && !directed.has(b + "," + a)) {
      throw new Error("missing order for a folded hinge");
    }
    return directed.has(b + "," + a) !== fold.Ff[a] ? "M" : "V";
  });
}

async function solve(source, candidate, target, limit) {
  globalThis.onmessage = null;
  let reply;
  globalThis.postMessage = message => { if (message.type === "end") reply = message; };
  await import(pathToFileURL(path.join(source, "src", "compute.js")));
  function request(type, ...args) {
    reply = null;
    globalThis.onmessage({data: {type, args}});
    if (!reply) throw new Error("Flat-Folder did not complete " + type);
    return reply.arg;
  }
  request("setup");
  // Upstream merges collinear unit segments in its edge importer. Supplying
  // the unsubdivided faces alongside those segments bypasses that step.
  const {vertices_coords, edges_vertices} = candidate;
  const edges_assignment = candidate.edges_assignment.map(a => a === "M" ? "V" : a === "V" ? "M" : a);
  const f = request("doc_type_side_2_fold", JSON.stringify({vertices_coords, edges_vertices, edges_assignment}), "fold", true);
  const c = request("get_cell");
  request("build_variables");
  request("build_constraints");
  const [pre] = request("presolve");
  if (pre !== "ok") return {status: "no_layer_state", stage: "presolve"};
  const [status, counts] = request("solve", limit);
  if (status !== "success") return {status: "no_layer_state", stage: "solve"};
  const rings = c.CP.map(face => face.map(v => c.P[v]));
  const pix = [...target.bits].flatMap((b, i) => b === "1" ? [[i % 8, Math.floor(i / 8)]] : []);
  const transparent = target.background === "transparent";
  const selection = counts.map(() => 0), tried = new Set();
  let states = 0, remaining = true;
  while (remaining && states < limit) {
    states++;
    const [stacks, orders] = request("Gi_2_CD_FO", selection);
    for (const back of [false, true]) {
      // Gi_2_CD_FO sorts above-to-below in Cartesian FOLD coordinates.
      const top = stacks.map(stack => back ? stack.at(-1) : stack[0]);
      for (const inkOnBackOfSheet of [false, true]) {
        const ink = top.map(face => face !== undefined && (f.Ff[face] !== back) === inkOnBackOfSheet);
        if (transparent && ink.some((v, i) => !v && stacks[i].length)) continue;
        const key = Number(back) + ":" + ink.map(Number).join("");
        if (tried.has(key)) continue;
        tried.add(key);
        const view = matchView(rings, ink, pix, back);
        if (!view) continue;
        const graph = {file_spec: 1.1, file_creator: "dotFoldSolver and Flat-Folder",
          vertices_coords: f.V, edges_vertices: f.EV, edges_assignment: assignments(f, orders), faces_vertices: f.FV};
        return {status: "exact", states, side: back ? "back" : "front", inkOnBackOfSheet,
          pixelDifferenceArea: view.difference, quarterTurns: view.quarterTurns, translation: view.translation,
          graph, folded: {...graph, frame_classes: ["foldedForm"], vertices_coords: f.Vf, faceOrders: orders},
          cells: view.placed.flatMap((polygon, i) => stacks[i].length ? [{polygon, ink: ink[i], stack: stacks[i]}] : [])};
      }
    }
    remaining = false;
    for (let i = 0; i < counts.length; i++) {
      if (++selection[i] < counts[i]) { remaining = true; break; }
      selection[i] = 0;
    }
  }
  return {status: "no_visible_match", states, stateLimit: limit,
    searchMayBeTruncated: remaining || counts.some(count => count >= limit)};
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  const [source, input, target, output, limit] = process.argv.slice(2);
  const read = file => JSON.parse(fs.readFileSync(file, "utf8"));
  fs.writeFileSync(output, JSON.stringify(await solve(source, read(input), read(target), Number(limit))));
}
