# DEFOX folding-sequence workflow

Use this reference after the final crease pattern and layer solution have been adopted.

DEFOX is a diagram editor for origami creators. Its official repository describes it as a tool for distorting valid flat-foldable states and adding tutorial symbols to `.cp` inputs. The application stores an editable `.defox` project and exports CP, SVG, and PNG material. It also offers crease interpolation, forward/backward layer-order inference, manual layer selection, cyclic-order resolution, and adjacent-state comparison.

Source: [DEFOX official repository](https://github.com/kei-morisue/step-folder)

## What DEFOX establishes

DEFOX can represent an ordered sequence of flat states and help illustrate the change between adjacent states. It does not establish all of the following on its own:

- that an arbitrary final CP can be reached continuously from the sheet;
- that fingers can access the required layers;
- that moving packets avoid three-dimensional collision;
- that positive-thickness paper fits the zero-thickness states;
- that a compound transition is understandable or repeatable by a folder.

Keep these as separate claims in the final evidence.

## Prepare ordered states

1. Start from the validated final base or folded state and decompose it into recognizable operations. Working backward is often easier because each removal should simplify the state.
2. Create `000.cp` for the sheet, followed by `001.cp`, `002.cp`, and so on. Each file must describe the complete state after that step, not only newly added creases.
3. Prefer one standard operation per transition: precrease, valley or mountain fold, unfold, reverse fold, squash, petal fold, rabbit ear, pleat, sink, swivel, or a clearly named shaping move.
4. Split a compound operation when its moving packet, pivot, layer access, or release action cannot be shown unambiguously in one diagram.
5. Re-run Oriedita or the adopted global validator on every state whose geometry or assignments differ. Preserve the exact report beside that state.

Record every transition in `fold-sequence-plan.json`:

- source and destination state;
- operation name and changed crease identifiers;
- moving and stationary packets;
- layer access and any temporary opening;
- expected visible landmarks before and after;
- collision review and thickness hotspots;
- validation status and physical-test status.

## Assemble in DEFOX

1. Import the ordered `.cp` files with **Crease Interpolation** enabled only when correspondence with the previous state is intentional.
2. Inspect the state created for every import. Reject a state when DEFOX reports it as unfoldable or chooses the wrong global layer solution.
3. Use forward or backward layer-order inference only between corresponding neighboring states. Review every inferred order; do not propagate an error through the remaining sequence.
4. Resolve ambiguous groups with **Manual Layer Control**. Use **Resolve Cyclic Orders** when needed, then recheck the affected packets.
5. Use adjacent-state difference and depth controls to identify the active creases and moving layers. Confirm that unchanged landmarks remain stable.
6. Add arrows, mountain/valley symbols, unfold marks, reference points, repeat marks, and explanatory symbols only after the transition is geometrically settled.
7. Save the `.defox` project before export. Export step images or page SVG/PNG and, when useful, the ordered CP states.

The DEFOX project format is an application-owned format. Prefer saving it from DEFOX rather than synthesizing `.defox` JSON directly, because internal fields may change.

## Review each transition

A transition is ready for delivery only when:

- both endpoint states are valid under the chosen zero-thickness checker;
- the changed creases and their assignments match the intended operation;
- moving and stationary packets are named;
- layer access is visible or explained;
- no obvious locked pocket or packet crossing is left unresolved;
- thickness hotspots have layer counts for `evaluate_thickness.py`;
- symbols agree with the actual motion;
- a physical trial is marked passed, failed, or not run.

DEFOX output is diagram evidence. State separately whether the full sequence was physically folded from the intended paper.
