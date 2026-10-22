---
name: origami-crease-pattern-production
description: Create, edit, batch-evaluate, and validate editable origami crease patterns, DEFOX folding sequences, and paper-thickness budgets with reproducible evidence. Use for original-model searches, many-candidate experiments, or delivery-grade validation; use a simpler crease-pattern workflow for one-off edits that do not need batch orchestration.
---

# 折り紙展開図プロダクション

Produce an editable crease pattern as the primary artifact and a reproducible evidence bundle as the proof. Treat topology, local flat-foldability, global layer order, recognizable silhouette, and practical paper folding as separate claims.

## Choose the route

- Preserve user-supplied `.cp`, `.fold`, or exact construction geometry unless the requested change requires otherwise.
- For a parametric base or tessellation, derive coordinates from shared formulas, symmetry, ratios, and construction constraints.
- For a subject requested only by name, read [references/novel-subject-workflow.md](references/novel-subject-workflow.md). Plan named features and a flap tree before drawing creases.
- For research based on a designer, article set, or image collection, read [references/research-and-provenance.md](references/research-and-provenance.md). When many downloaded images would otherwise be inspected individually, also read [references/research-image-index.md](references/research-image-index.md) and use `scripts/make_contact_sheet.py`.

Use [assets/examples/validated-crane-base.cp](assets/examples/validated-crane-base.cp) only for a relevant bird-like base. Any change invalidates its previous evidence and requires a new validation run.

## Build candidates

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

For an original multi-flap subject, keep a machine-readable feature map. Copy [assets/templates/subject-design-brief.md](assets/templates/subject-design-brief.md) and [assets/templates/features.json](assets/templates/features.json) when useful, replacing all placeholders.

## Search efficiently

Generate a bounded candidate set before invoking expensive validators. Do not alternate one model decision with one validator call when candidates can be evaluated together.

For multiple candidates, read [references/validation-pipeline.md](references/validation-pipeline.md), run the dependency preflight, and use the batch runner:

```bash
python3 scripts/check_dependencies.py --config validators.json
node scripts/validate_candidates.mjs \
  --input candidates \
  --config validators.json \
  --out-dir evidence/run-001 \
  --cache-dir evidence/cache
```

Flat-Folder and SAT are separate validators. Flat-Folder is an origami-specific constraint solver; do not describe it as a general SAT solver. Treat SAT search as assignment-discovery evidence until the exact assigned CP passes the unchanged original checker and Oriedita.

Inspect `summary.json` and `run-manifest.json` first. Open candidate logs only for validator disagreements, timeouts, new error classes, or finalists. A timeout means unknown, not invalid. Do not retry an unchanged candidate more than once.

## Validate adopted candidates

When Oriedita MCP is available, read [references/oriedita-mcp.md](references/oriedita-mcp.md) and validate the exact adopted CP without taking over unrelated unsaved work. Otherwise run the bundled direct bridge:

```bash
node scripts/validate_cp.mjs pattern.cp
```

Set `ORIEDITA_JAR` or pass `--jar /absolute/path/oriedita.jar`. Do not search source trees or download dependencies automatically after the fixed resolver fails; report the missing dependency.

Call an Oriedita candidate validated only when:

- `violationCount` is `0`;
- calculation reports `started: true`;
- the folded state reports `completed: true`;
- folded-figure image and folded-model data were returned.

For complex original models, also run an independent global solver when available and audit its state with `scripts/audit_folded_state.py`. Read [references/computational-validation.md](references/computational-validation.md) and [references/validation-criteria.md](references/validation-criteria.md) before interpreting those results.

After several materially similar failures, change topology, simplify the target, or report the limitation. Do not continue an unchanged search solely to consume the remaining budget.

## Build the folding sequence

After adopting and validating the geometry, read [references/defox-fold-sequence.md](references/defox-fold-sequence.md). DEFOX edits and illustrates an ordered series of valid flat-folded states; it does not by itself prove that an arbitrary final CP has a physically executable sequence.

Use [assets/templates/fold-sequence-plan.json](assets/templates/fold-sequence-plan.json) to plan the state series. Keep one state per meaningful folding operation or clearly documented compound operation, identify the changed creases, and record the moving packet, stationary packet, required layer access, and collision review. Validate every edited `.cp` state before importing it into DEFOX.

In DEFOX, import the ordered `.cp` states, propagate layer order only where the geometry justifies it, resolve cyclic or ambiguous orders explicitly, inspect the difference between each adjacent pair, then add fold arrows and tutorial symbols. Save the editable `.defox` project and export the step or page SVG/PNG evidence. Call the result a generated folding sequence only when the ordered states and transitions are included; call it physically verified only after a real-paper trial.

## Budget paper thickness

Read [references/paper-thickness.md](references/paper-thickness.md) whenever practical foldability or paper choice matters. Prefer a measured sheet thickness in millimetres. Do not treat GSM as thickness unless density is supplied and the result is labeled an estimate.

Populate [assets/templates/thickness-budget.json](assets/templates/thickness-budget.json) from the adopted layer order and DEFOX transitions, then run:

```bash
python3 scripts/evaluate_thickness.py thickness-budget.json evidence/thickness-report.json
```

Review maximum stack thickness, stack-to-feature-width ratio, and the clearance margin at every wrapping crease. The crease-width result is a proportional thickness budget derived from intervening layer count, not an exact finite-element simulation. If layer counts, paper caliper, or available clearances are missing, report the affected result as unassessed rather than assuming zero-thickness paper.

When a thickness check fails, first revise the sequence, layer order, spread/sink strategy, local clearance, sheet size, or paper choice. Revalidate any geometry change and recompute the thickness report from the final sequence.

## Coordinate optional agents

The skill must work with one agent. When the host supports subagents, read [references/orchestration.md](references/orchestration.md) and delegate only independent candidate evaluation, research partitions, or final auditing. Keep sequential geometry decisions in the main agent.

## Deliver

Provide stable final artifacts separately from exploratory candidates:

- editable `.cp` source;
- exported `.fold` and `.svg` when Oriedita validation ran;
- crease-pattern and folded-figure PNG evidence;
- editable DEFOX `.defox` project, ordered state `.cp` files, and step/page SVG or PNG when a folding sequence was requested;
- fold-sequence plan with transition, layer-access, and collision-review records;
- thickness input and `thickness-report.json` when practical paper folding or paper choice was requested;
- validation JSON and batch `run-manifest.json` when the batch runner was used;
- feature map and folded-state audit for original multi-flap subjects;
- construction record for substantial original models;
- a short claim table distinguishing format validity, local validation, global layer order, target fidelity, folding sequence, and physical testing.

If Oriedita is unavailable, label the CP **unverified** and identify the missing dependency or failed check. If DEFOX or measured paper data is unavailable, separately label the sequence or thickness claim unverified. A rendered image or SAT assignment does not replace editable geometry and final revalidation.
