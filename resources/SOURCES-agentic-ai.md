# SOURCES — the agentic-AI attack technique library

Provenance for `resources/payloads/agentic-ai.json`. Distilled 2026-11-18
from public research and standards. **Original prose and original payload
templates only** — techniques are described in the pack's own words and the
payloads were written for this pack; no source text is reproduced verbatim
(the halo-re REPOS.md precedent for training-derived content).

## Standards and taxonomies

| Source | What it anchors |
|---|---|
| [OWASP Top 10 for LLM Applications 2025](https://genai.owasp.org/llm-top-10/) | Class-to-risk mapping (LLM01 prompt injection, LLM06 excessive agency, LLM07 system prompt leakage, LLM08 vector/embedding weaknesses) |
| [MITRE ATLAS](https://atlas.mitre.org/) | Adversary-technique refs (AML.T0051 LLM prompt injection, AML.T0051.001 indirect, AML.T0024 exfiltration, AML.T0040 ML supply-chain/confused-deputy patterns); the pack ships ATLAS data in `resources/atlas/atlas.json` |

## Research the technique classes distill

| Source | Author / org | Contribution |
|---|---|---|
| [Embrace the Red](https://embracethered.com/) (blog) | Johann Rehberger | Indirect prompt injection against real assistants, system-prompt extraction patterns, exfiltration via markdown/images, agent persistence tricks |
| [Not what you've signed up for: Compromising Real-World LLM-Integrated Applications with Indirect Prompt Injection](https://arxiv.org/abs/2302.12173) (arXiv) | Greshake et al. | The foundational indirect-injection paper: poisoned retrieved content executing in a privileged context |
| [Zenity Labs research blog](https://labs.zenity.io/) | Zenity Labs | Copilot/agent IPI work: separator spoofing, RAG poisoning, "assume a fully compromised model" — the approval-policy and permission-boundary classes |
| "AIjacking" and agent-permission research | Michael Bargury | Living-off-the-land abuse of agent permissions; confirmation and consent flows as an attack surface |
| Public jailbreak literature and disclosure writeups (DAN-family, encoding pivots, low-resource-language pivots) | various | The persona, encoding, and multi-turn classes — folklore techniques restated as testable templates |

## Distillation method

Each technique was rewritten as a *testable template*: a class, a name, when
to reach for it, payload templates with `{{CANARY}}` placeholders, and the
observable that counts as success. Well-known public payloads (plain
"ignore previous instructions", base64 wrappers) are restated generically.
Anything that could not be attributed to public research was written fresh
for this library. Nothing here is copied from a non-public source.
