# Validation criteria

Report each level separately. Passing one level does not imply the next.

1. **Format validity** — every `.cp` row parses, assignments are known, and segments are non-degenerate.
2. **Local flat-foldability** — Oriedita reports zero local violations. This is stronger than a plausible-looking drawing but is not sufficient by itself.
3. **Calculated flat-folded state** — Oriedita starts and completes the folding calculation and returns folded-model data.
4. **Target fidelity** — the completed silhouette, flap count, proportions, and visible sides match the user's requested subject. This needs visual or geometric review.
5. **Practical foldability** — a usable folding sequence exists and the model is physically reasonable with real paper. Oriedita's completed state does not prove this.

The bundled validator marks `success: true` only for levels 1–3. Describe levels 4 and 5 from evidence; never infer them automatically.

## Failure interpretation

- `violationCount > 0`: the current vertices/assignments violate local flat-foldability checks. Inspect the affected construction rather than merely swapping arbitrary colors.
- `started: false`: Oriedita refused to calculate, usually because violations or malformed geometry remain.
- Calculation started but did not complete: simplify the candidate, check degeneracies and intersections, and retain the failed report.
- Completed but wrong silhouette: this is a design failure, not a validator success for the user's actual goal. Revise topology/proportions and rerun all checks.

## Evidence bundle

The validator writes a compact `report.json`, `crease-pattern.png`, exported `.fold` and `.svg`, and—on a completed calculation—`folded-figure.png`. Keep these files together with the exact `.cp` input used for the run.
