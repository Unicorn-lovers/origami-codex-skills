#!/usr/bin/env node

import { createHash, randomUUID } from "node:crypto";
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import {
  mkdir,
  mkdtemp,
  readFile,
  readdir,
  rename,
  rm,
  stat,
  writeFile,
} from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const SCHEMA_VERSION = 1;
const MAX_LOG_BYTES = 1024 * 1024;
const SKILL_DIR = path.dirname(path.dirname(fileURLToPath(import.meta.url)));

function usage(message) {
  if (message) console.error(`error: ${message}`);
  console.error(`usage: validate_candidates.mjs --input FILE_OR_DIR --config validators.json
  [--out-dir DIR] [--cache-dir DIR] [--max-parallel N] [--force] [--no-recursive]
  validate_candidates.mjs --self-test`);
  process.exit(2);
}

function parseArgs(argv) {
  const options = {
    input: null,
    config: null,
    outDir: null,
    cacheDir: null,
    maxParallel: 2,
    force: false,
    recursive: true,
    selfTest: false,
  };
  for (let index = 0; index < argv.length; index += 1) {
    const item = argv[index];
    if (item === "--force") options.force = true;
    else if (item === "--no-recursive") options.recursive = false;
    else if (item === "--self-test") options.selfTest = true;
    else if (["--input", "--config", "--out-dir", "--cache-dir", "--max-parallel"].includes(item)) {
      const value = argv[index + 1];
      if (!value) usage(`${item} requires a value`);
      const key = item.slice(2).replace(/-([a-z])/g, (_, letter) => letter.toUpperCase());
      options[key] = item === "--max-parallel" ? Number(value) : value;
      index += 1;
    } else usage(`unknown option: ${item}`);
  }
  if (options.selfTest) return options;
  if (!options.input || !options.config) usage("--input and --config are required");
  if (!Number.isInteger(options.maxParallel) || options.maxParallel < 1 || options.maxParallel > 32) {
    usage("--max-parallel must be an integer from 1 to 32");
  }
  return options;
}

function stableValue(value) {
  if (Array.isArray(value)) return value.map(stableValue);
  if (value && typeof value === "object") {
    return Object.fromEntries(Object.keys(value).sort().map((key) => [key, stableValue(value[key])]));
  }
  return value;
}

function stableJson(value) {
  return JSON.stringify(stableValue(value));
}

function sha256(value) {
  return createHash("sha256").update(value).digest("hex");
}

function safeId(value) {
  const cleaned = value.replace(/[^A-Za-z0-9._-]+/g, "-").replace(/^-+|-+$/g, "");
  return cleaned || "candidate";
}

function validateConfig(config) {
  if (!config || typeof config !== "object" || Array.isArray(config)) throw new Error("config root must be an object");
  if (!Array.isArray(config.validators) || config.validators.length === 0) throw new Error("config.validators must be a non-empty array");
  const ids = new Set();
  for (const validator of config.validators) {
    if (!validator || typeof validator !== "object") throw new Error("each validator must be an object");
    if (typeof validator.id !== "string" || !/^[A-Za-z0-9_-]+$/.test(validator.id)) {
      throw new Error("validator.id must contain only letters, digits, underscore, or hyphen");
    }
    if (ids.has(validator.id)) throw new Error(`duplicate validator id: ${validator.id}`);
    ids.add(validator.id);
    if (typeof validator.version !== "string" || !validator.version.trim()) {
      throw new Error(`validator ${validator.id} requires a non-empty version`);
    }
    if (!Array.isArray(validator.command) || validator.command.length === 0 || validator.command.some((item) => typeof item !== "string")) {
      throw new Error(`validator ${validator.id}.command must be a non-empty string array`);
    }
    const timeout = validator.timeoutSeconds ?? 60;
    if (!Number.isFinite(timeout) || timeout <= 0 || timeout > 3600) {
      throw new Error(`validator ${validator.id}.timeoutSeconds must be between 0 and 3600`);
    }
    if (validator.env !== undefined && (!validator.env || typeof validator.env !== "object" || Array.isArray(validator.env))) {
      throw new Error(`validator ${validator.id}.env must be an object`);
    }
    if (validator.classification !== undefined) {
      const rule = validator.classification;
      if (!rule || typeof rule.field !== "string" || !Array.isArray(rule.passValues) || !Array.isArray(rule.failValues)) {
        throw new Error(`validator ${validator.id}.classification requires field, passValues, and failValues`);
      }
    }
  }
  const extensions = config.extensions ?? [".cp"];
  if (!Array.isArray(extensions) || extensions.length === 0 || extensions.some((item) => typeof item !== "string" || !item.startsWith("."))) {
    throw new Error("config.extensions must be a non-empty array of extensions beginning with a dot");
  }
  return { ...config, extensions: extensions.map((item) => item.toLowerCase()) };
}

async function discoverCandidates(input, extensions, recursive, excludedRoots) {
  const absolute = path.resolve(input);
  const inputStat = await stat(absolute);
  if (inputStat.isFile()) return [absolute];
  if (!inputStat.isDirectory()) throw new Error(`input is not a file or directory: ${absolute}`);

  const candidates = [];
  async function walk(directory) {
    const entries = await readdir(directory, { withFileTypes: true });
    for (const entry of entries.sort((left, right) => left.name.localeCompare(right.name))) {
      const target = path.join(directory, entry.name);
      if (excludedRoots.some((root) => target === root || target.startsWith(`${root}${path.sep}`))) continue;
      if (entry.isDirectory() && recursive) await walk(target);
      else if (entry.isFile() && extensions.includes(path.extname(entry.name).toLowerCase())) candidates.push(target);
    }
  }
  await walk(absolute);
  return candidates;
}

function expand(value, placeholders) {
  return value.replace(/\{(input|output_dir|candidate_id|skill_dir|config_dir)\}/g, (_, key) => placeholders[key]);
}

function parseJsonOutput(stdout) {
  const text = stdout.trim();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    const lines = text.split(/\r?\n/).map((line) => line.trim()).filter(Boolean).reverse();
    for (const line of lines) {
      try {
        return JSON.parse(line);
      } catch {
        // Continue looking for a final one-line JSON record.
      }
    }
  }
  return null;
}

function getField(value, dottedPath) {
  return dottedPath.split(".").reduce((current, key) => (
    current !== null && current !== undefined && typeof current === "object" ? current[key] : undefined
  ), value);
}

function includesJson(values, target) {
  const encoded = stableJson(target);
  return values.some((value) => stableJson(value) === encoded);
}

function classify({ validator, parsed, exitCode, signal, timedOut, spawnError }) {
  if (timedOut) return { status: "timeout", errorClass: "timeout" };
  if (spawnError) return { status: "error", errorClass: "spawn_error" };
  if (validator.classification && parsed !== null) {
    const actual = getField(parsed, validator.classification.field);
    if (includesJson(validator.classification.passValues, actual)) return { status: "passed", errorClass: null };
    if (includesJson(validator.classification.failValues, actual)) return { status: "failed", errorClass: null };
  }
  if (exitCode === 0) return { status: "completed", errorClass: null };
  if (signal) return { status: "error", errorClass: `signal_${signal}` };
  return { status: "error", errorClass: `exit_${exitCode ?? "unknown"}` };
}

function boundedAppend(state, chunk) {
  if (state.bytes >= MAX_LOG_BYTES) {
    state.truncated = true;
    return;
  }
  const buffer = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
  const remaining = MAX_LOG_BYTES - state.bytes;
  state.chunks.push(buffer.subarray(0, remaining));
  state.bytes += Math.min(buffer.length, remaining);
  if (buffer.length > remaining) state.truncated = true;
}

async function runProcess(command, options) {
  const started = Date.now();
  const stdout = { chunks: [], bytes: 0, truncated: false };
  const stderr = { chunks: [], bytes: 0, truncated: false };
  let timedOut = false;
  let spawnError = null;

  const outcome = await new Promise((resolve) => {
    let settled = false;
    let timer;
    const child = spawn(command[0], command.slice(1), {
      cwd: options.cwd,
      env: options.env,
      shell: false,
      detached: process.platform !== "win32",
      stdio: ["ignore", "pipe", "pipe"],
    });

    child.stdout.on("data", (chunk) => boundedAppend(stdout, chunk));
    child.stderr.on("data", (chunk) => boundedAppend(stderr, chunk));

    const finish = (value) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      resolve(value);
    };

    child.on("error", (error) => {
      spawnError = error.message;
      finish({ exitCode: null, signal: null });
    });
    child.on("close", (exitCode, signal) => finish({ exitCode, signal }));

    timer = setTimeout(() => {
      timedOut = true;
      try {
        if (process.platform !== "win32" && child.pid) process.kill(-child.pid, "SIGTERM");
        else child.kill("SIGTERM");
      } catch {
        // The child may have exited between the deadline and termination.
      }
      setTimeout(() => {
        try {
          if (process.platform !== "win32" && child.pid) process.kill(-child.pid, "SIGKILL");
          else child.kill("SIGKILL");
        } catch {
          // Already stopped.
        }
      }, 1000).unref();
    }, options.timeoutMs);
  });

  return {
    ...outcome,
    timedOut,
    spawnError,
    durationMs: Date.now() - started,
    stdout: Buffer.concat(stdout.chunks).toString("utf8"),
    stderr: Buffer.concat(stderr.chunks).toString("utf8"),
    stdoutTruncated: stdout.truncated,
    stderrTruncated: stderr.truncated,
  };
}

async function writeJsonAtomic(target, value) {
  await mkdir(path.dirname(target), { recursive: true });
  const temporary = `${target}.${process.pid}.${randomUUID()}.tmp`;
  await writeFile(temporary, `${JSON.stringify(value, null, 2)}\n`, "utf8");
  await rename(temporary, target);
}

async function runJob(job, context) {
  const validatorFingerprint = stableJson({
    schemaVersion: SCHEMA_VERSION,
    id: job.validator.id,
    version: job.validator.version,
    command: job.validator.command,
    timeoutSeconds: job.validator.timeoutSeconds ?? 60,
    classification: job.validator.classification ?? null,
    cwd: job.validator.cwd ?? null,
    env: job.validator.env ?? null,
  });
  const key = sha256(Buffer.concat([
    Buffer.from(`schema:${SCHEMA_VERSION}\n${validatorFingerprint}\n`, "utf8"),
    job.content,
  ]));
  const cacheRoot = path.join(context.cacheDir, key);
  const cacheResult = path.join(cacheRoot, "result.json");

  if (!context.force && existsSync(cacheResult)) {
    try {
      const cached = JSON.parse(await readFile(cacheResult, "utf8"));
      if (cached.cacheable === true && ["passed", "failed", "completed"].includes(cached.status)) {
        return { ...cached, cache_hit: true, retrieval_duration_ms: 0 };
      }
    } catch {
      // Ignore an incomplete or corrupt cache entry and recompute it.
    }
  }

  const artifactDir = path.join(cacheRoot, "artifacts");
  await mkdir(artifactDir, { recursive: true });
  const placeholders = {
    input: job.input,
    output_dir: artifactDir,
    candidate_id: job.candidateId,
    skill_dir: SKILL_DIR,
    config_dir: context.configDir,
  };
  const command = job.validator.command.map((item) => expand(item, placeholders));
  const cwd = path.resolve(expand(job.validator.cwd ?? context.configDir, placeholders));
  const configuredEnv = Object.fromEntries(Object.entries(job.validator.env ?? {}).map(
    ([keyName, value]) => [keyName, expand(String(value), placeholders)],
  ));
  const execution = await runProcess(command, {
    cwd,
    env: { ...process.env, ...configuredEnv },
    timeoutMs: (job.validator.timeoutSeconds ?? 60) * 1000,
  });
  const stdoutPath = path.join(cacheRoot, "stdout.log");
  const stderrPath = path.join(cacheRoot, "stderr.log");
  await writeFile(stdoutPath, execution.stdout, "utf8");
  await writeFile(stderrPath, execution.stderr, "utf8");
  const parsed = parseJsonOutput(execution.stdout);
  const classification = classify({
    validator: job.validator,
    parsed,
    exitCode: execution.exitCode,
    signal: execution.signal,
    timedOut: execution.timedOut,
    spawnError: execution.spawnError,
  });
  const result = {
    schema_version: SCHEMA_VERSION,
    candidate_id: job.candidateId,
    input: job.input,
    input_sha256: job.inputHash,
    validator_id: job.validator.id,
    validator_version: job.validator.version,
    status: classification.status,
    error_class: classification.errorClass,
    exit_code: execution.exitCode,
    signal: execution.signal,
    spawn_error: execution.spawnError,
    duration_ms: execution.durationMs,
    cache_hit: false,
    cacheable: ["passed", "failed", "completed"].includes(classification.status),
    command,
    cwd,
    configured_env_keys: Object.keys(configuredEnv).sort(),
    stdout_log: stdoutPath,
    stderr_log: stderrPath,
    stdout_truncated: execution.stdoutTruncated,
    stderr_truncated: execution.stderrTruncated,
    parsed_output: parsed,
    artifact_dir: artifactDir,
  };
  await writeJsonAtomic(cacheResult, result);
  return result;
}

async function mapLimit(items, limit, mapper) {
  const results = new Array(items.length);
  let next = 0;
  async function worker() {
    while (true) {
      const index = next;
      next += 1;
      if (index >= items.length) return;
      results[index] = await mapper(items[index], index);
    }
  }
  await Promise.all(Array.from({ length: Math.min(limit, items.length) }, () => worker()));
  return results;
}

function summarize(results) {
  const statusCounts = {};
  const errorClasses = {};
  const validators = {};
  for (const result of results) {
    statusCounts[result.status] = (statusCounts[result.status] ?? 0) + 1;
    if (result.error_class) errorClasses[result.error_class] = (errorClasses[result.error_class] ?? 0) + 1;
    const record = validators[result.validator_id] ?? {
      jobs: 0,
      cache_hits: 0,
      computed_duration_ms: 0,
      status_counts: {},
    };
    record.jobs += 1;
    if (result.cache_hit) record.cache_hits += 1;
    else record.computed_duration_ms += result.duration_ms;
    record.status_counts[result.status] = (record.status_counts[result.status] ?? 0) + 1;
    validators[result.validator_id] = record;
  }

  const byCandidate = new Map();
  for (const result of results) {
    const records = byCandidate.get(result.candidate_id) ?? [];
    records.push(result);
    byCandidate.set(result.candidate_id, records);
  }
  const disagreements = [];
  for (const [candidateId, records] of byCandidate) {
    const conclusive = records.filter((record) => ["passed", "failed"].includes(record.status));
    if (new Set(conclusive.map((record) => record.status)).size > 1) {
      disagreements.push({
        candidate_id: candidateId,
        validators: Object.fromEntries(conclusive.map((record) => [record.validator_id, record.status])),
      });
    }
  }

  const bottlenecks = Object.entries(validators)
    .map(([validatorId, record]) => ({ validator_id: validatorId, computed_duration_ms: record.computed_duration_ms }))
    .sort((left, right) => right.computed_duration_ms - left.computed_duration_ms);
  return { status_counts: statusCounts, error_classes: errorClasses, validators, disagreements, bottlenecks };
}

async function runBatch(options) {
  const startedAt = new Date();
  const input = path.resolve(options.input);
  const configPath = path.resolve(options.config);
  const configDir = path.dirname(configPath);
  const config = validateConfig(JSON.parse(await readFile(configPath, "utf8")));
  const outDir = path.resolve(options.outDir ?? path.join(process.cwd(), `validation-run-${Date.now()}`));
  const cacheDir = path.resolve(options.cacheDir ?? path.join(outDir, "cache"));
  await mkdir(outDir, { recursive: true });
  await mkdir(cacheDir, { recursive: true });
  const candidates = await discoverCandidates(input, config.extensions, options.recursive, [outDir, cacheDir]);
  if (candidates.length === 0) throw new Error(`no candidate files found under ${input}`);

  const inputIsDirectory = (await stat(input)).isDirectory();
  const candidateRecords = [];
  for (const candidate of candidates) {
    const content = await readFile(candidate);
    const inputHash = sha256(content);
    const relative = inputIsDirectory ? path.relative(input, candidate) : path.basename(candidate);
    const name = relative.slice(0, relative.length - path.extname(relative).length).split(path.sep).join("-");
    candidateRecords.push({
      input: candidate,
      content,
      inputHash,
      candidateId: `${safeId(name)}-${inputHash.slice(0, 8)}`,
    });
  }

  const jobs = candidateRecords.flatMap((candidate) => config.validators.map((validator) => ({ ...candidate, validator })));
  const results = await mapLimit(jobs, options.maxParallel, (job) => runJob(job, {
    cacheDir,
    configDir,
    force: options.force,
  }));
  results.sort((left, right) => (
    left.candidate_id.localeCompare(right.candidate_id) || left.validator_id.localeCompare(right.validator_id)
  ));

  const endedAt = new Date();
  const summary = summarize(results);
  const manifest = {
    schema_version: SCHEMA_VERSION,
    run_id: randomUUID(),
    task_content: "crease_pattern_batch_validation",
    started_at: startedAt.toISOString(),
    ended_at: endedAt.toISOString(),
    duration_ms: endedAt.getTime() - startedAt.getTime(),
    input,
    config: configPath,
    config_hash: sha256(stableJson(config)),
    candidate_count: candidateRecords.length,
    validator_count: config.validators.length,
    job_count: results.length,
    cache_hits: results.filter((result) => result.cache_hit).length,
    max_parallel: options.maxParallel,
    status_counts: summary.status_counts,
    error_classes: summary.error_classes,
    model_usage: {
      model: null,
      reasoning_effort: null,
      input_tokens: null,
      cached_input_tokens: null,
      output_tokens: null,
      reasoning_tokens: null,
    },
    jobs: results.map((result) => ({
      candidate_id: result.candidate_id,
      validator_id: result.validator_id,
      status: result.status,
      error_class: result.error_class,
      duration_ms: result.duration_ms,
      cache_hit: result.cache_hit,
      exit_code: result.exit_code,
      stdout_log: result.stdout_log,
      stderr_log: result.stderr_log,
      artifact_dir: result.artifact_dir,
    })),
  };
  await Promise.all([
    writeJsonAtomic(path.join(outDir, "results.json"), results),
    writeJsonAtomic(path.join(outDir, "summary.json"), summary),
    writeJsonAtomic(path.join(outDir, "run-manifest.json"), manifest),
  ]);
  return { outDir, results, summary, manifest };
}

async function selfTest() {
  const temporary = await mkdtemp(path.join(os.tmpdir(), "origami-batch-self-test-"));
  try {
    const inputDir = path.join(temporary, "candidates");
    const outDir = path.join(temporary, "run");
    const cacheDir = path.join(temporary, "cache");
    await mkdir(inputDir, { recursive: true });
    await writeFile(path.join(inputDir, "good.cp"), "GOOD\n", "utf8");
    await writeFile(path.join(inputDir, "bad.cp"), "BAD\n", "utf8");
    const validatorCode = [
      "const fs=require('fs');",
      "const value=fs.readFileSync(process.argv[1],'utf8');",
      "const valid=value.includes('GOOD');",
      "console.log(JSON.stringify({valid}));",
      "process.exit(valid?0:2);",
    ].join("");
    const configPath = path.join(temporary, "validators.json");
    await writeJsonAtomic(configPath, {
      extensions: [".cp"],
      validators: [{
        id: "mock",
        version: "self-test-v1",
        command: [process.execPath, "-e", validatorCode, "{input}"],
        timeoutSeconds: 2,
        classification: { field: "valid", passValues: [true], failValues: [false] },
      }, {
        id: "mock_timeout",
        version: "self-test-v1",
        command: [process.execPath, "-e", "setTimeout(()=>{}, 5000)"],
        timeoutSeconds: 0.1,
      }],
    });
    const options = {
      input: inputDir,
      config: configPath,
      outDir,
      cacheDir,
      maxParallel: 2,
      force: false,
      recursive: true,
    };
    const first = await runBatch(options);
    const second = await runBatch({ ...options, outDir: path.join(temporary, "run-2") });
    const firstStatuses = first.results.map((result) => result.status).sort();
    const expected = ["failed", "passed", "timeout", "timeout"];
    if (stableJson(firstStatuses) !== stableJson(expected)) throw new Error(`unexpected statuses: ${firstStatuses}`);
    const secondCacheHits = second.results.filter((result) => result.cache_hit).length;
    if (secondCacheHits !== 2) throw new Error(`expected two reusable cache entries, got ${secondCacheHits}`);
    if (second.results.filter((result) => result.status === "timeout").length !== 2) {
      throw new Error("timeout results were not recomputed as expected");
    }
    console.log(JSON.stringify({ success: true, statuses: firstStatuses, second_run_cache_hits: secondCacheHits }));
  } finally {
    await rm(temporary, { recursive: true, force: true });
  }
}

const options = parseArgs(process.argv.slice(2));
try {
  if (options.selfTest) await selfTest();
  else {
    const outcome = await runBatch(options);
    console.log(JSON.stringify({
      output: outcome.outDir,
      candidates: outcome.manifest.candidate_count,
      jobs: outcome.manifest.job_count,
      cache_hits: outcome.manifest.cache_hits,
      status_counts: outcome.summary.status_counts,
      disagreements: outcome.summary.disagreements.length,
    }, null, 2));
    if ((outcome.summary.status_counts.error ?? 0) > 0 || (outcome.summary.status_counts.timeout ?? 0) > 0) {
      process.exitCode = 2;
    }
  }
} catch (error) {
  console.error(`error: ${error instanceof Error ? error.message : String(error)}`);
  process.exitCode = 2;
}
