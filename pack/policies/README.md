# policies/

Engagement and execution policy definitions. The machine schemas are
`../schemas/engagement.schema.json` and `../schemas/scope-targets.schema.json`.

Enforcement model (per the pack spec, Phase 5): a Security Tool Broker
validates every tool action against the engagement policy BEFORE
execution, independently of the LLM, deny-by-default. The mechanical
pre-tool-call hook does not exist in Halo yet (docs/CORE_REQUESTS.md CR-4);
until it does, active stages are human-gated in the playbook schema and
bios carry mirror deny-rules. Prompt wording is never the enforcement
mechanism.
