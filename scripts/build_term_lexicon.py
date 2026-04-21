#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from normalize_raw_documents import ROOT, PIPELINE_DATE, PIPELINE_VERSION, normalized_key, read_json, stable_id, write_json


NODES_PATH = ROOT / "data" / "seeds" / "nodes.json"
ALIASES_PATH = ROOT / "data" / "dictionaries" / "skill_aliases.json"
RAW_DIR = ROOT / "data" / "sources" / "raw"
DEFAULT_OUTPUT = ROOT / "data" / "canonical" / "term_lexicon.json"


SOURCE_PRIORITY = {
    "seed_node_name": 1,
    "seed_alias": 2,
    "external_profile_title": 3,
    "external_job_title": 4,
    "external_profile_tag": 5,
    "rule_expansion": 6,
}


def concept_type_for_node(node: dict[str, Any]) -> str:
    layer = str(node.get("layer", ""))
    node_type = str(node.get("node_type", ""))
    if layer == "role":
        return "occupation_internal"
    if layer == "direction":
        return "direction_internal"
    if layer == "composite":
        return "capability_internal"
    if layer == "ability":
        return "ability_internal"
    if node_type == "tool":
        return "tool_internal"
    if node_type == "knowledge":
        return "knowledge_internal"
    return f"{node_type or 'concept'}_internal"


def external_occ_id(profile: dict[str, Any]) -> str:
    scheme = str(profile.get("source_type") or "external").replace("_online", "")
    source_id = str(profile.get("source_id") or profile.get("profile_id") or "")
    return f"ext_occ_{stable_id(scheme, source_id)}"


def add_term(
    terms_by_key: dict[tuple[str, str, str], dict[str, Any]],
    surface: Any,
    concept_id: str,
    concept_type: str,
    source: str,
    language: str = "mixed",
    preferred: bool = False,
    metadata: dict[str, Any] | None = None,
) -> None:
    surface_text = str(surface or "").strip()
    normalized = normalized_key(surface_text)
    if not surface_text or not normalized:
        return
    key = (normalized, concept_id, source)
    current = terms_by_key.get(key)
    item = {
        "concept_id": concept_id,
        "concept_type": concept_type,
        "language": language,
        "metadata": metadata or {},
        "normalized": normalized,
        "preferred": preferred,
        "source": source,
        "surface": surface_text,
        "term_id": f"term_{stable_id(concept_id, normalized)}",
    }
    if current is None or len(surface_text) < len(str(current["surface"])):
        terms_by_key[key] = item


def add_seed_terms(terms_by_key: dict[tuple[str, str, str], dict[str, Any]]) -> None:
    nodes = read_json(NODES_PATH, default=[])
    aliases = read_json(ALIASES_PATH, default={})
    for node in nodes:
        if not isinstance(node, dict):
            continue
        node_id = str(node.get("id", ""))
        if not node_id:
            continue
        concept_type = concept_type_for_node(node)
        add_term(
            terms_by_key,
            node.get("name", ""),
            node_id,
            concept_type,
            "seed_node_name",
            preferred=True,
            metadata={"layer": node.get("layer", ""), "node_type": node.get("node_type", "")},
        )
        for alias in aliases.get(node_id, []):
            add_term(
                terms_by_key,
                alias,
                node_id,
                concept_type,
                "seed_alias",
                metadata={"layer": node.get("layer", ""), "node_type": node.get("node_type", "")},
            )


def strip_onet_code(title: str) -> str:
    if " - " in title:
        return title.split(" - ", 1)[1].strip()
    return title.strip()


def add_external_profile_terms(terms_by_key: dict[tuple[str, str, str], dict[str, Any]]) -> None:
    for path in sorted(RAW_DIR.glob("*_profiles.json")):
        profiles = read_json(path, default=[])
        if not isinstance(profiles, list):
            continue
        for profile in profiles:
            if not isinstance(profile, dict):
                continue
            source_type = str(profile.get("source_type") or path.stem)
            concept_id = external_occ_id(profile)
            metadata = {
                "external_id": str(profile.get("source_id", "")),
                "profile_id": str(profile.get("profile_id", "")),
                "source_name": source_type,
            }
            title = strip_onet_code(str(profile.get("source_title", "")))
            add_term(
                terms_by_key,
                title,
                concept_id,
                "occupation_external",
                "external_profile_title",
                language="en",
                preferred=True,
                metadata=metadata,
            )
            for title in profile.get("sample_job_titles", []):
                add_term(
                    terms_by_key,
                    title,
                    concept_id,
                    "occupation_external",
                    "external_job_title",
                    language="en",
                    metadata=metadata,
                )
            for tag in profile.get("profile_tags", []):
                add_term(
                    terms_by_key,
                    tag,
                    concept_id,
                    "occupation_external",
                    "external_profile_tag",
                    language="en",
                    metadata=metadata,
                )


def add_rule_expansions(terms_by_key: dict[tuple[str, str, str], dict[str, Any]]) -> None:
    expansions = {
        "tool_nodejs": ["Node.js", "nodejs", "node"],
        "skill_csharp": [".NET", "dotnet", "C#"],
        "skill_cpp": ["C++", "cpp"],
        "dir_frontend": ["frontend", "front end", "web frontend", "前端"],
        "dir_web_backend": ["backend", "back end", "server side", "后端"],
        "dir_fullstack": ["fullstack", "full stack", "全栈"],
        "dir_devops": ["devops", "sre", "platform engineering"],
    }
    for concept_id, surfaces in expansions.items():
        concept_type = "tool_internal" if concept_id.startswith("tool_") else "skill_internal"
        if concept_id.startswith("dir_"):
            concept_type = "direction_internal"
        for surface in surfaces:
            add_term(terms_by_key, surface, concept_id, concept_type, "rule_expansion", metadata={"rule": "code_token_alias"})


def build_terms() -> list[dict[str, Any]]:
    terms_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    add_seed_terms(terms_by_key)
    add_external_profile_terms(terms_by_key)
    add_rule_expansions(terms_by_key)
    return sorted(
        terms_by_key.values(),
        key=lambda item: (
            SOURCE_PRIORITY.get(str(item["source"]), 99),
            str(item["concept_type"]),
            str(item["normalized"]),
            str(item["concept_id"]),
        ),
    )


def build_payload(terms: list[dict[str, Any]]) -> dict[str, Any]:
    by_type: dict[str, int] = {}
    for term in terms:
        by_type[str(term["concept_type"])] = by_type.get(str(term["concept_type"]), 0) + 1
    return {
        "pipeline_date": PIPELINE_DATE,
        "pipeline_version": PIPELINE_VERSION,
        "source": "data/seeds/nodes.json + data/dictionaries/skill_aliases.json + data/sources/raw/*_profiles.json",
        "term_count": len(terms),
        "term_count_by_type": dict(sorted(by_type.items())),
        "terms": terms,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a deterministic term lexicon from seed graph and raw profiles.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    terms = build_terms()
    write_json(args.output, build_payload(terms))
    print(f"built {len(terms)} terms -> {args.output.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
