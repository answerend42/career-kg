from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..schemas import RecommendationItem, RecommendationRequest
from ..services.explainer import GraphExplainer
from ..services.graph_loader import GraphLoader
from ..services.inference_engine import InferenceEngine
from ..services.input_normalizer import InputNormalizer
from ..services.nl_parser import LightweightNLParser


MIN_RECOMMENDATION_SCORE = 0.05


class RecommendationService:
    def __init__(self, base_dir: Path | None = None) -> None:
        self.loader = GraphLoader(base_dir=base_dir)
        self.graph = self.loader.load_graph()
        self.aliases = self.loader.load_aliases()
        self.preference_patterns = self.loader.load_preference_patterns()
        self.parsing_patterns = self.loader.load_parsing_patterns()
        self.normalizer = InputNormalizer(self.graph, self.aliases)
        self.nl_parser = LightweightNLParser(self.graph, self.aliases, self.preference_patterns, self.parsing_patterns)
        self.engine = InferenceEngine()
        self.explainer = GraphExplainer()
        self.sample_request_path = self.loader.base_dir / "data" / "demo" / "sample_request.json"
        self.provenance_summary = self._build_provenance_summary()

    def recommend(self, payload: dict[str, Any] | None) -> dict[str, Any]:
        request = RecommendationRequest.from_payload(payload)
        structured_signals, unresolved = self.normalizer.normalize_signals(request.signals)
        parse_result = self.nl_parser.parse_detailed(request.text)
        merged_signals = self.normalizer.merge_signals(parse_result.signals, structured_signals)
        score_map = self.normalizer.to_score_map(merged_signals)

        states = self.engine.run(self.graph, score_map)
        ranked_roles = sorted(
            self.graph.role_ids,
            key=lambda node_id: (states[node_id].score, self.graph.nodes[node_id].name),
            reverse=True,
        )
        ranked_roles = [role_id for role_id in ranked_roles if states[role_id].score >= MIN_RECOMMENDATION_SCORE]

        recommendations: list[RecommendationItem] = []
        for role_id in ranked_roles[: request.top_k]:
            paths = self.explainer.top_paths(self.graph, states, role_id, limit=3)
            recommendations.append(
                RecommendationItem(
                    job_id=role_id,
                    job_name=self.graph.nodes[role_id].name,
                    score=states[role_id].score,
                    reason=self.explainer.summarize_reason(self.graph, states, role_id, paths),
                    paths=paths,
                    limitations=self.explainer.limitations(states, role_id),
                    provenance_count=int(self.graph.nodes[role_id].metadata.get("provenance_count", 0) or 0),
                    source_refs=self._normalize_source_refs(self.graph.nodes[role_id].metadata.get("source_refs", [])),
                )
            )

        return {
            "normalized_inputs": [item.as_dict() for item in merged_signals],
            "recommendations": [item.as_dict() for item in recommendations],
            "propagation_snapshot": self._build_snapshot(states) if request.include_snapshot else None,
            "parsing_notes": parse_result.notes[:30],
            "parsing_debug": parse_result.debug,
            "unresolved_entities": unresolved,
            "graph_stats": {
                "node_count": len(self.graph.nodes),
                "edge_count": len(self.graph.edges),
                "activated_node_count": sum(1 for state in states.values() if state.score >= 0.05),
                **self.provenance_summary,
            },
        }

    def catalog(self) -> dict[str, Any]:
        evidence_nodes = [
            {
                "id": node_id,
                "name": node.name,
                "node_type": node.node_type,
                "description": node.description,
                "aliases": self.aliases.get(node_id, []),
            }
            for node_id, node in sorted(
                self.graph.nodes.items(),
                key=lambda item: (item[1].layer, item[1].node_type, item[1].name),
            )
            if node.layer == "evidence"
        ]
        return {
            "evidence_nodes": evidence_nodes,
            "graph_stats": {
                "node_count": len(self.graph.nodes),
                "edge_count": len(self.graph.edges),
                "evidence_node_count": len(self.graph.evidence_ids),
                "role_count": len(self.graph.role_ids),
                **self.provenance_summary,
            },
            "sample_request": self.sample_request(),
        }

    def sample_request(self) -> dict[str, Any]:
        return json.loads(self.sample_request_path.read_text(encoding="utf-8"))

    def _build_provenance_summary(self) -> dict[str, Any]:
        unique_profiles: dict[str, dict[str, Any]] = {}
        source_type_counts: dict[str, int] = {}
        nodes_with_provenance = 0
        latest_snapshot_date = ""

        for node in self.graph.nodes.values():
            refs = self._normalize_source_refs(node.metadata.get("source_refs", []))
            if refs:
                nodes_with_provenance += 1
            for ref in refs:
                profile_key = ref["profile_id"] or f"{ref['source_type']}::{ref['source_id']}"
                unique_profiles.setdefault(profile_key, ref)
                if ref["source_type"]:
                    source_type_counts[ref["source_type"]] = source_type_counts.get(ref["source_type"], 0) + 1
                if ref["snapshot_date"] and ref["snapshot_date"] > latest_snapshot_date:
                    latest_snapshot_date = ref["snapshot_date"]

        return {
            "source_profile_count": len(unique_profiles),
            "nodes_with_provenance": nodes_with_provenance,
            "source_types": sorted(source_type_counts),
            "latest_snapshot_date": latest_snapshot_date,
        }

    def _normalize_source_refs(self, raw_refs: Any) -> list[dict[str, Any]]:
        if not isinstance(raw_refs, list):
            return []

        refs: list[dict[str, Any]] = []
        for ref in raw_refs:
            if not isinstance(ref, dict):
                continue
            sample_job_titles = ref.get("sample_job_titles", [])
            refs.append(
                {
                    "profile_id": str(ref.get("profile_id", "")),
                    "source_type": str(ref.get("source_type", "")),
                    "source_id": str(ref.get("source_id", "")),
                    "source_title": str(ref.get("source_title", "")),
                    "source_url": str(ref.get("source_url", "")),
                    "snapshot_date": str(ref.get("snapshot_date", "")),
                    "evidence_snippet": str(ref.get("evidence_snippet", "")),
                    "sample_job_titles": [
                        str(title)
                        for title in sample_job_titles
                        if str(title).strip()
                    ][:6],
                }
            )

        refs.sort(key=lambda item: (item["source_type"], item["source_title"], item["profile_id"]))
        return refs

    def _serialize_node_metadata(self, node_id: str) -> dict[str, Any]:
        node = self.graph.nodes[node_id]
        metadata = dict(node.metadata)
        metadata["source_refs"] = self._normalize_source_refs(metadata.get("source_refs", []))
        metadata["provenance_count"] = int(metadata.get("provenance_count", len(metadata["source_refs"])) or 0)
        return metadata

    def _build_snapshot(self, states: dict[str, Any]) -> dict[str, Any]:
        nodes = [
            {
                "id": node_id,
                "name": self.graph.nodes[node_id].name,
                "layer": self.graph.nodes[node_id].layer,
                "node_type": self.graph.nodes[node_id].node_type,
                "description": self.graph.nodes[node_id].description,
                "score": state.score,
                "aggregator": self.graph.nodes[node_id].aggregator,
                "metadata": self._serialize_node_metadata(node_id),
                "diagnostics": state.diagnostics,
            }
            for node_id, state in sorted(
                states.items(),
                key=lambda item: (item[1].score, item[0]),
                reverse=True,
            )
            if state.score >= 0.05
        ]

        edges = []
        for target_id, state in states.items():
            if state.score < 0.05:
                continue
            for contribution in state.parent_contributions:
                if contribution.value < 0.05:
                    continue
                edges.append(
                    {
                        "source": contribution.parent_id,
                        "target": target_id,
                        "relation": contribution.relation,
                        "value": contribution.value,
                        "note": contribution.note,
                    }
                )
        edges.sort(key=lambda item: item["value"], reverse=True)
        return {"nodes": nodes, "edges": edges[:200]}


def recommend_from_payload(payload: dict[str, Any] | None, base_dir: Path | None = None) -> dict[str, Any]:
    service = RecommendationService(base_dir=base_dir)
    return service.recommend(payload)
