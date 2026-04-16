from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


def clamp_score(value: Any, default: float = 0.0) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return default
    return max(0.0, min(1.0, score))


def coerce_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "y", "on"}:
            return True
        if normalized in {"0", "false", "no", "n", "off", ""}:
            return False
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    return default


@dataclass(slots=True)
class SignalInput:
    entity: str
    score: float = 0.7

    @classmethod
    def from_payload(cls, payload: Any) -> "SignalInput":
        if isinstance(payload, dict):
            entity = str(payload.get("entity", "")).strip()
            return cls(entity=entity, score=clamp_score(payload.get("score", 0.7), default=0.7))
        return cls(entity=str(payload).strip(), score=0.7)


@dataclass(slots=True)
class RecommendationRequest:
    text: str = ""
    signals: list[SignalInput] = field(default_factory=list)
    top_k: int = 5
    include_snapshot: bool = True

    @classmethod
    def from_payload(cls, payload: Any | None) -> "RecommendationRequest":
        if not isinstance(payload, dict):
            payload = {}
        raw_signals = payload.get("signals", [])
        signals: list[SignalInput] = []
        if isinstance(raw_signals, dict):
            signals = [SignalInput(entity=str(key), score=clamp_score(value, default=0.7)) for key, value in raw_signals.items()]
        elif isinstance(raw_signals, list):
            signals = [SignalInput.from_payload(item) for item in raw_signals]

        top_k = payload.get("top_k", 5)
        try:
            top_k = int(top_k)
        except (TypeError, ValueError):
            top_k = 5
        top_k = max(1, min(20, top_k))

        include_snapshot = coerce_bool(payload.get("include_snapshot", True), default=True)
        return cls(
            text=str(payload.get("text", "") or ""),
            signals=signals,
            top_k=top_k,
            include_snapshot=include_snapshot,
        )


@dataclass(slots=True)
class NormalizedSignal:
    node_id: str
    node_name: str
    score: float
    source: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class PathExplanation:
    score: float
    node_ids: list[str]
    labels: list[str]
    relations: list[str]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class RecommendationItem:
    job_id: str
    job_name: str
    score: float
    reason: str
    paths: list[PathExplanation]
    limitations: list[str]
    provenance_count: int = 0
    source_refs: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["paths"] = [path.as_dict() for path in self.paths]
        return payload
