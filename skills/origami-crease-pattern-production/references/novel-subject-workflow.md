# Novel subject workflow

Use this workflow when the user names a subject but does not provide an established construction.

## 1. Define what must be visible

Write a compact design brief before drawing creases. List the features that carry the identity of the subject, their count, relative length, connection point, and priority. Separate these three kinds of requirements:

- **Flap requirements:** independently movable tips such as ears, horns, wings, limbs, tail, nose, petals, or handles.
- **Surface requirements:** broad areas such as face, chest, shell, fuselage, or clothing that need paper width rather than another tip.
- **Pose and silhouette requirements:** which parts must reach the outline, overlap, point upward, remain paired, or stay separated.

Do not turn every decorative detail into a flap. Begin with the fewest tips that can communicate the subject. Use `assets/templates/subject-design-brief.md` when a saved brief helps.

## 2. Plan a flap tree and paper allocation

Connect the required tips through a tree of meaningful body junctions. Assign relative path lengths before choosing paper coordinates. Reserve rivers or bands between crowded parts when their layers must pass without trapping one another.

Check every pair of leaf tips: the distance on paper must be at least the scaled path length through the tree. Record active or nearly active contacts; they explain the geometry of the base. Prefer analytic symmetry and contact equations over hand-tuned coordinates.

If a TreeMaker-compatible implementation is available, generate the uniaxial base from this tree. Otherwise construct the simplest known base whose independent flaps and surface areas satisfy the same topology. A successful base establishes paper allocation, not a finished subject.

## 3. Establish a verified base

Validate the base before shaping it. Retain these records:

- tree, node positions, and relative lengths;
- paper scale and all leaf coordinates;
- editable CP or FOLD data;
- local flat-fold report;
- one complete layer order when a global solver is available.

Name each leaf in a feature map. Do not rely on visual guesses later.

## 4. Shape in small stages

Work in the folded state when possible. Move one logical group at a time: spread wings, separate paired legs, raise a tail, lift the head, then shape small facial tips. After each adopted stage, map the new fold lines back to the unfolded paper and validate the whole model again.

A useful geometric operation is reflection across a folded-state line. For unit normal `n` and line `n·q=c`, reflection sends a point to:

`q' = q - 2(n·q-c)n`

To send a flap tip from `q` to target `t`, use the perpendicular bisector of `q` and `t`. Select the connected face group on the intended side of the line, and reject the operation if it captures protected features or overlaps another simultaneous move. Map each clipped line segment back through the rigid isometry of its source face.

Record each stage as both an input intention and a resolved plan containing affected faces, line parameters, original tip, and target tip. Do not present this computational design sequence as a proven physical folding sequence.

## 5. Judge the actual silhouette

Inspect the solver's visible cells and layer order, not a hand-drawn completed animal. For every named feature, check:

- the paper point maps to the expected folded tip;
- different features do not coincide;
- a feature intended to be visible lies on the computed silhouette boundary;
- paired features are visually separable;
- long features retain enough width at their roots;
- the subject still has the required surface area for face or body.

A buried ear or nose does not become successful merely because its endpoint exists in the folded geometry. Revise the surrounding surface or competing flap root.

## 6. Finish at the right claim level

Use “computational flat-fold prototype” when local conditions and a global layer order pass but no paper prototype exists. Use “original model” without qualification only when the requested subject is visually recognizable and the claim is supported by the delivered evidence. State separately whether a continuous folding sequence, paper thickness, three-dimensional shaping, and real-paper reproduction were tested.

When practical folding remains untested, deliver the editable CP and design record so a folder can continue from an honest prototype.
