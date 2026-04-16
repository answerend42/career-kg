#!/usr/bin/env python3

from __future__ import annotations

from collections import deque
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.services.graph_loader import GraphLoader


VALID_RELATIONS = {"supports", "requires", "prefers", "inhibits", "evidences"}


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

    invalid_relations = [f"{edge.source}->{edge.target}:{edge.relation}" for edge in graph.edges if edge.relation not in VALID_RELATIONS]
    if invalid_relations:
        raise SystemExit(f"invalid relations found: {invalid_relations[:10]}")

    reachable, missing_roles = reachable_roles(loader)
    if missing_roles:
        raise SystemExit(f"unreachable role nodes: {missing_roles}")

    evidence_count = len(graph.evidence_ids)
    role_count = len(graph.role_ids)
    if len(graph.nodes) < 100 or len(graph.edges) < 200:
        raise SystemExit("graph is too small for the expected course-project demo scale")

    print("graph validation passed")
    print(f"nodes={len(graph.nodes)} edges={len(graph.edges)} evidence_nodes={evidence_count} roles={role_count}")
    print(f"reachable_nodes={len(reachable)} topological_order={len(graph.topological_order)}")


if __name__ == "__main__":
    main()
