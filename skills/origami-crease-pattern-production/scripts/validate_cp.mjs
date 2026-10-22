#!/usr/bin/env node

import { randomBytes } from "node:crypto";
import { spawn, spawnSync } from "node:child_process";
import { closeSync, existsSync, openSync, readdirSync } from "node:fs";
import { mkdir, readFile, rm, stat, unlink, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";

function usage(message) {
  if (message) console.error(`error: ${message}`);
  console.error("usage: validate_cp.mjs INPUT.cp [--out-dir DIR] [--jar ORIEDITA.jar] [--java COMMAND] [--force]");
  process.exit(2);
}

function parseArgs(argv) {
  const options = { input: null, outDir: null, jar: null, java: process.env.ORIEDITA_JAVA ?? "java", force: false };
  for (let index = 0; index < argv.length; index += 1) {
    const item = argv[index];
    if (item === "--force") options.force = true;
    else if (["--out-dir", "--jar", "--java"].includes(item)) {
      const value = argv[index + 1];
      if (!value) usage(`${item} requires a value`);
      options[item.slice(2).replace(/-([a-z])/g, (_, letter) => letter.toUpperCase())] = value;
      index += 1;
    } else if (item.startsWith("-")) usage(`unknown option: ${item}`);
    else if (options.input) usage("only one input file is accepted");
    else options.input = item;
  }
  if (!options.input) usage("an input .cp file is required");
  return options;
}

function jarsIn(targetDirectory) {
  try {
    return readdirSync(targetDirectory)
      .filter((name) => /^oriedita-.+\.jar$/.test(name) && !name.startsWith("original-"))
      .sort()
      .reverse()
      .map((name) => path.join(targetDirectory, name));
  } catch {
    return [];
  }
}

function findJar(explicit) {
  const projectTargets = [
    path.join(os.homedir(), "Documents/oriedita/oriedita/target"),
    path.join(os.homedir(), "Library/Mobile Documents/com~apple~CloudDocs/Documents/oriedita/oriedita/target"),
  ];
  const candidates = [
    explicit,
    process.env.ORIEDITA_JAR,
    ...projectTargets.flatMap(jarsIn),
  ].filter(Boolean).map((candidate) => path.resolve(candidate));
  return candidates.find((candidate) => existsSync(candidate));
}

function inspectCp(source) {
  const counts = { edge: 0, mountain: 0, valley: 0 };
  const lines = source.split(/\r?\n/).filter((line) => line.trim() && !line.trim().startsWith("#"));
  lines.forEach((line, index) => {
    const fields = line.trim().split(/\s+/);
    if (fields.length !== 5) throw new Error(`invalid .cp row ${index + 1}: expected 5 fields`);
    const code = Number(fields[0]);
    const coordinates = fields.slice(1).map(Number);
    if (![1, 2, 3].includes(code) || coordinates.some((value) => !Number.isFinite(value))) {
      throw new Error(`invalid .cp row ${index + 1}: unsupported code or coordinate`);
    }
    if (Math.hypot(coordinates[0] - coordinates[2], coordinates[1] - coordinates[3]) <= 1e-9) {
      throw new Error(`invalid .cp row ${index + 1}: zero-length segment`);
    }
    counts[code === 1 ? "edge" : code === 2 ? "mountain" : "valley"] += 1;
  });
  if (!lines.length) throw new Error("the .cp file contains no segments");
  return { lineCount: lines.length, assignments: counts };
}

async function renderSvgWithSips(svgPath, pngPath) {
  const temporarySvg = `${svgPath}.white-background.svg`;
  try {
    const source = await readFile(svgPath, "utf8");
    const withBackground = source.replace(
      /(<svg\b[^>]*>)/,
      '$1\n<rect x="-100000" y="-100000" width="200000" height="200000" fill="white"/>',
    );
    if (withBackground === source) return false;
    await writeFile(temporarySvg, withBackground);
    const rendered = spawnSync("sips", ["-s", "format", "png", temporarySvg, "--out", pngPath], {
      encoding: "utf8",
      stdio: "pipe",
    });
    return rendered.status === 0 && existsSync(pngPath);
  } catch {
    return false;
  } finally {
    await unlink(temporarySvg).catch(() => {});
  }
}

function sleep(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

async function readConnection(connectionFile) {
  try {
    const value = JSON.parse(await readFile(connectionFile, "utf8"));
    if (typeof value.url === "string" && typeof value.token === "string") return value;
  } catch {
    // A missing or partially-written connection file is normal while Oriedita starts.
  }
  return null;
}

async function request(connection, endpoint, options = {}) {
  const response = await fetch(`${connection.url}${endpoint}`, {
    ...options,
    headers: {
      Authorization: `Bearer ${connection.token}`,
      "Content-Type": "application/json",
      ...(options.headers ?? {}),
    },
  });
  const payload = await response.json().catch(() => null);
  if (!response.ok || !payload?.ok) {
    throw new Error(payload?.error?.message ?? `${response.status} ${response.statusText}`);
  }
  return payload.result;
}

async function healthy(connection) {
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 750);
    try {
      const status = await request(connection, "/health", { signal: controller.signal });
      return status?.ready === true;
    } finally {
      clearTimeout(timeout);
    }
  } catch {
    return false;
  }
}

async function connectToOriedita({ jarFile, javaCommand, runtimeDirectory, logFile }) {
  const connectionFile = path.join(runtimeDirectory, "connection.json");
  const existing = await readConnection(connectionFile);
  if (existing && await healthy(existing)) return { connection: existing, launched: false };

  await mkdir(runtimeDirectory, { recursive: true, mode: 0o700 });
  await rm(connectionFile, { force: true });
  const token = randomBytes(32).toString("hex");
  const logDescriptor = openSync(logFile, "a", 0o600);
  const child = spawn(javaCommand, ["-jar", jarFile], {
    cwd: path.dirname(path.dirname(path.dirname(jarFile))),
    detached: true,
    env: {
      ...process.env,
      ORIEDITA_MCP_CONNECTION_FILE: connectionFile,
      ORIEDITA_MCP_TOKEN: token,
    },
    stdio: ["ignore", logDescriptor, logDescriptor],
  });
  child.unref();
  closeSync(logDescriptor);

  const deadline = Date.now() + 30_000;
  while (Date.now() < deadline) {
    const connection = await readConnection(connectionFile);
    if (connection?.token === token && await healthy(connection)) return { connection, launched: true };
    await sleep(150);
  }
  throw new Error(`Oriedita did not become ready within 30 seconds; see ${logFile}`);
}

const options = parseArgs(process.argv.slice(2));
const input = path.resolve(options.input);
if (path.extname(input).toLowerCase() !== ".cp") usage("input must end in .cp");
if (!existsSync(input)) usage(`input does not exist: ${input}`);
const jarFile = findJar(options.jar);
if (!jarFile) usage("Oriedita JAR not found; set ORIEDITA_JAR or pass --jar");

const stem = path.basename(input, ".cp");
const outDir = path.resolve(options.outDir ?? path.join(path.dirname(input), `${stem}-validation`));
const outputs = {
  report: path.join(outDir, "report.json"),
  creasePattern: path.join(outDir, "crease-pattern.png"),
  fold: path.join(outDir, `${stem}.fold`),
  svg: path.join(outDir, `${stem}.svg`),
  foldedFigure: path.join(outDir, "folded-figure.png"),
};

if (!options.force) {
  for (const output of Object.values(outputs)) {
    if (existsSync(output) && (await stat(output)).size > 0) usage(`output exists: ${output} (pass --force to replace evidence)`);
  }
}
await mkdir(outDir, { recursive: true });

let syntax;
try {
  syntax = inspectCp(await readFile(input, "utf8"));
} catch (error) {
  usage(error instanceof Error ? error.message : String(error));
}

const userSuffix = typeof process.getuid === "function" ? process.getuid() : "user";
const runtimeDirectory = path.resolve(process.env.ORIEDITA_MCP_RUNTIME_DIR ?? path.join(os.tmpdir(), `oriedita-mcp-${userSuffix}`));
const logFile = path.join(runtimeDirectory, "oriedita.log");
const report = {
  success: false,
  validatedAt: new Date().toISOString(),
  input,
  jar: jarFile,
  transport: "Oriedita local control bridge",
  syntax,
  oriedita: {},
  evidence: {},
  limitations: [
    "Oriedita validation does not prove resemblance to the requested subject.",
    "Oriedita validation does not establish a practical folding sequence.",
  ],
};

try {
  const { connection, launched } = await connectToOriedita({
    jarFile,
    javaCommand: options.java,
    runtimeDirectory,
    logFile,
  });
  report.oriedita.launchedByValidator = launched;
  const api = (endpoint, body) => request(connection, endpoint, body === undefined ? {} : {
    method: "POST",
    body: JSON.stringify(body),
  });

  await api("/open", { path: input });
  const document = await api("/document");
  report.oriedita.documentLineCount = document?.lineCount ?? document?.lines?.length ?? null;

  await api("/export", { path: outputs.fold });
  await api("/export", { path: outputs.svg });
  await api("/export", { path: outputs.creasePattern });
  report.evidence.creasePatternRender = await renderSvgWithSips(outputs.svg, outputs.creasePattern)
    ? "full SVG rendered with sips"
    : "Oriedita PNG export (may reflect the current camera view)";
  report.evidence.creasePatternPng = outputs.creasePattern;
  report.evidence.fold = outputs.fold;
  report.evidence.svg = outputs.svg;

  const calculation = await api("/fold-calculate", {});
  report.oriedita.calculation = {
    started: calculation?.started === true,
    violationCount: Number.isFinite(calculation?.violationCount) ? calculation.violationCount : null,
  };

  let foldedImage = false;
  let modelInspected = false;
  if (report.oriedita.calculation.started && report.oriedita.calculation.violationCount === 0) {
    const deadline = Date.now() + 30_000;
    let status = await api("/state");
    while (status?.foldingTask?.running && Date.now() < deadline) {
      await sleep(150);
      status = await api("/state");
    }
    if (status?.foldingTask?.running) throw new Error("folding did not finish within 30 seconds");
    const foldedFigure = await api("/folded-figure");
    if (foldedFigure?.data) {
      await writeFile(outputs.foldedFigure, Buffer.from(foldedFigure.data, "base64"));
      foldedImage = true;
    }
    const foldedModel = await api("/folded-model");
    modelInspected = Boolean(foldedModel);
  }
  report.evidence.foldedFigurePng = foldedImage ? outputs.foldedFigure : null;
  report.oriedita.foldedModelReturned = modelInspected;

  const finalStatus = await api("/state");
  report.oriedita.version = finalStatus?.version ?? null;
  report.oriedita.completed = finalStatus?.foldedFigures?.completed === true;
  report.success = report.oriedita.calculation.started
    && report.oriedita.calculation.violationCount === 0
    && report.oriedita.completed
    && foldedImage
    && modelInspected;
} catch (error) {
  report.error = error instanceof Error ? error.message : String(error);
} finally {
  await writeFile(outputs.report, `${JSON.stringify(report, null, 2)}\n`);
}

console.log(JSON.stringify({ success: report.success, report: outputs.report, calculation: report.oriedita.calculation ?? null, completed: report.oriedita.completed ?? false }, null, 2));
if (!report.success) process.exitCode = 2;
