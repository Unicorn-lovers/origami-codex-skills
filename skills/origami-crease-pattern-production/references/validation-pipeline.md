# Reproducible validation pipeline

Use this reference when evaluating more than one candidate or when the final result needs repeatable timing, cache, and failure evidence.

## Pipeline boundary

Keep these validators distinct:

1. syntax and boundary checks;
2. Flat-Folder or another origami-specific global constraint solver;
3. an optional independent SAT encoding;
4. Oriedita validation of adopted finalists;
5. folded-state geometry and feature audit.

Do not turn agreement between weak checks into a stronger claim. SAT can discover an assignment; it does not prove that a changed encoding is equivalent to the original constraints. Oriedita completion does not establish target resemblance or a practical folding sequence.

## Batch runner

`scripts/validate_candidates.mjs` accepts one `.cp` file or a directory and a JSON configuration. It runs validator commands without a shell, applies wall-clock timeouts, limits parallel work, hashes inputs and validator settings, and writes compact summaries.

Read [run-manifest-schema.md](run-manifest-schema.md) when integrating the output with host telemetry or comparing task-content bottlenecks.

Example `validators.json`:

```json
{
  "extensions": [".cp"],
  "validators": [
    {
      "id": "flat_folder",
      "version": "flat-folder commit-or-release",
      "command": ["node", "/absolute/path/to/flatfold-validator.mjs", "{input}"],
      "timeoutSeconds": 60,
      "classification": {
        "field": "valid",
        "passValues": [true],
        "failValues": [false]
      }
    },
    {
      "id": "sat",
      "version": "cadical 2.x + encoding-v1",
      "command": ["python3", "/absolute/path/to/sat-validator.py", "{input}"],
      "timeoutSeconds": 90,
      "classification": {
        "field": "satisfiable",
        "passValues": [true],
        "failValues": [false]
      }
    },
    {
      "id": "oriedita",
      "version": "oriedita release-or-jar-checksum",
      "command": [
        "node",
        "{skill_dir}/scripts/validate_cp.mjs",
        "{input}",
        "--out-dir",
        "{output_dir}",
        "--force"
      ],
      "timeoutSeconds": 120,
      "classification": {
        "field": "success",
        "passValues": [true],
        "failValues": [false]
      }
    }
  ]
}
```

Supported placeholders are `{input}`, `{output_dir}`, `{candidate_id}`, and `{skill_dir}`. Commands are argument arrays deliberately; do not replace them with shell command strings.

The validator should print one JSON object to stdout. `classification.field` may be a dotted path such as `result.valid`. If classification is omitted, exit code `0` means `completed`; a nonzero exit means `error`.

## Cache correctness

The cache key includes:

- exact candidate bytes;
- validator identifier and declared version;
- command, timeout, classification, working directory, and configured environment;
- batch-runner schema version.

Change the declared validator version whenever solver code, constraint encoding, tolerance, or meaningful settings change. Cache `passed`, `failed`, and `completed` results. Do not reuse `timeout` or `error` results as mathematical conclusions.

## Review order

Read outputs in this order:

1. `summary.json` for counts and bottlenecks;
2. `run-manifest.json` for duration, cache hits, and error classes;
3. `results.json` for validator disagreements and finalists;
4. per-job stdout and stderr only when investigation is necessary.

Prefer changing the candidate generator when many candidates fail in the same way. Prefer changing the validator integration when many candidates share the same process error. Do not ask the model to reinterpret hundreds of identical logs.
