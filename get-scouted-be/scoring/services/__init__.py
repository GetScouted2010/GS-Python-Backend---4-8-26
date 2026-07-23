"""Shared service-layer substrate for Phase 4's score endpoints.

`population.py` centralizes the single reconstruct-from-ORM entry point and
the canonical reconstruct -> RMM -> Compatibility/Transfer-Probability
wiring order (proven correct by Phase 3's `generate_scoring_oracle.py`) so
every downstream score service (compatibility, financial, performance,
transfer-probability, summary) reuses it verbatim instead of reinventing
(and drifting on) the sequencing.
"""
