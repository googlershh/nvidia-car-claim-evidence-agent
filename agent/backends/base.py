"""Model-facing interfaces. Everything else in the pipeline is deterministic."""

from __future__ import annotations

from typing import Protocol

from ..schemas import ClaimBundle, ClaimResult, DamageFinding, VideoFinding


class VideoAnalyzer(Protocol):
    def analyze(self, bundle: ClaimBundle) -> VideoFinding: ...


class DamageAnalyzer(Protocol):
    def analyze(self, bundle: ClaimBundle) -> DamageFinding: ...


class Writer(Protocol):
    def write(self, result: ClaimResult) -> str: ...


class Backend(Protocol):
    name: str
    video: VideoAnalyzer
    damage: DamageAnalyzer
    writer: Writer

    def usage(self) -> tuple[int, int]:
        """(calls, tokens) spent so far."""
        ...
