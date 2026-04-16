#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

EVIDENCE_NODE_TYPES = {
    "skill": "skill",
    "tool": "skill",
    "knowledge": "knowledge",
    "project": "project",
    "interest": "interest",
    "soft_skill": "soft_skill",
    "constraint": "constraint",
}

NODE_TYPES = [
    {
        "id": "skill",
        "layer": "evidence",
        "default_aggregator": "source",
        "description": "技能或工具证据，直接由用户输入或解析得到。",
    },
    {
        "id": "knowledge",
        "layer": "evidence",
        "default_aggregator": "source",
        "description": "课程、理论基础或通用知识证据。",
    },
    {
        "id": "project",
        "layer": "evidence",
        "default_aggregator": "source",
        "description": "项目经历、实践场景或工作方式证据。",
    },
    {
        "id": "interest",
        "layer": "evidence",
        "default_aggregator": "source",
        "description": "兴趣偏好、工作倾向或主观选择。",
    },
    {
        "id": "constraint",
        "layer": "evidence",
        "default_aggregator": "source",
        "description": "明确短板或负向偏好，用于抑制相关方向。",
    },
    {
        "id": "soft_skill",
        "layer": "evidence",
        "default_aggregator": "source",
        "description": "沟通、协作、文档等软技能证据。",
    },
    {
        "id": "ability_unit",
        "layer": "ability",
        "default_aggregator": "weighted_sum_capped",
        "description": "由原子证据聚合得到的基础能力单元。",
    },
    {
        "id": "compound_capability",
        "layer": "composite",
        "default_aggregator": "soft_and",
        "description": "由多个能力单元共同组成的复合能力。",
    },
    {
        "id": "career_direction",
        "layer": "direction",
        "default_aggregator": "penalty_gate",
        "description": "岗位方向或能力簇，连接复合能力与具体职业。",
    },
    {
        "id": "career_role",
        "layer": "role",
        "default_aggregator": "hard_gate",
        "description": "最终推荐的具体职业节点。",
    },
]

EDGE_TYPES = [
    {
        "id": "supports",
        "sign": "positive",
        "description": "常规正向支持，边权表示对目标节点的贡献力度。",
        "explainable": True,
    },
    {
        "id": "requires",
        "sign": "positive",
        "description": "关键前置关系，会触发门槛或惩罚机制。",
        "explainable": True,
    },
    {
        "id": "prefers",
        "sign": "positive",
        "description": "兴趣或偏好的软加成关系，不单独构成硬门槛。",
        "explainable": True,
    },
    {
        "id": "inhibits",
        "sign": "negative",
        "description": "抑制关系，表示明显短板或负向偏好会压低目标节点。",
        "explainable": True,
    },
    {
        "id": "evidences",
        "sign": "positive",
        "description": "项目、课程等实践性证据，为目标节点提供额外可信度。",
        "explainable": True,
    },
]


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def default_note(target_name: str, relation: str) -> str:
    templates = {
        "supports": f"该节点正向支撑 {target_name}。",
        "requires": f"{target_name} 依赖该关键前置。",
        "prefers": f"该偏好会抬升 {target_name}。",
        "evidences": f"该项目或经历为 {target_name} 提供额外证据。",
        "inhibits": f"该约束会抑制 {target_name}。",
    }
    return templates[relation]


class GraphBuilder:
    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = base_dir or ROOT
        self.sources_dir = self.base_dir / "data" / "sources"
        self.ontology_dir = self.base_dir / "data" / "ontology"
        self.seeds_dir = self.base_dir / "data" / "seeds"
        self.dictionaries_dir = self.base_dir / "data" / "dictionaries"
        self.demo_dir = self.base_dir / "data" / "demo"

        self.nodes: list[dict[str, Any]] = []
        self.edges: list[dict[str, Any]] = []
        self.aliases: dict[str, set[str]] = {}
        self.node_ids: set[str] = set()
        self.edge_keys: set[tuple[str, str, str]] = set()
        self.node_layers: dict[str, str] = {}
        self.imported_refs_by_node: dict[str, list[dict[str, Any]]] = {}
        self.imported_profile_ids: set[str] = set()

    def build(self) -> dict[str, int]:
        skills = load_json(self.sources_dir / "skills.json")
        templates = load_json(self.sources_dir / "capability_templates.json")
        roles = load_json(self.sources_dir / "roles.json")
        relations = load_json(self.sources_dir / "relations.json")
        alias_overrides = load_json(self.sources_dir / "aliases.json")
        sample_request = load_json(self.sources_dir / "sample_request.json")
        parsing_patterns = load_json(self.sources_dir / "parsing_patterns.json")
        nl_benchmark = load_json(self.sources_dir / "nl_benchmark.json")
        recommendation_benchmark = load_json(self.sources_dir / "recommendation_benchmark.json")
        planning_benchmark = load_json(self.sources_dir / "planning_benchmark.json")
        action_templates = load_json(self.sources_dir / "action_templates.json")
        imported_profiles_path = self.sources_dir / "imported_profiles.json"
        imported_profiles = load_json(imported_profiles_path) if imported_profiles_path.exists() else []

        for path in [self.ontology_dir, self.seeds_dir, self.dictionaries_dir, self.demo_dir]:
            ensure_dir(path)

        self._index_imported_profiles(imported_profiles)
        self._compile_evidence(skills)
        self._compile_templates(templates, relations)
        self._compile_standalone_roles(roles.get("standalone_roles", []), relations)
        self._compile_specializations(roles.get("specializations", []), relations)
        self._merge_alias_overrides(alias_overrides.get("extra_aliases", {}))

        missing_import_targets = sorted(set(self.imported_refs_by_node) - self.node_ids)
        if missing_import_targets:
            raise ValueError(f"imported profiles reference unknown node ids: {missing_import_targets[:12]}")

        write_json(self.ontology_dir / "node_types.json", NODE_TYPES)
        write_json(self.ontology_dir / "edge_types.json", EDGE_TYPES)
        write_json(self.seeds_dir / "nodes.json", self.nodes)
        write_json(self.seeds_dir / "edges.json", self.edges)
        write_json(
            self.dictionaries_dir / "skill_aliases.json",
            {node_id: sorted(values) for node_id, values in sorted(self.aliases.items())},
        )
        write_json(self.dictionaries_dir / "preference_patterns.json", relations["preference_patterns"])
        write_json(self.dictionaries_dir / "parsing_patterns.json", parsing_patterns)
        write_json(self.demo_dir / "sample_request.json", sample_request)
        write_json(self.demo_dir / "nl_benchmark.json", nl_benchmark)
        write_json(self.demo_dir / "recommendation_benchmark.json", recommendation_benchmark)
        write_json(self.demo_dir / "planning_benchmark.json", planning_benchmark)
        write_json(self.demo_dir / "action_templates.json", action_templates)

        return {
            "nodes": len(self.nodes),
            "edges": len(self.edges),
            "aliases": len(self.aliases),
            "imported_profiles": len(self.imported_profile_ids),
            "nodes_with_provenance": sum(1 for node in self.nodes if node.get("metadata", {}).get("source_refs")),
        }

    def _index_imported_profiles(self, profiles: list[dict[str, Any]]) -> None:
        for profile in profiles:
            profile_id = str(profile["profile_id"])
            self.imported_profile_ids.add(profile_id)
            source_ref = {
                "profile_id": profile_id,
                "source_type": profile["source_type"],
                "source_id": profile["source_id"],
                "source_title": profile["source_title"],
                "source_url": profile["source_url"],
                "snapshot_date": profile["snapshot_date"],
                "evidence_snippet": profile["evidence_snippet"],
                "sample_job_titles": profile.get("sample_job_titles", [])[:4],
            }
            for node_id in profile.get("mapped_node_ids", []):
                self.imported_refs_by_node.setdefault(node_id, []).append(source_ref)
        for node_id, source_refs in list(self.imported_refs_by_node.items()):
            self.imported_refs_by_node[node_id] = self._dedupe_and_sort_source_refs(source_refs)

    def _dedupe_and_sort_source_refs(self, source_refs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        deduped: dict[str, dict[str, Any]] = {}
        for source_ref in source_refs:
            profile_id = str(source_ref.get("profile_id", ""))
            if not profile_id:
                continue
            deduped[profile_id] = source_ref
        return sorted(
            deduped.values(),
            key=lambda item: (
                str(item.get("source_type", "")),
                str(item.get("source_title", "")),
                str(item.get("profile_id", "")),
            ),
        )

    def _source_metadata_for_node(self, node_id: str) -> dict[str, Any]:
        source_refs = self.imported_refs_by_node.get(node_id, [])
        if not source_refs:
            return {}
        source_types = sorted({str(source_ref.get("source_type", "")) for source_ref in source_refs if source_ref.get("source_type")})
        latest_snapshot_date = max((str(source_ref.get("snapshot_date", "")) for source_ref in source_refs), default="")
        return {
            "source_refs": source_refs,
            "provenance_count": len(source_refs),
            "source_types": source_types,
            "source_type_count": len(source_types),
            "latest_snapshot_date": latest_snapshot_date,
        }

    def _compile_evidence(self, skills: dict[str, list[dict[str, Any]]]) -> None:
        for category, specs in skills.items():
            node_type = EVIDENCE_NODE_TYPES[category]
            for spec in specs:
                self.add_node(
                    node_id=spec["id"],
                    name=spec["name"],
                    layer="evidence",
                    node_type=node_type,
                    aggregator="source",
                    description=spec.get("description", f"{spec['name']} 相关证据。"),
                    params=spec.get("params", {}),
                    aliases=spec.get("aliases", []),
                    metadata={"source_file": "skills.json", "category": category, "origin": spec.get("origin", "seed")},
                )

    def _compile_templates(self, templates: dict[str, list[dict[str, Any]]], relations: dict[str, Any]) -> None:
        layer_defaults = relations["layer_defaults"]
        for spec in templates.get("abilities", []):
            self._compile_template_node(spec, "ability", "ability_unit", "weighted_sum_capped", layer_defaults["ability"], "capability_templates.json")
        for spec in templates.get("composites", []):
            self._compile_template_node(spec, "composite", "compound_capability", "soft_and", layer_defaults["composite"], "capability_templates.json")
        for spec in templates.get("directions", []):
            self._compile_template_node(spec, "direction", "career_direction", "penalty_gate", layer_defaults["direction"], "capability_templates.json")

    def _compile_template_node(
        self,
        spec: dict[str, Any],
        layer: str,
        node_type: str,
        default_aggregator: str,
        default_weights: dict[str, float],
        source_file: str,
    ) -> None:
        self.add_node(
            node_id=spec["id"],
            name=spec["name"],
            layer=layer,
            node_type=node_type,
            aggregator=spec.get("aggregator", default_aggregator),
            description=spec.get("description", f"{spec['name']}。"),
            params=spec.get("params", {}),
            aliases=spec.get("aliases", []),
            metadata={"source_file": source_file, "template_group": layer},
        )
        self._add_relation_bundle(
            target_id=spec["id"],
            target_name=spec["name"],
            source_file=source_file,
            relation_sources={relation: spec.get(relation, []) for relation in ("supports", "requires", "prefers", "evidences", "inhibits")},
            weights=spec.get("weights", {}),
            default_weights=default_weights,
        )

    def _compile_standalone_roles(self, roles: list[dict[str, Any]], relations: dict[str, Any]) -> None:
        default_weights = relations["layer_defaults"]["role"]
        for spec in roles:
            self.add_node(
                node_id=spec["id"],
                name=spec["name"],
                layer="role",
                node_type="career_role",
                aggregator=spec.get("aggregator", "hard_gate"),
                description=spec.get("description", f"{spec['name']}，最终推荐岗位节点。"),
                params=spec.get("params", {"cap": 1.0, "required_threshold": 0.025}),
                aliases=spec.get("aliases", []),
                metadata={"source_file": "roles.json", "role_kind": "standalone", "family": spec.get("family", "standalone")},
            )
            relation_sources = {
                "supports": [spec["direction_id"], spec["capability_id"], *spec.get("supports", [])],
                "requires": [spec["capability_id"], *spec.get("requires", [])],
                "prefers": spec.get("prefers", []),
                "evidences": spec.get("evidences", []),
                "inhibits": spec.get("inhibits", []),
            }
            self._add_relation_bundle(spec["id"], spec["name"], "roles.json", relation_sources, spec.get("weights", {}), default_weights)

    def _compile_specializations(self, specs: list[dict[str, Any]], relations: dict[str, Any]) -> None:
        defaults = relations["layer_defaults"]
        role_defaults = relations["specialization_defaults"]
        for spec in specs:
            family = spec.get("family", "specialization")

            self.add_node(
                node_id=spec["stack_ability_id"],
                name=spec["stack_ability_name"],
                layer="ability",
                node_type="ability_unit",
                aggregator=spec.get("stack_ability_aggregator", role_defaults["stack_ability"]["aggregator"]),
                description=spec.get("stack_ability_description", f"{spec['stack_ability_name']}。"),
                params=spec.get("stack_ability_params", role_defaults["stack_ability"]["params"]),
                aliases=spec.get("stack_ability_aliases", []),
                metadata={"source_file": "roles.json", "role_kind": "specialization", "family": family, "stage": "stack_ability"},
            )
            self._add_relation_bundle(
                spec["stack_ability_id"],
                spec["stack_ability_name"],
                "roles.json",
                {
                    "supports": spec.get("stack_supports", []),
                    "requires": spec.get("stack_requires", []),
                    "prefers": spec.get("stack_prefers", []),
                    "evidences": spec.get("stack_evidences", []),
                    "inhibits": spec.get("stack_inhibits", []),
                },
                spec.get("stack_weights", {}),
                defaults["stack_ability"],
            )

            capability_supports = [spec["stack_ability_id"], spec["base_capability_id"], *spec.get("capability_supports", [])]
            capability_requires = [spec["stack_ability_id"], *spec.get("capability_requires", [])]
            self.add_node(
                node_id=spec["capability_id"],
                name=spec["capability_name"],
                layer="composite",
                node_type="compound_capability",
                aggregator=spec.get("capability_aggregator", role_defaults["stack_capability"]["aggregator"]),
                description=spec.get("capability_description", f"{spec['capability_name']}。"),
                params=spec.get("capability_params", role_defaults["stack_capability"]["params"]),
                aliases=spec.get("capability_aliases", []),
                metadata={"source_file": "roles.json", "role_kind": "specialization", "family": family, "stage": "capability"},
            )
            self._add_relation_bundle(
                spec["capability_id"],
                spec["capability_name"],
                "roles.json",
                {
                    "supports": capability_supports,
                    "requires": capability_requires,
                    "prefers": spec.get("capability_prefers", spec.get("role_prefers", [])),
                    "evidences": spec.get("capability_evidences", []),
                    "inhibits": spec.get("capability_inhibits", spec.get("role_inhibits", [])),
                },
                spec.get("capability_weights", {}),
                defaults["stack_capability"],
            )

            role_supports = [spec["direction_id"], spec["capability_id"], *spec.get("role_supports", [])]
            role_requires = [spec["capability_id"], *spec.get("role_requires", [])]
            self.add_node(
                node_id=spec["role_id"],
                name=spec["role_name"],
                layer="role",
                node_type="career_role",
                aggregator=spec.get("role_aggregator", role_defaults["role"]["aggregator"]),
                description=spec.get("description", f"{spec['role_name']}，最终推荐岗位节点。"),
                params=spec.get("role_params", role_defaults["role"]["params"]),
                aliases=spec.get("aliases", []),
                metadata={"source_file": "roles.json", "role_kind": "specialization", "family": family, "stage": "role"},
            )
            self._add_relation_bundle(
                spec["role_id"],
                spec["role_name"],
                "roles.json",
                {
                    "supports": role_supports,
                    "requires": role_requires,
                    "prefers": spec.get("role_prefers", []),
                    "evidences": spec.get("role_evidences", []),
                    "inhibits": spec.get("role_inhibits", []),
                },
                spec.get("role_weights", {}),
                defaults["role"],
            )

    def _merge_alias_overrides(self, extra_aliases: dict[str, list[str]]) -> None:
        for node_id, values in extra_aliases.items():
            alias_bucket = self.aliases.setdefault(node_id, set())
            alias_bucket.update(alias.lower() for alias in values)

    def _add_relation_bundle(
        self,
        target_id: str,
        target_name: str,
        source_file: str,
        relation_sources: dict[str, list[str]],
        weights: dict[str, float],
        default_weights: dict[str, float],
    ) -> None:
        for relation, source_ids in relation_sources.items():
            if not source_ids:
                continue
            weight = float(weights.get(relation, default_weights[relation]))
            note = default_note(target_name, relation)
            for source_id in source_ids:
                self.add_edge(
                    source=source_id,
                    target=target_id,
                    relation=relation,
                    weight=weight,
                    note=note,
                    metadata={"source_file": source_file, "relation_group": relation},
                )

    def add_node(
        self,
        node_id: str,
        name: str,
        layer: str,
        node_type: str,
        aggregator: str,
        description: str,
        params: dict[str, Any],
        aliases: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if node_id in self.node_ids:
            raise ValueError(f"duplicate node id detected: {node_id}")
        self.node_ids.add(node_id)
        self.node_layers[node_id] = layer
        merged_metadata = {"origin": "curated", **(metadata or {})}
        source_metadata = self._source_metadata_for_node(node_id)
        if source_metadata:
            merged_metadata.update(source_metadata)
            merged_metadata["origin"] = "curated+imported"
        self.nodes.append(
            {
                "id": node_id,
                "name": name,
                "layer": layer,
                "node_type": node_type,
                "aggregator": aggregator,
                "description": description,
                "params": params,
                "metadata": merged_metadata,
            }
        )
        alias_bucket = self.aliases.setdefault(node_id, set())
        alias_bucket.add(name.lower())
        if aliases:
            alias_bucket.update(alias.lower() for alias in aliases)

    def add_edge(
        self,
        source: str,
        target: str,
        relation: str,
        weight: float,
        note: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        edge_key = (source, target, relation)
        if edge_key in self.edge_keys:
            return
        self.edge_keys.add(edge_key)
        merged_metadata = dict(metadata or {})
        source_metadata = self._source_metadata_for_node(target)
        if source_metadata and self.node_layers.get(target) in {"role", "direction", "composite"}:
            merged_metadata.update(source_metadata)
        self.edges.append(
            {
                "source": source,
                "target": target,
                "relation": relation,
                "weight": weight,
                "note": note,
                "metadata": merged_metadata,
            }
        )


def build_all(base_dir: Path | None = None) -> dict[str, int]:
    builder = GraphBuilder(base_dir=base_dir)
    return builder.build()


def main() -> None:
    summary = build_all()
    print(
        f"generated {summary['nodes']} nodes and {summary['edges']} edges "
        f"({summary['imported_profiles']} imported profiles, {summary['nodes_with_provenance']} nodes with provenance)"
    )


if __name__ == "__main__":
    main()
