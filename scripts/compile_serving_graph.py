#!/usr/bin/env python3

from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path
from typing import Any

from normalize_raw_documents import ROOT, PIPELINE_DATE, PIPELINE_VERSION, read_json, write_json


NODES_PATH = ROOT / "data" / "seeds" / "nodes.json"
EDGES_PATH = ROOT / "data" / "seeds" / "edges.json"
ALIGNMENT_PATH = ROOT / "data" / "alignment" / "occupation_alignment.json"
TRIPLES_PATH = ROOT / "data" / "canonical" / "relation_triples.json"
RUNTIME_DIR = ROOT / "data" / "runtime"


def load_alignment_by_node(path: Path) -> dict[str, list[dict[str, Any]]]:
    payload = read_json(path, default={"mappings": []})
    by_node: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in payload.get("mappings", []):
        if not isinstance(item, dict) or int(item.get("candidate_rank", 0)) > 3:
            continue
        if str(item.get("mapping_type")) == "unmapped":
            continue
        by_node[str(item.get("internal_concept_id", ""))].append(item)
    for node_id in list(by_node):
        by_node[node_id].sort(key=lambda item: (int(item.get("candidate_rank", 99)), -float(item.get("confidence", 0))))
    return dict(by_node)


def load_triple_support(path: Path) -> tuple[dict[str, list[dict[str, Any]]], dict[tuple[str, str, str], list[dict[str, Any]]]]:
    payload = read_json(path, default={"triples": []})
    by_node: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_edge: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for triple in payload.get("triples", []):
        if not isinstance(triple, dict):
            continue
        head = str(triple.get("head_id", ""))
        tail = str(triple.get("tail_id", ""))
        relation = str(triple.get("relation", ""))
        by_node[head].append(triple)
        by_node[tail].append(triple)
        by_edge[(head, tail, relation)].append(triple)
    return dict(by_node), dict(by_edge)


def compact_provenance_refs(node: dict[str, Any], triples: list[dict[str, Any]], alignments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    refs: dict[str, dict[str, Any]] = {}
    metadata = node.get("metadata", {}) if isinstance(node.get("metadata"), dict) else {}
    for ref in metadata.get("source_refs", []) if isinstance(metadata.get("source_refs"), list) else []:
        if isinstance(ref, dict) and ref.get("profile_id"):
            refs[f"profile:{ref['profile_id']}"] = {
                "profile_id": str(ref.get("profile_id", "")),
                "source_id": str(ref.get("source_id", "")),
                "source_title": str(ref.get("source_title", "")),
                "source_type": str(ref.get("source_type", "")),
                "source_url": str(ref.get("source_url", "")),
            }
    for triple in triples[:12]:
        refs[f"triple:{triple.get('triple_id', '')}"] = {
            "confidence": triple.get("confidence", 0),
            "source_doc_id": str(triple.get("source_doc_id", "")),
            "triple_id": str(triple.get("triple_id", "")),
        }
    for alignment in alignments[:3]:
        refs[f"alignment:{alignment.get('external_id', '')}"] = {
            "confidence": alignment.get("confidence", 0),
            "external_id": str(alignment.get("external_id", "")),
            "mapping_type": str(alignment.get("mapping_type", "")),
        }
    return sorted(refs.values(), key=lambda item: str(item))


def augment_nodes(nodes: list[dict[str, Any]], alignment_by_node: dict[str, list[dict[str, Any]]], triples_by_node: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    augmented: list[dict[str, Any]] = []
    for node in nodes:
        node_id = str(node.get("id", ""))
        alignments = alignment_by_node.get(node_id, [])
        triples = triples_by_node.get(node_id, [])
        metadata = dict(node.get("metadata", {}) if isinstance(node.get("metadata"), dict) else {})
        external_ids = [f"onet:{item['external_id']}" for item in alignments]
        canonical_ids = [str(item.get("external_concept_id", "")) for item in alignments if item.get("external_concept_id")]
        canonical_ids.extend(str(triple.get("triple_id", "")) for triple in triples[:20] if triple.get("triple_id"))
        metadata.update(
            {
                "alignment_status": alignments[0]["mapping_type"] if alignments else metadata.get("alignment_status", "not_aligned"),
                "derivation_method": "canonical_alignment_compile" if alignments or triples else "curated_source_compile",
                "derived_from_canonical_ids": sorted(set(canonical_ids)),
                "derived_from_external_schemes": sorted({"onet"} if external_ids else set()),
                "derived_from_external_ids": sorted(set(external_ids)),
                "provenance_refs": compact_provenance_refs(node, triples, alignments),
                "support_count": len(triples) + len(alignments),
            }
        )
        updated = dict(node)
        updated["metadata"] = metadata
        augmented.append(updated)
    return augmented


def augment_edges(edges: list[dict[str, Any]], triples_by_edge: dict[tuple[str, str, str], list[dict[str, Any]]]) -> list[dict[str, Any]]:
    relation_reverse = {
        "supports": "supports",
        "requires": "requires",
        "prefers": "optional_for",
        "evidences": "supported_by",
        "inhibits": "inhibits",
    }
    augmented: list[dict[str, Any]] = []
    for edge in edges:
        source = str(edge.get("source", ""))
        target = str(edge.get("target", ""))
        canonical_relation = relation_reverse.get(str(edge.get("relation", "")), str(edge.get("relation", "")))
        triples = triples_by_edge.get((source, target, canonical_relation), [])
        metadata = dict(edge.get("metadata", {}) if isinstance(edge.get("metadata"), dict) else {})
        metadata.update(
            {
                "derivation_method": "canonical_triple_compile" if triples else metadata.get("derivation_method", "curated_source_compile"),
                "derived_from_canonical_ids": sorted(str(triple.get("triple_id", "")) for triple in triples if triple.get("triple_id")),
                "support_count": len(triples),
            }
        )
        updated = dict(edge)
        updated["metadata"] = metadata
        augmented.append(updated)
    return augmented


def compile_serving_graph(output_dir: Path = RUNTIME_DIR) -> dict[str, Any]:
    nodes = read_json(NODES_PATH, default=[])
    edges = read_json(EDGES_PATH, default=[])
    alignment_by_node = load_alignment_by_node(ALIGNMENT_PATH)
    triples_by_node, triples_by_edge = load_triple_support(TRIPLES_PATH)
    augmented_nodes = augment_nodes(nodes, alignment_by_node, triples_by_node)
    augmented_edges = augment_edges(edges, triples_by_edge)

    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "serving_nodes.json", augmented_nodes)
    write_json(output_dir / "serving_edges.json", augmented_edges)

    aligned_nodes = sum(1 for node in augmented_nodes if node.get("metadata", {}).get("alignment_status") != "not_aligned")
    canonical_supported_nodes = sum(1 for node in augmented_nodes if node.get("metadata", {}).get("support_count", 0) > 0)
    summary = {
        "aligned_nodes": aligned_nodes,
        "canonical_supported_nodes": canonical_supported_nodes,
        "edge_count": len(augmented_edges),
        "node_count": len(augmented_nodes),
        "pipeline_date": PIPELINE_DATE,
        "pipeline_version": PIPELINE_VERSION,
        "runtime_edges": str((output_dir / "serving_edges.json").relative_to(ROOT)),
        "runtime_nodes": str((output_dir / "serving_nodes.json").relative_to(ROOT)),
    }
    write_json(output_dir / "serving_graph_summary.json", summary)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compile augmented runtime serving graph copies with canonical metadata.")
    parser.add_argument("--output-dir", type=Path, default=RUNTIME_DIR)
    args = parser.parse_args(argv)

    summary = compile_serving_graph(args.output_dir)
    print(
        f"compiled runtime serving graph with {summary['node_count']} nodes and {summary['edge_count']} edges "
        f"-> {summary['runtime_nodes']}, {summary['runtime_edges']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
