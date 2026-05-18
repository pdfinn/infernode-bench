"""Decontamination — n-gram overlap checks against upstream corpora.

Placeholder package for IB-18. The full implementation walks the four
risk corpora (upstream inferno-os, InferNode itself, plan9port, the
Inferno Programmer's Manual), computes minhash signatures, and reports
items with significant overlap.

Until IB-18a lands, `overlap_check.run()` is a no-op that emits a
manifest documenting the corpora it would have checked.
"""
