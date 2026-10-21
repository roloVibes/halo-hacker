# PLAYBOOK_CATALOG.md

## Shipped (0.2.0, 2026-10-21) — all 16 validated against schemas/playbook.schema.json
Below: the shipped catalog. Every playbook is model-independent (enforced by test); every stage above low-impact requires approval (enforced by test + validator).

| ID | Phase | Category | Methodology ref |
|---|---|---|---|
| recon.asset-inventory | reconnaissance | recon | WSTG-INFO-* |
| recon.endpoint-discovery | reconnaissance | recon | from provided data only |
| recon.technology-id | reconnaissance | recon | WSTG-INFO-02 |
| discovery.authz-object-level | discovery | api | OWASP API1:2023 |
| discovery.authz-function-level | discovery | api | OWASP API5:2023 |
| discovery.authn-testing | discovery | web | WSTG-ATHN-* |
| discovery.session-handling | discovery | web | WSTG-SESS-* |
| discovery.input-handling | discovery | web | WSTG-INPV-* |
| discovery.business-logic | discovery | web | WSTG-BUSL-* |
| discovery.llm-prompt-injection | discovery | ai | OWASP LLM01 |
| discovery.llm-tool-boundaries | discovery | ai | OWASP LLM06/LLM07 |
| discovery.cloud-iam-config | discovery | cloud | CSP config guides |
| validation.low-impact-repro | validation | validation | — |
| validation.active-approval-gated | validation | validation | requires_approval: true |
| evidence.sanitize-and-store | evidence | evidence | content-addressed |
| reporting.draft-from-confirmed | reporting | reporting | generated, never hand-written |

Rules already fixed by the schema: playbooks never name models or
providers; stages are ordered with rising impact; any stage above
`low-impact` defaults to `requires_approval: true` at authoring time
(pending CORE_REQUESTS CR-4 for mechanical enforcement).
