from __future__ import annotations

import re
from dataclasses import dataclass

from ..schemas import NormalizedSignal
from .graph_loader import GraphData


@dataclass(slots=True, frozen=True)
class AliasPattern:
    node_id: str
    alias: str
    pattern: re.Pattern[str]


class LightweightNLParser:
    def __init__(self, graph: GraphData, aliases: dict[str, list[str]], preference_patterns: dict[str, list[str]]) -> None:
        self.graph = graph
        self.aliases = aliases
        self.preference_patterns = preference_patterns
        self.alias_patterns = self._build_alias_patterns()

    def _build_alias_patterns(self) -> list[AliasPattern]:
        patterns: list[AliasPattern] = []
        for node_id, values in self.aliases.items():
            for alias in sorted(values, key=len, reverse=True):
                if re.fullmatch(r"[a-z0-9.+#\- ]+", alias):
                    pattern = re.compile(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", flags=re.IGNORECASE)
                else:
                    pattern = re.compile(re.escape(alias), flags=re.IGNORECASE)
                patterns.append(AliasPattern(node_id=node_id, alias=alias, pattern=pattern))
        patterns.sort(key=lambda item: len(item.alias), reverse=True)
        return patterns

    def parse(self, text: str) -> tuple[list[NormalizedSignal], list[str]]:
        if not text.strip():
            return [], []

        found: dict[str, NormalizedSignal] = {}
        notes: list[str] = []
        lowered = text.lower()

        for alias_pattern in self.alias_patterns:
            node = self.graph.nodes.get(alias_pattern.node_id)
            if node is None:
                continue
            for match in alias_pattern.pattern.finditer(lowered):
                window = lowered[max(0, match.start() - 8) : min(len(lowered), match.end() + 8)]
                score = self._score_match(node.node_type, node.id, window)
                if score is None:
                    continue
                self._upsert(found, node.id, node.name, score, "natural_language")
                if node.id == "knowledge_math_foundation" and self._contains(window, "negative"):
                    self._upsert(found, "constraint_dislike_math_theory", self.graph.nodes["constraint_dislike_math_theory"].name, 0.82, "natural_language")
                notes.append(f"{alias_pattern.alias} -> {node.name} ({score:.2f})")

        return sorted(found.values(), key=lambda item: (-item.score, item.node_id)), notes

    def _score_match(self, node_type: str, node_id: str, window: str) -> float | None:
        if node_type == "project":
            if not any(keyword in window for keyword in ("项目", "做过", "实践", "负责", "写过", "经历")):
                return None
        has_negative = self._contains(window, "negative")
        if node_type == "interest":
            if has_negative:
                return None
            if not self._contains(window, "preference"):
                return None
            return 0.86
        if node_type == "constraint":
            return 0.85

        if has_negative:
            if node_id == "knowledge_math_foundation":
                return 0.22
            return None
        if self._contains(window, "strong_positive"):
            return 0.92
        if self._contains(window, "medium_positive"):
            return 0.78
        if self._contains(window, "weak_positive"):
            return 0.35
        if self._contains(window, "light_positive"):
            return 0.58
        if node_type == "project":
            return 0.75
        return 0.62

    def _contains(self, window: str, pattern_key: str) -> bool:
        return any(keyword in window for keyword in self.preference_patterns.get(pattern_key, []))

    @staticmethod
    def _upsert(
        found: dict[str, NormalizedSignal],
        node_id: str,
        node_name: str,
        score: float,
        source: str,
    ) -> None:
        current = found.get(node_id)
        if current is None or score > current.score:
            found[node_id] = NormalizedSignal(node_id=node_id, node_name=node_name, score=score, source=source)
