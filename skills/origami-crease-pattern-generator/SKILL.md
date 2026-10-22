---
name: origami-crease-pattern-generator
description: Design, edit, and validate editable origami crease patterns, including original models invented from a requested subject, flap-tree planning, staged shaping, Oriedita-compatible .cp files, and computational evidence. Use when the user asks to create an origami model or crease pattern, revise mountain/valley assignments, or test flat-foldability; do not use for decorative crease-pattern artwork or folding instructions alone.
---

# 折り紙展開図ジェネレーター

Produce the crease pattern itself as the primary artifact. A rendered image is supporting evidence, not a substitute for editable geometry. For a new subject, treat topology, flat folding, recognizable shape, and physical foldability as separate questions.

## Choose the generation route

- If the user supplies a `.cp`, `.fold`, diagram, or exact construction, preserve its geometry and revise only the requested parts.
- For a parametric base or geometric tessellation, derive coordinates from symmetry, ratios, and construction constraints. Prefer exact or consistently rounded coordinates over hand-estimated points.
- For a novel object requested only by name, read [references/novel-subject-workflow.md](references/novel-subject-workflow.md). Begin from a feature and flap plan, then iterate against both foldability and silhouette. Do not claim the intended object was generated merely because the pattern folds flat.
- Use [assets/examples/validated-crane-base.cp](assets/examples/validated-crane-base.cp) only when a bird/crane-like base is relevant. Any modification invalidates its previous validation and must be tested again.

If the user supplies a designer, blog, or body of work as a reference, research the cited primary material before designing. Record exactly what was read, distinguish a fresh review from inherited notes, extract reusable design principles, and avoid copying a creator's CP as the new model. Read [references/research-and-provenance.md](references/research-and-provenance.md) for this mode.

## Build the `.cp`

For programmatic construction, describe the paper and crease segments in JSON as documented in [references/cp-format.md](references/cp-format.md), then run:

```bash
python3 scripts/build_cp.py pattern.json pattern.cp
```

Keep the following invariants:

- Include the complete paper boundary.
- Assign every crease intentionally as mountain or valley; do not use color as decoration.
- Remove zero-length and duplicate segments. Snap points that are meant to coincide and preserve exact symmetry where intended.
- Keep source/construction notes outside the `.cp` file because the format stores only colored segments.
- Never silently replace a user-provided pattern with a visually similar one.

Read [references/cp-format.md](references/cp-format.md) before writing `.cp` files directly or constructing the JSON input.

For complex original models, keep a machine-readable feature map from named subject parts to paper coordinates. This lets later stages verify that ears, wings, limbs, tails, or other flaps remain distinct rather than merely existing somewhere in the layer stack. Copy [assets/templates/subject-design-brief.md](assets/templates/subject-design-brief.md) and [assets/templates/features.json](assets/templates/features.json) when they are useful; replace every placeholder before delivery.

## Validate with Oriedita

When Oriedita MCP is available, use it so the exact CP can be opened, calculated, inspected, and saved in Oriedita. Read [references/oriedita-mcp.md](references/oriedita-mcp.md) before the first MCP validation in a task.

When MCP is unavailable, run the bundled direct-bridge validator after every adopted geometry or assignment change:

```bash
node scripts/validate_cp.mjs pattern.cp
```

Set `ORIEDITA_JAR` or pass `--jar /absolute/path/oriedita.jar` if the local Oriedita application JAR is not found automatically. The validator connects directly to Oriedita's local control bridge and does not require Node packages from the separate MCP server. Use `--out-dir` to choose the evidence directory and `--force` only when replacing prior generated evidence is intended. Record whether the validation used MCP or the direct bridge.

Call a candidate validated only when all of these are true:

- Oriedita reports `violationCount: 0`.
- Folding calculation reports `started: true`.
- The final folded-figure state reports `completed: true`.
- Both a folded-figure image and folded-model data were returned.

Visually inspect the crease-pattern and folded-figure PNGs. Flat-foldability does not establish that the result resembles the requested subject, has an ergonomic folding sequence, avoids impractical layer thickness, or can fold rigidly. Read [references/validation-criteria.md](references/validation-criteria.md) when interpreting or reporting validation.

For a complex original model, also validate the complete layer order with an independent flat-fold solver when one is available. If an exploratory solver chooses mountain/valley assignments, export those assignments and re-open the assigned CP in the original solver and Oriedita. A faster search order or SAT encoding may discover an assignment, but it is evidence only after the unchanged constraints and final CP have been checked again.

Use `scripts/audit_folded_state.py` on Flat-Folder-style solver output to audit the square boundary, connectivity, area, rigid face geometry, named feature collisions, and whether feature tips reach the computed silhouette. Read [references/computational-validation.md](references/computational-validation.md) before using that report as evidence.

When validation fails, use the violation count and visible geometry to revise the smallest relevant region. Preserve failed reports that explain a design decision. After several materially similar failures, change the topology, simplify the target, or report the limitation instead of repeating the same search or calling an unvalidated pattern complete.

## Deliver

Provide:

- the editable `.cp` source;
- the exported `.fold` and `.svg` when Oriedita validation ran;
- crease-pattern and folded-figure PNG evidence;
- the validation JSON;
- a feature map and a computed folded-state audit for original multi-flap subjects;
- a short statement distinguishing syntax validity, Oriedita flat-fold validation, visual match to the requested subject, and whether a folding sequence was established.

For substantial original models, also provide a short construction record: intended flap tree and ratios, shaping stages, the exact final validation inputs, rejected features that materially affected the result, and the scope of any research used. Package stable final artifacts separately from exploratory candidates. A PDF can help print or explain the CP, but it does not replace `.cp`, `.fold`, or validation evidence.

If Oriedita is unavailable, the `.cp` may be delivered only as **unverified**, with the missing dependency or failed check stated plainly.
