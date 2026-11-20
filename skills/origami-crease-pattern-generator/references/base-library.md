# Base library and adaptation

Use the base library before designing an original subject from a blank square. The goal is to reuse a verified topology when it covers the essential tips and surfaces with fewer risky changes than a new construction.

## Route

1. Convert the subject brief into named flap and surface requirements.
2. Rank the bundled bases and inspect the top candidates.
3. Map every essential feature to a specific flap or surface on each candidate.
4. Compare the transformations, thickness, unused regions, and shaping access.
5. Adopt the lowest-risk candidate only after inspecting its CP.
6. Design from scratch only when every candidate has an essential blocker or needs a topology-changing rewrite.

Do not treat a base name as a subject category. A bird base is a topology with particular tips and panels, not a restriction to birds.

## Bundled bases

The library in `assets/bases/` contains eight generated and Oriedita-validated CPs:

| Base | Useful starting structure | Common cost |
|---|---|---|
| Bird | opposed long tips and paired side panels | dense center and competition between tip length and panel width |
| Frog | four limb-like tips around a shared center | high layer density and limited broad body area |
| Fish | two rabbit-ear tips on a strong diagonal axis | few independent appendages |
| Preliminary | neutral four-flap stack | most useful capability still requires a transformation |
| Waterbomb | radial triangular panels and volume | weak long-axis differentiation |
| Blintz | four inward corner regions and an inner square | smaller effective sheet and early layer buildup |
| Kite | long pointed nose and a broad rear panel on a diagonal axis | few independent appendages |
| Windmill | four outward blades around a square hub | blade direction has a handedness |

`assets/bases/catalog.json` records each individual flap's heuristic length, width, paired relation, affordances, tradeoffs, common transformations, and the validation level. These profiles are screening descriptors, not geometric proof. Inspect `assets/bases/validation-preview.png` for a quick view of the bundled CPs and Oriedita folded-figure results; the preview is validation evidence, not a physical-fold guarantee.

## Rank candidates

Copy `assets/examples/base-requirements.json`, replace the subject and features, then run:

```bash
python3 scripts/rank_bases.py base-requirements.json --top 3 --output base-candidates.json
```

Each feature needs:

- `name`;
- positive integer `count`;
- `length`: `long`, `medium`, or `short`;
- `width`: `broad`, `medium`, or `narrow`;
- `priority`: `essential`, `supporting`, or `optional`;
- optional `paired: true` when a visually paired allocation matters;
- optional `derive_from`: the name of a directly allocated parent feature when small local features can be split from that same region.

`derive_from` is a strict shared-region instruction: the child will not receive an independent flap. Use it only for one local step, such as ears split from a broad head flap. A child cannot be longer or broader than its parent, and multiple children must each be narrower than the parent region. The result records `source_flap_ids`, but the ranker still cannot prove that a proposed split has enough paper; inspect the geometry. Do not use derivation to excuse a new global branch or a chain of derived features. Broad face, torso, shell, or wing regions belong in `surfaces`, not as extra flaps. Preferences may name `bilateral`, `rotational`, or `diagonal` symmetry and `flat` or `3d` volume.

The ranker assigns each independent flap at most once. A longer or broader flap can cover a smaller requirement with an adaptation cost. It reports derived details, unmatched features, essential blockers, unused flaps, likely transformations, and catalog tradeoffs. Scores may be negative when the mismatch is severe.

For the bundled bases, copy a candidate's `suggested_assignments` into the adaptation plan. Each entry identifies a reserved flap or surface in [regions.json](../assets/bases/regions.json). For a fixed flap assignment the ranker chooses surface IDs that minimize the total area of pairwise overlap, then lists each positive-area intersection in `region_conflicts`. Its `area_fraction` is relative to the whole square. A shared edge consumes zero common area. Review the declared tip, root and polygons on the unfolded paper and adjust the allocation wherever an intersection matters. Derived children continue to reference their parent's paper through `source_flap_ids` until the geometry defines the split. Custom catalogs may omit the top-level `regions` file for count-only screening.

## Compare adaptation plans

For the chosen mapping, follow [the adaptation workflow](base-adaptation.md). Use the [base folding sequences](base-fold-sequences.md) to locate its original corners and layers.

For each shortlisted base, record:

- the exact flap or surface assigned to every named feature;
- which tips are shortened, stretched, split, joined, or moved;
- added rivers, grafts, sinks, or hybrid quadrants;
- regions that become unavailable after each change;
- expected layer hotspots and shaping access;
- whether the result still resembles the original base enough for its evidence to be useful.

Prefer an adaptation when all essential features are covered and the remaining work is local. Reject it when a missing essential feature forces a new global topology, when a broad surface would be consumed, or when the added layers defeat the intended paper.

## Transformation order

Use lower-risk changes before global ones:

1. shorten or redirect an existing tip;
2. change final shaping without changing the CP;
3. split one flap locally;
4. release an unused edge or corner region;
5. add a narrow border or strip graft;
6. add a river or stretch a base;
7. hybridize a quadrant or replace a molecule;
8. abandon the base and return to a new flap tree.

Every crease change creates a new candidate. Revalidate the exact modified CP; the bundled base validation does not transfer to a derivative.

## Library maintenance

The CP files are generated from exact formulas:

```bash
python3 scripts/generate_base_library.py --check
```

Run `scripts/rank_bases.py --self-test` after changing catalog capabilities or ranking behavior. When base geometry changes, regenerate it, validate every CP with Oriedita, visually inspect both crease-pattern and folded-figure images, and then update the catalog validation fields.
