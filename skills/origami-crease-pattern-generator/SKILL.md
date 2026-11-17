---
name: origami-crease-pattern-generator
description: Design, edit, search, and validate editable origami crease patterns. Use for one-off models and revisions, multi-candidate experiments, Oriedita validation, DEFOX folding sequences, or paper-thickness evaluation; do not use for decorative crease-pattern artwork or folding instructions without editable geometry.
---

# 折り紙展開図ジェネレーター

Produce an editable crease pattern as the primary artifact and evidence appropriate to the claim being made. Treat topology, local flat-foldability, global layer order, target fidelity, folding sequence, paper thickness, and real-paper reproduction as separate questions.

## Choose the operating mode

- Use **standard mode** by default for one crease pattern, a user-supplied pattern, a focused edit, or ordinary Oriedita validation.
- Use **production mode** when the request needs multiple candidates, batch evaluation, repeatable run records, a DEFOX folding sequence, a paper-thickness budget, or delivery-grade evidence.
- Load only the production references needed for the request. Do not run a batch search, build a folding sequence, or estimate thickness merely because those capabilities are available.

Both modes use the same geometry, validation criteria, scripts, and final crease-pattern source.

## Plan the geometry

- Preserve a user-supplied `.cp`, `.fold`, diagram, or exact construction unless the requested change requires new geometry.
- For a parametric base or tessellation, derive coordinates from shared formulas, symmetry, ratios, and construction constraints.
- For a subject requested only by name, read [references/novel-subject-workflow.md](references/novel-subject-workflow.md). Plan named features and a flap tree before drawing creases.
- Use [assets/examples/validated-crane-base.cp](assets/examples/validated-crane-base.cp) only for a relevant bird-like base. Any change invalidates its previous evidence and requires revalidation.

If the user supplies a designer, article set, blog, or body of work as a reference, read [references/research-and-provenance.md](references/research-and-provenance.md). Record what was reviewed, extract reusable principles, and do not copy another creator's crease pattern as the new model. For a large image set, also read [references/research-image-index.md](references/research-image-index.md) and use `scripts/make_contact_sheet.py`.

## Build the crease pattern

Read [references/cp-format.md](references/cp-format.md) before creating `.cp` data. For programmatic construction, write the documented JSON and run:

```bash
python3 scripts/build_cp.py pattern.json pattern.cp
```

Maintain these invariants:

- include the complete paper boundary;
- assign every adopted crease intentionally as mountain or valley;
- remove zero-length and duplicate segments;
- snap intended intersections and preserve exact symmetry;
- keep design notes and feature names outside the `.cp` file;
- never silently replace a user-supplied pattern with a similar-looking pattern.

For an original multi-flap subject, keep a machine-readable feature map. Copy [assets/templates/subject-design-brief.md](assets/templates/subject-design-brief.md) and [assets/templates/features.json](assets/templates/features.json) when useful, replacing every placeholder.

## Validate the adopted pattern

When Oriedita MCP is available, read [references/oriedita-mcp.md](references/oriedita-mcp.md) and validate the exact adopted CP without taking over unrelated unsaved work. Otherwise run:

```bash
node scripts/validate_cp.mjs pattern.cp
```

Set `ORIEDITA_JAR` or pass `--jar /absolute/path/oriedita.jar` when automatic discovery fails. Record whether validation used MCP or the direct bridge.

Call the Oriedita result validated only when:

- `violationCount` is `0`;
- calculation reports `started: true`;
- the folded state reports `completed: true`;
- folded-figure image and folded-model data were returned.

Visually inspect the crease-pattern and folded-figure images. For complex original models, use an independent global solver when available and audit its output with `scripts/audit_folded_state.py`. Read [references/computational-validation.md](references/computational-validation.md) and [references/validation-criteria.md](references/validation-criteria.md) before interpreting the evidence.

After several materially similar failures, change topology, simplify the target, or report the limitation. Do not repeat an unchanged search or call an unvalidated pattern complete.

## Use production mode when required

### Evaluate multiple candidates

Read [references/validation-pipeline.md](references/validation-pipeline.md), run the dependency preflight, and use the batch runner:

```bash
python3 scripts/check_dependencies.py --config validators.json
node scripts/validate_candidates.mjs \
  --input candidates \
  --config validators.json \
  --out-dir evidence/run-001 \
  --cache-dir evidence/cache
```

Inspect `summary.json` and `run-manifest.json` before individual logs. Treat a timeout as unknown, not invalid. Treat an exploratory SAT assignment as discovery evidence until the exact assigned CP passes the unchanged original checker and Oriedita.

### Build a folding sequence

After adopting and validating the geometry, read [references/defox-fold-sequence.md](references/defox-fold-sequence.md). Use [assets/templates/fold-sequence-plan.json](assets/templates/fold-sequence-plan.json) to record ordered states, changed creases, moving and stationary packets, layer access, collision review, and validation status.

Validate every edited `.cp` state before importing it into DEFOX. Save the editable `.defox` project and export the requested diagrams. DEFOX provides sequence representation and diagram evidence; only a real-paper trial establishes physical executability.

### Evaluate paper thickness

Read [references/paper-thickness.md](references/paper-thickness.md) when practical foldability or paper choice matters. Prefer measured paper caliper; do not treat GSM as thickness unless density is supplied and the result is labeled an estimate.

Populate [assets/templates/thickness-budget.json](assets/templates/thickness-budget.json) from the adopted layer order and sequence, then run:

```bash
python3 scripts/evaluate_thickness.py thickness-budget.json evidence/thickness-report.json
```

Treat the result as a screening budget, not a physical simulation. Revalidate geometry and recompute the report after any relevant design change.

### Coordinate optional agents

The skill must work with one agent. When the user or host explicitly permits subagents and independent work would help, read [references/orchestration.md](references/orchestration.md). Delegate only independent candidate evaluation, research partitions, or final auditing; keep sequential geometry decisions in the main agent.

## Deliver

Always provide the stable final artifacts separately from exploratory candidates:

- editable `.cp` source;
- `.fold` and `.svg` exports when Oriedita validation ran;
- crease-pattern and folded-figure images plus validation JSON;
- feature map and folded-state audit for original multi-flap subjects;
- a short claim table separating format validity, local validation, global layer order, target fidelity, sequence evidence, thickness evidence, and physical testing.

Include production artifacts only when their route was used: batch summaries and `run-manifest.json`, ordered state files and the `.defox` project, or thickness inputs and reports. Include a construction record for substantial original models.

If Oriedita is unavailable, label the CP **unverified** and identify the missing dependency or failed check. Label sequence, thickness, and physical-folding claims separately when their evidence is unavailable.
