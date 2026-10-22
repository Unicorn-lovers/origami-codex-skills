# Oriedita MCP validation

Use the Oriedita MCP tools exposed in the current environment. Tool names can vary slightly by integration; inspect their schemas instead of assuming a hidden endpoint.

## Safe validation sequence

1. Read Oriedita status. If the active document is unsaved, do not replace it. Use an isolated Oriedita instance when the environment supports one, or stop and preserve the user's document.
2. Open the absolute path of the candidate `.cp`.
3. Read the imported crease pattern and record its line count.
4. Start the folding calculation and record whether it started and the local violation count.
5. Wait until calculation stops. Require a completed folded figure, not merely a started task.
6. Retrieve the folded figure image and folded model. Inspect the image and retain model data as evidence.
7. Save the exact final document as `.ori` when native editing data is part of the deliverable. Export `.fold`, `.svg`, and a crease-pattern image when supported.

Call the candidate MCP-validated only if the imported segment count matches the intended CP, local violation count is zero, the calculation completes, and both folded image and model data are returned. Keep the validation report next to the exact CP it describes.

## Operational boundaries

- Do not expose connection tokens, authorization headers, or connection-file contents in reports.
- Do not take over an unrelated Oriedita window containing unsaved work.
- An MCP timeout means the calculation was not confirmed within the wait period; it is not a mathematical proof that no flat state exists.
- Native `.ori`, `.cp`, `.fold`, and `.svg` should be compared by normalized segment endpoints and mountain/valley assignment before claiming that they are equivalent.
- Oriedita's successful calculation does not verify subject resemblance, a continuous physical sequence, paper thickness, or three-dimensional finishing.
