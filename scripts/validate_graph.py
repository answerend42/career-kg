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


def load_seed_payloads() -> tuple[list[dict], list[dict]]:
    nodes_path = ROOT / "data" / "seeds" / "nodes.json"
    edges_path = ROOT / "data" / "seeds" / "edges.json"
    return (
        json.loads(nodes_path.read_text(encoding="utf-8")),
        json.loads(edges_path.read_text(encoding="utf-8")),
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

    print("graph validation passed")
    print(f"nodes={len(graph.nodes)} edges={len(graph.edges)} evidence_nodes={evidence_count} roles={role_count}")
    print(f"reachable_nodes={len(reachable)} topological_order={len(graph.topological_order)} directions={len(direction_ids)}")
    print(f"role_families={len(role_families)}")


if __name__ == "__main__":
    main()
