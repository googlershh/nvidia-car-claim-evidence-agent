"""Model backends: `oracle` (offline, ground truth injected) and `nim` (hosted NIM)."""

from __future__ import annotations


def load_backend(name: str, **kwargs):
    if name == "oracle":
        from .oracle import OracleBackend
        return OracleBackend(**kwargs)
    if name == "nim":
        from .nim import NimBackend
        return NimBackend(**kwargs)
    raise ValueError(f"unknown backend {name!r} (oracle | nim)")
