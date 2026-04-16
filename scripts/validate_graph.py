#!/usr/bin/env python3

from __future__ import annotations

from collections import deque
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.services.graph_loader import GraphLoader


VALID_RELATIONS = {"supports", "requires", "prefers", "inhibits", "evidences"}
MIN_NODES = 300
MIN_EDGES = 700
MIN_EVIDENCE_NODES = 120
MIN_ROLE_NODES = 25
MIN_ROLE_FAMILIES = 8
MIN_IMPORTED_PROFILES = 5
MIN_PROVENANCE_NODES = 40
REQUIRED_IMPORTED_PROFILE_KEYS = {
    "profile_id",
    "source_type",
    "source_id",
    "source_url",
    "source_title",
    "snapshot_date",
    "evidence_snippet",
    "mapped_node_ids",
}
REQUIRED_SOURCE_REF_KEYS = {
    "profile_id",
    "source_type",
    "source_id",
    "source_title",
    "source_url",
    "snapshot_date",
    "evidence_snippet",
}
PLACEHOLDER_SNIPPET_MARKERS = {
    "a subset of this occupation's profile is available.",
    "data collection is currently underway",
}


def load_seed_payloads() -> tuple[list[dict], list[dict]]:
    nodes_path = ROOT / "data" / "seeds" / "nodes.json"
    edges_path = ROOT / "data" / "seeds" / "edges.json"
    return (
        json.loads(nodes_path.read_text(encoding="utf-8")),
        json.loads(edges_path.read_text(encoding="utf-8")),
    )


def load_imported_payloads() -> tuple[list[dict], list[dict]]:
    imported_path = ROOT / "data" / "sources" / "imported_profiles.json"
    raw_snapshot_path = ROOT / "data" / "sources" / "raw" / "onet_profiles.json"
    if not imported_path.exists():
        raise SystemExit("imported profile dataset is missing: data/sources/imported_profiles.json")
    if not raw_snapshot_path.exists():
        raise SystemExit("raw source snapshot is missing: data/sources/raw/onet_profiles.json")
    return (
        json.loads(imported_path.read_text(encoding="utf-8")),
        json.loads(raw_snapshot_path.read_text(encoding="utf-8")),
    )


def reachable_roles(loader: GraphLoader) -> tuple[set[str], list[str]]:
    graph = loader.load_graph()
    queue = deque(graph.evidence_ids)
    seen = set(graph.evidence_ids)
    while queue:
        node_id = queue.popleft()
        for edge in graph.outgoing.get(node_id, []):
            if edge.target not in seen:
                seen.add(edge.target)
                queue.append(edge.target)
    missing_roles = [role_id for role_id in graph.role_ids if role_id not in seen]
    return seen, missing_roles


def main() -> None:
    loader = GraphLoader()
    graph = loader.load_graph()
    raw_nodes, raw_edges = load_seed_payloads()
    imported_profiles, raw_profiles = load_imported_payloads()

    invalid_relations = [f"{edge.source}->{edge.target}:{edge.relation}" for edge in graph.edges if edge.relation not in VALID_RELATIONS]
    if invalid_relations:
        raise SystemExit(f"invalid relations found: {invalid_relations[:10]}")

    reachable, missing_roles = reachable_roles(loader)
    if missing_roles:
        raise SystemExit(f"unreachable role nodes: {missing_roles}")

    evidence_count = len(graph.evidence_ids)
    role_count = len(graph.role_ids)
    if len(graph.nodes) < MIN_NODES or len(graph.edges) < MIN_EDGES:
        raise SystemExit("graph is too small for the expected course-project demo scale")
    if evidence_count < MIN_EVIDENCE_NODES or role_count < MIN_ROLE_NODES:
        raise SystemExit("graph is missing the expected evidence or role coverage")

    missing_node_metadata = [
        item["id"]
        for item in raw_nodes
        if not item.get("metadata", {}).get("source_file")
    ]
    missing_edge_metadata = [
        f"{item['source']}->{item['target']}:{item['relation']}"
        for item in raw_edges
        if not item.get("metadata", {}).get("source_file")
    ]
    if missing_node_metadata:
        raise SystemExit(f"nodes missing source metadata: {missing_node_metadata[:10]}")
    if missing_edge_metadata:
        raise SystemExit(f"edges missing source metadata: {missing_edge_metadata[:10]}")

    direction_ids = [node_id for node_id, node in graph.nodes.items() if node.layer == "direction"]
    directions_without_upstream = [
        node_id
        for node_id in direction_ids
        if not any(edge.relation in {"supports", "requires", "prefers", "evidences"} for edge in graph.incoming.get(node_id, []))
    ]
    directions_without_roles = [
        node_id
        for node_id in direction_ids
        if not any(graph.nodes[edge.target].layer == "role" for edge in graph.outgoing.get(node_id, []))
    ]
    if directions_without_upstream:
        raise SystemExit(f"direction nodes missing upstream capability paths: {directions_without_upstream}")
    if directions_without_roles:
        raise SystemExit(f"direction nodes missing role coverage: {directions_without_roles}")

    role_families = {
        item.get("metadata", {}).get("family")
        for item in raw_nodes
        if item.get("layer") == "role" and item.get("metadata", {}).get("family")
    }
    if len(role_families) < MIN_ROLE_FAMILIES:
        raise SystemExit(f"role family coverage is too narrow: {sorted(role_families)}")

    if len(imported_profiles) < MIN_IMPORTED_PROFILES:
        raise SystemExit(f"imported profile coverage is too small: {len(imported_profiles)}")
    if len(raw_profiles) < len(imported_profiles):
        raise SystemExit("raw profile snapshot count is smaller than imported profile count")

    invalid_imported_profiles = []
    imported_profile_ids = set()
    for profile in imported_profiles:
        missing_keys = sorted(
            key for key in REQUIRED_IMPORTED_PROFILE_KEYS
            if not profile.get(key)
        )
        if missing_keys:
            invalid_imported_profiles.append(f"{profile.get('profile_id', 'unknown')} missing {missing_keys}")
        else:
            imported_profile_ids.add(str(profile["profile_id"]))
    if invalid_imported_profiles:
        raise SystemExit(f"invalid imported profiles: {invalid_imported_profiles[:5]}")

    placeholder_profiles = [
        str(profile.get("profile_id", "unknown"))
        for profile in imported_profiles
        if any(marker in str(profile.get("evidence_snippet", "")).lower() for marker in PLACEHOLDER_SNIPPET_MARKERS)
    ]
    if placeholder_profiles:
        raise SystemExit(f"imported profiles still contain placeholder evidence snippets: {placeholder_profiles}")

    provenance_nodes = [item for item in raw_nodes if item.get("metadata", {}).get("source_refs")]
    if len(provenance_nodes) < MIN_PROVENANCE_NODES:
        raise SystemExit(f"provenance node coverage is too small: {len(provenance_nodes)}")

    source_ref_issues = []
    referenced_profile_ids = set()
    for node in provenance_nodes:
        metadata = node.get("metadata", {})
        source_refs = metadata.get("source_refs", [])
        if metadata.get("provenance_count") != len(source_refs):
            source_ref_issues.append(f"{node['id']} provenance_count mismatch")
        for ref in source_refs:
            missing_keys = sorted(key for key in REQUIRED_SOURCE_REF_KEYS if not ref.get(key))
            if missing_keys:
                source_ref_issues.append(f"{node['id']} missing source ref keys {missing_keys}")
                continue
            referenced_profile_ids.add(str(ref["profile_id"]))
    if source_ref_issues:
        raise SystemExit(f"invalid source refs: {source_ref_issues[:5]}")

    missing_profile_refs = sorted(imported_profile_ids - referenced_profile_ids)
    if missing_profile_refs:
        raise SystemExit(f"imported profiles not attached to any compiled node: {missing_profile_refs}")

    print("graph validation passed")
    print(f"nodes={len(graph.nodes)} edges={len(graph.edges)} evidence_nodes={evidence_count} roles={role_count}")
    print(f"reachable_nodes={len(reachable)} topological_order={len(graph.topological_order)} directions={len(direction_ids)}")
    print(f"role_families={len(role_families)} imported_profiles={len(imported_profiles)} provenance_nodes={len(provenance_nodes)}")


if __name__ == "__main__":
    main()
