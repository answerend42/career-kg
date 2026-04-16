from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..schemas import (
    ActionSimulationRequest,
    LearningPathStep,
    NearMissItem,
    RecommendationItem,
    RecommendationRequest,
    RoleGapRequest,
)
from ..services.action_simulator import ActionSimulator
from ..services.action_template_matcher import ActionTemplateMatcher
from ..services.explainer import GraphExplainer
from ..services.graph_loader import GraphLoader
from ..services.inference_engine import InferenceEngine, NodeState
from ..services.input_normalizer import InputNormalizer
from ..services.learning_path_planner import LearningPathPlanner
from ..services.nl_parser import LightweightNLParser
from ..services.role_gap_analyzer import RoleGapAnalyzer


MIN_RECOMMENDATION_SCORE = 0.05
MIN_NEAR_MISS_SCORE = 0.05
MAX_NEAR_MISS_ITEMS = 4
DEMO_CASE_METADATA = {
    "sample_request": {
        "title": "系统示例：后端入门画像",
        "summary": "适合第一屏演示推荐、节点确认和传播图。",
        "tags": ["系统示例", "后端", "推荐演示"],
    },
    "backend_bundle_nl": {
        "title": "后端成长画像",
        "summary": "用自然语言直接演示后端目标岗位分析与双动作组合模拟。",
        "tags": ["自然语言", "后端", "组合模拟"],
    },
    "data_engineer_structured": {
        "title": "数据工程画像",
        "summary": "适合展示结构化信号如何触发数据工程成长路径。",
        "tags": ["结构化输入", "数据工程", "规划链路"],
    },
    "frontend_structured": {
        "title": "前端画像",
        "summary": "适合展示前端方向的推荐、差距分析和动作模板匹配。",
        "tags": ["结构化输入", "前端", "动作模板"],
    },
    "qa_nl": {
        "title": "质量保障画像",
        "summary": "适合演示 QA / 测试开发方向的差距分析与补齐建议。",
        "tags": ["自然语言", "QA", "补齐建议"],
    },
    "appsec_structured": {
        "title": "应用安全画像",
        "summary": "适合展示安全方向的前置能力和专项行动模板。",
        "tags": ["结构化输入", "安全", "前置能力"],
    },
    "devops_nl": {
        "title": "DevOps 画像",
        "summary": "适合演示基础能力补齐后如何重新拉动 DevOps 目标岗位。",
        "tags": ["自然语言", "DevOps", "规划回放"],
    },
}


class RecommendationService:
    def __init__(self, base_dir: Path | None = None) -> None:
        self.loader = GraphLoader(base_dir=base_dir)
        self.graph = self.loader.load_graph()
        self.aliases = self.loader.load_aliases()
        self.preference_patterns = self.loader.load_preference_patterns()
        self.parsing_patterns = self.loader.load_parsing_patterns()
        self.action_templates = self.loader.load_action_templates()
        self.normalizer = InputNormalizer(self.graph, self.aliases)
        self.nl_parser = LightweightNLParser(self.graph, self.aliases, self.preference_patterns, self.parsing_patterns)
        self.engine = InferenceEngine()
        self.explainer = GraphExplainer()
        self.role_gap_analyzer = RoleGapAnalyzer(self.graph, self.engine, self.explainer)
        self.learning_path_planner = LearningPathPlanner(self.graph, self.role_gap_analyzer)
        self.action_template_matcher = ActionTemplateMatcher(self.graph, self.action_templates)
        self.action_simulator = ActionSimulator(self.graph, self.engine, self.role_gap_analyzer)
        self.sample_request_path = self.loader.base_dir / "data" / "demo" / "sample_request.json"
        self.planning_benchmark_path = self.loader.base_dir / "data" / "demo" / "planning_benchmark.json"
        self.provenance_summary = self._build_provenance_summary()

    def recommend(self, payload: dict[str, Any] | None) -> dict[str, Any]:
        request = RecommendationRequest.from_payload(payload)
        merged_signals, unresolved, parse_result, score_map, states = self._resolve_request_context(
            request.text,
            request.signals,
        )
        ranked_roles = sorted(
            self.graph.role_ids,
            key=lambda node_id: (states[node_id].score, self.graph.nodes[node_id].name),
            reverse=True,
        )
        ranked_roles = [role_id for role_id in ranked_roles if states[role_id].score >= MIN_RECOMMENDATION_SCORE]
        selected_role_ids = ranked_roles[: request.top_k]

        recommendations: list[RecommendationItem] = []
        for role_id in selected_role_ids:
            recommendations.append(self._build_recommendation_item(states, role_id))

        near_miss_roles = self._build_near_miss_items(
            states,
            excluded_role_ids=set(selected_role_ids),
            limit=min(MAX_NEAR_MISS_ITEMS, max(2, request.top_k)),
        )

        return {
            "normalized_inputs": [item.as_dict() for item in merged_signals],
            "recommendations": [item.as_dict() for item in recommendations],
            "near_miss_roles": [item.as_dict() for item in near_miss_roles],
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

    def role_gap(self, payload: dict[str, Any] | None) -> dict[str, Any]:
        request = RoleGapRequest.from_payload(payload)
        if not request.target_role_id:
            raise ValueError("target_role_id is required")
        if request.target_role_id not in self.graph.role_ids:
            raise ValueError(f"unknown target role: {request.target_role_id}")

        merged_signals, unresolved, parse_result, score_map, states = self._resolve_request_context(
            request.text,
            request.signals,
        )
        analysis = self.role_gap_analyzer.analyze(
            states=states,
            score_map=score_map,
            target_role_id=request.target_role_id,
            source_payload=self._role_source_payload(request.target_role_id),
            scenario_limit=request.scenario_limit,
        )
        analysis.learning_path = self._build_learning_path(states, score_map, request.target_role_id)
        return {
            "target_role": analysis.as_dict(),
            "normalized_inputs": [item.as_dict() for item in merged_signals],
            "parsing_notes": parse_result.notes[:30],
            "parsing_debug": parse_result.debug,
            "unresolved_entities": unresolved,
        }

    def action_simulate(self, payload: dict[str, Any] | None) -> dict[str, Any]:
        request = ActionSimulationRequest.from_payload(payload)
        if not request.target_role_id:
            raise ValueError("target_role_id is required")
        if request.target_role_id not in self.graph.role_ids:
            raise ValueError(f"unknown target role: {request.target_role_id}")
        if not request.action_keys and not request.template_ids:
            raise ValueError("action_keys or template_ids is required")

        merged_signals, unresolved, parse_result, score_map, states = self._resolve_request_context(
            request.text,
            request.signals,
        )
        learning_path = self._build_learning_path(states, score_map, request.target_role_id)
        simulation = self.action_simulator.simulate(
            states=states,
            score_map=score_map,
            target_role_id=request.target_role_id,
            learning_path=learning_path,
            action_keys=request.action_keys,
            template_ids=request.template_ids,
        )
        return {
            "simulation": simulation.as_dict(),
            "normalized_inputs": [item.as_dict() for item in merged_signals],
            "parsing_notes": parse_result.notes[:30],
            "parsing_debug": parse_result.debug,
            "unresolved_entities": unresolved,
        }

    def _build_recommendation_item(self, states: dict[str, NodeState], role_id: str) -> RecommendationItem:
        paths = self.explainer.top_paths(self.graph, states, role_id, limit=3)
        source_payload = self._role_source_payload(role_id)
        return RecommendationItem(
            job_id=role_id,
            job_name=self.graph.nodes[role_id].name,
            score=states[role_id].score,
            reason=self.explainer.summarize_reason(self.graph, states, role_id, paths),
            paths=paths,
            limitations=self.explainer.limitations(states, role_id),
            **source_payload,
        )

    def _build_near_miss_items(
        self,
        states: dict[str, NodeState],
        excluded_role_ids: set[str],
        limit: int,
    ) -> list[NearMissItem]:
        candidates: list[tuple[float, float, str]] = []
        for role_id in self.graph.role_ids:
            if role_id in excluded_role_ids:
                continue
            near_miss_score = self._estimate_near_miss_score(states[role_id])
            if near_miss_score < MIN_NEAR_MISS_SCORE:
                continue
            candidates.append((near_miss_score, states[role_id].score, role_id))

        selected: list[NearMissItem] = []
        for near_miss_score, _, role_id in sorted(
            candidates,
            key=lambda item: (item[0], item[1], self.graph.nodes[item[2]].name),
            reverse=True,
        )[:limit]:
            suggestions = self.role_gap_analyzer.build_gap_suggestions(states, role_id)
            paths = self.explainer.top_paths(self.graph, states, role_id, limit=2)
            source_payload = self._role_source_payload(role_id)
            selected.append(
                NearMissItem(
                    job_id=role_id,
                    job_name=self.graph.nodes[role_id].name,
                    near_miss_score=near_miss_score,
                    score=states[role_id].score,
                    gap_summary=self.explainer.summarize_gap(
                        self.graph,
                        states,
                        role_id,
                        paths,
                        [item.node_name for item in suggestions],
                    ),
                    paths=paths,
                    limitations=self.explainer.limitations(states, role_id),
                    missing_requirements=list(states[role_id].diagnostics.get("missing_requirements", [])),
                    suggestions=suggestions,
                    **source_payload,
                )
            )
        return selected

    def _estimate_near_miss_score(self, state: NodeState) -> float:
        diagnostics = state.diagnostics
        support_total = float(diagnostics.get("support_total", 0.0) or 0.0)
        require_total = float(diagnostics.get("require_total", 0.0) or 0.0)
        prefer_total = float(diagnostics.get("prefer_total", 0.0) or 0.0)
        inhibit_total = float(diagnostics.get("inhibit_total", 0.0) or 0.0)
        near_miss_score = max(
            state.score,
            support_total + require_total + prefer_total * 0.6 - inhibit_total * 0.25,
        )
        if diagnostics.get("missing_requirements"):
            near_miss_score += 0.015
        return round(max(0.0, min(1.0, near_miss_score)), 4)

    def _role_source_payload(self, role_id: str) -> dict[str, Any]:
        return {
            "provenance_count": int(self.graph.nodes[role_id].metadata.get("provenance_count", 0) or 0),
            "source_type_count": int(self.graph.nodes[role_id].metadata.get("source_type_count", 0) or 0),
            "source_types": [
                str(source_type)
                for source_type in self.graph.nodes[role_id].metadata.get("source_types", [])
                if str(source_type).strip()
            ],
            "source_refs": self._normalize_source_refs(self.graph.nodes[role_id].metadata.get("source_refs", [])),
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
        role_nodes = [
            {
                "id": node_id,
                "name": node.name,
                "node_type": node.node_type,
                "description": node.description,
            }
            for node_id, node in sorted(
                self.graph.nodes.items(),
                key=lambda item: item[1].name,
            )
            if node.layer == "role"
        ]
        return {
            "evidence_nodes": evidence_nodes,
            "role_nodes": role_nodes,
            "graph_stats": {
                "node_count": len(self.graph.nodes),
                "edge_count": len(self.graph.edges),
                "evidence_node_count": len(self.graph.evidence_ids),
                "role_count": len(self.graph.role_ids),
                **self.provenance_summary,
            },
            "sample_request": self.sample_request(),
            "demo_cases": self.demo_cases(),
        }

    def sample_request(self) -> dict[str, Any]:
        return json.loads(self.sample_request_path.read_text(encoding="utf-8"))

    def demo_cases(self) -> list[dict[str, Any]]:
        cases: list[dict[str, Any]] = []
        sample_request = self.sample_request()
        cases.append(
            self._build_demo_case_payload(
                case_id="sample_request",
                text=str(sample_request.get("text", "") or ""),
                signals=sample_request.get("signals", []),
                target_role_id="role_backend_engineer",
                source="sample_request",
            )
        )

        if not self.planning_benchmark_path.exists():
            return cases

        for raw_case in json.loads(self.planning_benchmark_path.read_text(encoding="utf-8")):
            if not isinstance(raw_case, dict):
                continue
            target_role_id = str(raw_case.get("target_role_id", "") or "").strip()
            if not target_role_id or target_role_id not in self.graph.role_ids:
                continue
            cases.append(
                self._build_demo_case_payload(
                    case_id=str(raw_case.get("id", "") or "").strip() or target_role_id,
                    text=str(raw_case.get("text", "") or ""),
                    signals=raw_case.get("signals", []),
                    target_role_id=target_role_id,
                    source="planning_benchmark",
                )
            )
        return cases

    def _resolve_request_context(
        self,
        text: str,
        signals: list[Any],
    ) -> tuple[list[Any], list[str], Any, dict[str, float], dict[str, NodeState]]:
        structured_signals, unresolved = self.normalizer.normalize_signals(signals)
        parse_result = self.nl_parser.parse_detailed(text)
        merged_signals = self.normalizer.merge_signals(parse_result.signals, structured_signals)
        score_map = self.normalizer.to_score_map(merged_signals)
        states = self.engine.run(self.graph, score_map)
        return merged_signals, unresolved, parse_result, score_map, states

    def _build_learning_path(
        self,
        states: dict[str, NodeState],
        score_map: dict[str, float],
        target_role_id: str,
    ) -> list[LearningPathStep]:
        steps = self.learning_path_planner.plan(
            states=states,
            score_map=score_map,
            target_role_id=target_role_id,
        )
        return self.action_template_matcher.attach_actions(
            steps=steps,
            target_role_id=target_role_id,
        )

    def _build_provenance_summary(self) -> dict[str, Any]:
        unique_profiles: dict[str, dict[str, Any]] = {}
        nodes_with_provenance = 0
        latest_snapshot_date = ""

        for node in self.graph.nodes.values():
            refs = self._normalize_source_refs(node.metadata.get("source_refs", []))
            if refs:
                nodes_with_provenance += 1
            for ref in refs:
                profile_key = ref["profile_id"] or f"{ref['source_type']}::{ref['source_id']}"
                unique_profiles.setdefault(profile_key, ref)
                if ref["snapshot_date"] and ref["snapshot_date"] > latest_snapshot_date:
                    latest_snapshot_date = ref["snapshot_date"]

        source_profile_count_by_type: dict[str, int] = {}
        for ref in unique_profiles.values():
            if ref["source_type"]:
                source_profile_count_by_type[ref["source_type"]] = source_profile_count_by_type.get(ref["source_type"], 0) + 1

        return {
            "source_profile_count": len(unique_profiles),
            "nodes_with_provenance": nodes_with_provenance,
            "source_types": sorted(source_profile_count_by_type),
            "source_type_count": len(source_profile_count_by_type),
            "source_profile_count_by_type": {
                source_type: source_profile_count_by_type[source_type]
                for source_type in sorted(source_profile_count_by_type)
            },
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

    def _build_demo_case_payload(
        self,
        case_id: str,
        text: str,
        signals: Any,
        target_role_id: str,
        source: str,
    ) -> dict[str, Any]:
        normalized_signals: list[dict[str, Any]] = []
        if isinstance(signals, list):
            for signal in signals:
                if not isinstance(signal, dict):
                    continue
                entity = str(signal.get("entity", "") or "").strip()
                if not entity:
                    continue
                normalized_signals.append(
                    {
                        "entity": entity,
                        "score": float(signal.get("score", 0.7) or 0.7),
                    }
                )

        metadata = DEMO_CASE_METADATA.get(case_id, {})
        target_role_name = self.graph.nodes[target_role_id].name if target_role_id in self.graph.role_ids else target_role_id
        preview = text.strip()
        if not preview and normalized_signals:
            preview = "结构化信号：" + "、".join(
                f"{item['entity']} {item['score']:.2f}"
                for item in normalized_signals[:3]
            )
        if len(preview) > 88:
            preview = preview[:85].rstrip() + "..."

        return {
            "id": case_id,
            "title": metadata.get("title", target_role_name),
            "summary": metadata.get("summary", f"目标岗位：{target_role_name}"),
            "tags": metadata.get("tags", [source, target_role_name])[:4],
            "source": source,
            "text": text,
            "signals": normalized_signals,
            "signal_count": len(normalized_signals),
            "target_role_id": target_role_id,
            "target_role_name": target_role_name,
            "preview": preview,
        }

    def _serialize_node_metadata(self, node_id: str) -> dict[str, Any]:
        node = self.graph.nodes[node_id]
        metadata = dict(node.metadata)
        metadata["source_refs"] = self._normalize_source_refs(metadata.get("source_refs", []))
        metadata["provenance_count"] = int(metadata.get("provenance_count", len(metadata["source_refs"])) or 0)
        metadata["source_types"] = [
            str(source_type)
            for source_type in metadata.get("source_types", [])
            if str(source_type).strip()
        ]
        metadata["source_type_count"] = int(metadata.get("source_type_count", len(metadata["source_types"])) or 0)
        metadata["latest_snapshot_date"] = str(metadata.get("latest_snapshot_date", ""))
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
