# Validation criteria

Report each level separately. Passing one level does not imply the next.

1. **Format validity** — every `.cp` row parses, assignments are known, and segments are non-degenerate.
2. **Local flat-foldability** — Oriedita reports zero local violations. This is stronger than a plausible-looking drawing but is not sufficient by itself.
3. **Calculated flat-folded state** — Oriedita starts and completes the folding calculation and returns folded-model data.
4. **Target fidelity** — the completed silhouette, flap count, proportions, and visible sides match the user's requested subject. This needs visual or geometric review.
5. **Sequence representation** — ordered valid states and documented transitions exist, with moving packets, layer access, collision review, and DEFOX diagram evidence when requested.
6. **Positive-thickness budget** — measured or explicitly estimated caliper, adopted layer counts, stack hotspots, and wrapping-crease clearances have been evaluated. This remains a screening calculation.
7. **Practical foldability** — the complete sequence has been folded successfully from the intended real paper. Oriedita, DEFOX, and the thickness budget do not individually prove this.

The bundled Oriedita validator marks `success: true` only for levels 1–3. Describe levels 4–7 from their separate evidence; never infer them automatically.

## Failure interpretation

- `violationCount > 0`: the current vertices/assignments violate local flat-foldability checks. Inspect the affected construction rather than merely swapping arbitrary colors.
- `started: false`: Oriedita refused to calculate, usually because violations or malformed geometry remain.
- Calculation started but did not complete: simplify the candidate, check degeneracies and intersections, and retain the failed report.
- Completed but wrong silhouette: this is a design failure, not a validator success for the user's actual goal. Revise topology/proportions and rerun all checks.

## Evidence bundle

The validator writes a compact `report.json`, `crease-pattern.png`, exported `.fold` and `.svg`, and—on a completed calculation—`folded-figure.png`. Keep these files together with the exact `.cp` input used for the run.
