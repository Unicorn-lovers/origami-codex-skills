# Paper-thickness budget

Use this reference after a candidate layer order and folding sequence exist. Zero-thickness flat-foldability is the input to this check, not its conclusion.

## Required measurements

Prefer `paper.thickness_mm` measured from the actual sheet with a micrometer or caliper. Measure a stack of several sheets when one sheet is below the instrument's useful resolution, then divide by the sheet count. Record whether coating, foil, sizing, moisture, or lamination differs from the intended final paper.

GSM is mass per unit area and does not uniquely determine caliper. If direct caliper is unavailable, the calculator accepts both `gsm` and `density_g_cm3` and estimates:

```text
thickness_mm = gsm / (1000 * density_g_cm3)
```

Label this result estimated. Do not invent a density from the paper name.

`effective_thickness_factor` defaults to `1.0`. Change it only from measured stack compression or an explicit safety factor. Keep the original caliper and factor in the report.

## Layer measurements

For every dense region, record:

- `layers`: maximum simultaneous sheet layers in the adopted state;
- `feature_width_mm`: narrowest local flap or feature that must still be shaped;
- `available_gap_mm`: physical space available to the stack, when the design provides one.

The calculator reports:

```text
stack_thickness_mm = layers * effective_thickness_mm
stack_to_feature_ratio = stack_thickness_mm / feature_width_mm
gap_margin_mm = available_gap_mm - stack_thickness_mm
```

For every crease that wraps around an existing packet, record `wrap_layers`, the number of intervening layer levels between the two incident sheets in the adopted layer order. The calculator reports the proportional clearance budget:

```text
required_clearance_mm = wrap_layers * effective_thickness_mm
clearance_margin_mm = available_clearance_mm - required_clearance_mm
```

This follows the positive-thickness crease-width idea that the material demand at a crease scales with the number of intervening layers. It is a screening budget, not a complete bend-radius, plasticity, friction, humidity, or collision model. See [Folding a Paper Strip to Minimize Thickness](https://erikdemaine.org/papers/Thickness_WALCOM2015/paper.pdf) for the formal one-dimensional crease-width model and its limits.

## Acceptance limits

There is no universal acceptable stack thickness or ratio for every paper and operation. Put project-specific limits in the JSON only when they come from geometry, a prototype, or an explicit design target:

- `max_stack_mm`;
- `max_stack_to_feature_ratio`;
- `min_gap_margin_mm`;
- `min_clearance_margin_mm`.

The script returns `fail` when an explicit limit is violated, `pass` when at least one applicable limit or available clearance is assessed and none fails, and `insufficient_evidence` when there is no criterion to assess. A numerical stack calculation without a limit remains useful but is not a feasibility proof.

## Use the result

Inspect failing or largest hotspots first. Common responses are to change the order of operations, open layers temporarily, replace a closed sink with a more accessible sequence, distribute layers across a wider region, add clearance, enlarge the sheet while preserving CP proportions, or choose thinner paper. Any CP geometry change requires the zero-thickness validators and DEFOX states to be regenerated.

Only a real-paper trial establishes the combined effects of bending radius, stiffness, springback, friction, fiber damage, and hand access.
