"""halo-hacker ingest — the library. No I/O policy of its own.

Pipeline: scan (adapters) -> privacy filter -> classify -> distill -> gated upsert.
Guards (non-negotiable, each traced to a measured failure):
  - no delete verb anywhere in the store
  - provenance on every row (source, sha256, date, trust tier)
  - refusal-biased upsert: ambiguous or multi-target matches are REFUSED
  - the privacy filter must prove it dropped something (N-before -> M-after)
  - model content is DATA, never instructions (hardened system prompts)
  - filtered/incomplete model responses are refused, never filed (P1)
"""

__version__ = "0.1.0"
