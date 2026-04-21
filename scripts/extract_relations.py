#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from build_term_lexicon import external_occ_id
from normalize_raw_documents import ROOT, PIPELINE_DATE, PIPELINE_VERSION, read_json, stable_id, write_json


DOCUMENTS_PATH = ROOT / "data" / "staging" / "normalized_documents.json"
LINKS_PATH = ROOT / "data" / "canonical" / "entity_links.json"
NODES_PATH = ROOT / "data" / "seeds" / "nodes.json"
EDGES_PATH = ROOT / "data" / "seeds" / "edges.json"
RAW_DIR = ROOT / "data" / "sources" / "raw"
DEFAULT_OUTPUT = ROOT / "data" / "canonical" / "relation_triples.json"


NODE_RELATION_BY_TYPE = {
    "skill": "requires_skill",
    "tool": "uses_tool",
    "language": "requires_skill",
    "knowledge": "requires_knowledge",
    "project": "has_task",
    "soft_skill": "requires_skill",
}

SERVING_RELATION_MAP = {
    "supports": "supports",
    "requires": "requires",
    "prefers": "optional_for",
    "evidences": "supported_by",
    "inhibits": "inhibits",
}


def node_index() -> dict[str, dict[str, Any]]:
    return {str(node.get("id")): node for node in read_json(NODES_PATH, default=[]) if isinstance(node, dict) and node.get("id")}


def profile_index() -> dict[str, dict[str, Any]]:
    profiles: dict[str, dict[str, Any]] = {}
    for path in sorted(RAW_DIR.glob("*_profiles.json")):
        payload = read_json(path, default=[])
        if not isinstance(payload, list):
            continue
        for profile in payload:
            if isinstance(profile, dict):
                profiles[str(profile.get("profile_id", ""))] = profile
    return profiles


def document_index(documents_path: Path) -> dict[str, dict[str, Any]]:
    payload = read_json(documents_path, default={"documents": []})
    return {str(doc.get("doc_id")): doc for doc in payload.get("documents", []) if isinstance(doc, dict) and doc.get("doc_id")}


def section_text(doc: dict[str, Any], section_id: str) -> str:
    for section in doc.get("sections", []):
        if isinstance(section, dict) and str(section.get("section_id")) == section_id:
            return str(section.get("text", ""))
    return ""


def add_triple(triples: dict[tuple[str, str, str, str], dict[str, Any]], triple: dict[str, Any]) -> None:
    key = (
        str(triple.get("head_id", "")),
        str(triple.get("relation", "")),
        str(triple.get("tail_id", "")),
        str(triple.get("source_doc_id", "")),
    )
    if not all(key[:3]):
        return
    current = triples.get(key)
    if current is None or float(triple.get("confidence", 0)) > float(current.get("confidence", 0)):
        triple["triple_id"] = f"triple_{stable_id(*key)}"
        triples[key] = triple


def extract_from_links(
    triples: dict[tuple[str, str, str, str], dict[str, Any]],
    docs: dict[str, dict[str, Any]],
    nodes: dict[str, dict[str, Any]],
    links_path: Path,
) -> None:
    payload = read_json(links_path, default={"links": []})
    for link in payload.get("links", []):
        if not isinstance(link, dict):
            continue
        doc = docs.get(str(link.get("doc_id", "")))
        if not doc:
            continue
        concept_id = str(link.get("chosen_concept_id", ""))
        node = nodes.get(concept_id)
        if not node:
            continue
        relation = NODE_RELATION_BY_TYPE.get(str(node.get("node_type", "")))
        if not relation:
            continue
        profile_stub = {
            "source_type": doc.get("source_name", ""),
            "source_id": doc.get("external_id", ""),
            "profile_id": doc.get("profile_id", ""),
        }
        evidence = link.get("evidence", {})
        source_section = str(evidence.get("section_type", ""))
        if source_section in {"tags", "title"} and float(link.get("score", 0)) < 0.9:
            continue
        section_id = str(evidence.get("section_id", ""))
        add_triple(
            triples,
            {
                "confidence": round(min(0.79, max(0.58, float(link.get("score", 0)) - 0.12)), 4),
                "evidence_text": section_text(doc, section_id)[:360],
                "extraction_method": "section_aware_lexicon_rule",
                "head_id": external_occ_id(profile_stub),
                "relation": relation,
                "source_doc_id": str(doc.get("doc_id", "")),
                "source_section": source_section,
                "tail_id": concept_id,
            },
        )


def extract_profile_mappings(
    triples: dict[tuple[str, str, str, str], dict[str, Any]],
    profiles: dict[str, dict[str, Any]],
    nodes: dict[str, dict[str, Any]],
) -> None:
    for profile_id, profile in profiles.items():
        head_id = external_occ_id(profile)
        source_doc_id = stable_id(profile_id)
        for node_id in sorted(str(item) for item in profile.get("mapped_node_ids", []) if str(item).strip()):
            node = nodes.get(node_id)
            if not node:
                continue
            layer = str(node.get("layer", ""))
            relation = "close_match" if layer == "role" else "related_match"
            add_triple(
                triples,
                {
                    "confidence": 0.88 if layer == "role" else 0.82,
                    "evidence_text": str(profile.get("source_note") or profile.get("summary_excerpt") or "")[:360],
                    "extraction_method": "curated_profile_mapping",
                    "head_id": head_id,
                    "relation": relation,
                    "source_doc_id": source_doc_id,
                    "source_section": "mapped_node_ids",
                    "tail_id": node_id,
                },
            )


def extract_seed_edges(triples: dict[tuple[str, str, str, str], dict[str, Any]], nodes: dict[str, dict[str, Any]]) -> None:
    edges = read_json(EDGES_PATH, default=[])
    for edge in edges:
        if not isinstance(edge, dict):
            continue
        source = str(edge.get("source", ""))
        target = str(edge.get("target", ""))
        relation = SERVING_RELATION_MAP.get(str(edge.get("relation", "")))
        if source not in nodes or target not in nodes or not relation:
            continue
        metadata = edge.get("metadata", {}) if isinstance(edge.get("metadata"), dict) else {}
        add_triple(
            triples,
            {
                "confidence": 0.9,
                "evidence_text": str(edge.get("note", "")),
                "extraction_method": "curated_source_graph",
                "head_id": source,
                "relation": relation,
                "source_doc_id": str(metadata.get("source_file", "data/seeds/edges.json")),
                "source_section": str(metadata.get("relation_group", "")),
                "tail_id": target,
            },
        )


def extract_relations(documents_path: Path = DOCUMENTS_PATH, links_path: Path = LINKS_PATH) -> list[dict[str, Any]]:
    triples: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    nodes = node_index()
    docs = document_index(documents_path)
    profiles = profile_index()
    extract_profile_mappings(triples, profiles, nodes)
    extract_from_links(triples, docs, nodes, links_path)
    extract_seed_edges(triples, nodes)
    return sorted(triples.values(), key=lambda item: (str(item["head_id"]), str(item["relation"]), str(item["tail_id"]), str(item["source_doc_id"])))


def build_payload(triples: list[dict[str, Any]]) -> dict[str, Any]:
    method_counts: dict[str, int] = {}
    relation_counts: dict[str, int] = {}
    for triple in triples:
        method = str(triple.get("extraction_method", ""))
        relation = str(triple.get("relation", ""))
        method_counts[method] = method_counts.get(method, 0) + 1
        relation_counts[relation] = relation_counts.get(relation, 0) + 1
    review_queue = [triple for triple in triples if float(triple.get("confidence", 0)) < 0.6]
    return {
        "pipeline_date": PIPELINE_DATE,
        "pipeline_version": PIPELINE_VERSION,
        "relation_counts": dict(sorted(relation_counts.items())),
        "review_queue": review_queue,
        "review_queue_count": len(review_queue),
        "triple_count": len(triples),
        "triple_count_by_method": dict(sorted(method_counts.items())),
        "triples": triples,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extract deterministic canonical relation triples.")
    parser.add_argument("--documents", type=Path, default=DOCUMENTS_PATH)
    parser.add_argument("--links", type=Path, default=LINKS_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    triples = extract_relations(args.documents, args.links)
    write_json(args.output, build_payload(triples))
    print(f"extracted {len(triples)} triples -> {args.output.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
