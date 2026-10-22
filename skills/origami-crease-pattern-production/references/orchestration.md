# Optional agent orchestration

Use this reference only when the host supports subagents and the work contains genuinely independent partitions. The skill must remain functional without subagents.

## Delegation boundary

Good partitions include:

- independent groups of candidate files;
- separate primary-source inventories;
- an independent final audit that does not edit the design;
- investigation of distinct failure classes.

Keep a task in the main agent when each step depends on the preceding geometry decision, the task is short, agents would edit the same files, or one slow external process dominates elapsed time.

## Context and task brief

Give a subagent only:

- objective;
- exact input paths or identifiers;
- permitted tools and mutations;
- required output schema and artifact paths;
- timeout and retry limits;
- stop conditions.

When the host exposes a `fork_turns` control, use `none` for independent tasks and supply this brief instead of the whole conversation. Use a bounded recent-turn count only when the task truly depends on that context.

Do not require specific model names in this portable skill. Use lower-cost reasoning for inventory, extraction, batch execution, and formatting. Reserve the strongest available reasoning for difficult geometry design, conflicting solver evidence, and final audit.

Each agent should write a separate manifest file. Do not have multiple agents concurrently edit one shared JSON document. The coordinating agent may merge completed manifests afterward.
