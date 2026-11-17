# Computational validation for original models

Use this reference for multi-flap original models or whenever validation claims depend on more than Oriedita's local check.

## Evidence layers

Keep these results separate:

1. **CP syntax:** segments parse, boundary exists, assignments are known, and no segment is degenerate.
2. **Local flat-foldability:** vertex conditions have no reported violations.
3. **Global flat state:** a consistent layer ordering exists for all overlapping faces.
4. **Rigid-face geometry:** every folded face preserves its pairwise distances; the face areas tile one sheet and the graph remains connected.
5. **Feature fidelity:** named tips remain distinct and required visible tips lie on the actual silhouette.
6. **Sequence model:** ordered endpoint states, moving packets, layer access, and collision review for each transition.
7. **Positive thickness:** stack and wrapping-crease budgets computed from paper caliper and the adopted layer order.
8. **Physical model:** the continuous sequence, finite paper thickness, collisions, hand access, and three-dimensional finishing work succeed in real paper.

Oriedita completion supports levels 1–3 for its selected state. A second global solver or an independent constraint encoding is valuable for complex CPs. Geometry and feature audits support levels 4–5. DEFOX evidence and the sequence plan support level 6. The thickness report supports level 7. Only a physical trial supports level 8.

## Flat-Folder-style state audit

The bundled `scripts/audit_folded_state.py` accepts a JSON state containing:

- `fold.V`, `fold.Vf`, `fold.EV`, `fold.EA`, and `fold.FV`;
- optionally `cell.P`, `cell.SP`, and `cell.SC` for silhouette checks;
- an optional feature JSON object mapping names to `[paper_x, paper_y]`.

Run:

```bash
python3 scripts/audit_folded_state.py state.json report.json --features features.json
```

The audit checks graph connectivity, Euler value, boundary degree, total paper and face area, rigid distances within every face, coincident named tips, and silhouette distances. It assumes the state schema and layer solution are trustworthy inputs; it does not solve the CP itself.

## Assignment discovery

An unknown-MV CP may have a large search space. It is acceptable to change variable ordering or encode the same permitted constraint tuples as SAT to discover a solution. Do not change geometric tolerances, omit constraints, or treat a partial assignment as proof.

After discovery:

1. derive a complete mountain/valley assignment;
2. save a CP containing those assignments;
3. run the assigned CP through the original unchanged global solver;
4. run that exact CP through Oriedita;
5. retain the discovery report separately from the final revalidation reports.

If the CP importer changes paper side, document the mountain/valley convention and compare exported CP, FOLD, SVG, and native Oriedita data by normalized segment endpoints and assignments.

## Claims

Report counts and numerical errors only from the final adopted state. “Local violation count 0” is not shorthand for a valid global layer order. “Global layer order found” is not shorthand for a recognizable subject or a practical folding sequence.
