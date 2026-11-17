# Run manifest fields

The batch runner writes `run-manifest.json`, `summary.json`, and `results.json`. Keep them with the exact candidate set and configuration used for the run.

Important run fields:

- `run_id`, `started_at`, and `ended_at` identify the execution;
- `config_hash` and `candidate_count` identify its inputs;
- `duration_ms` measures wall-clock time;
- `cache_hits` separates reused computation from new computation;
- `status_counts` separates passed, failed, completed, timeout, and process error;
- `error_classes` groups failures that should be fixed once rather than investigated candidate by candidate;
- `jobs` records validator, candidate, duration, cache status, exit code, logs, parsed JSON, and artifact directory.

Model token usage is host telemetry, not something a validator can infer. If the host exposes usage, store it alongside the run without inventing missing values:

```json
{
  "model_usage": {
    "model": null,
    "reasoning_effort": null,
    "input_tokens": null,
    "cached_input_tokens": null,
    "output_tokens": null,
    "reasoning_tokens": null
  }
}
```

Use task-content labels such as `candidate_geometry_generation`, `flat_folder_validation`, `sat_assignment_search`, `oriedita_final_validation`, and `visual_evidence_review`. Avoid reporting only broad phases such as “analysis” or “implementation.”
