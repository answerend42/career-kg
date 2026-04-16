#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.api.recommend import RecommendationService


def main() -> None:
    benchmark_path = ROOT / "data" / "demo" / "nl_benchmark.json"
    cases = json.loads(benchmark_path.read_text(encoding="utf-8"))
    service = RecommendationService(ROOT)

    failures: list[str] = []
    for case in cases:
        result = service.recommend({"text": case["text"], "top_k": 6, "include_snapshot": False})
        normalized_ids = {item["node_id"] for item in result["normalized_inputs"]}
        top_role_ids = [item["job_id"] for item in result["recommendations"][:6]]

        missing_nodes = [node_id for node_id in case.get("expected_nodes", []) if node_id not in normalized_ids]
        unexpected_nodes = [node_id for node_id in case.get("unexpected_nodes", []) if node_id in normalized_ids]
        min_signal_count = int(case.get("min_signal_count", 0))
        role_expectations = case.get("expected_roles_any", [])
        has_expected_role = not role_expectations or any(role_id in top_role_ids for role_id in role_expectations)

        if missing_nodes:
            failures.append(f"{case['id']}: missing nodes {missing_nodes}")
        if unexpected_nodes:
            failures.append(f"{case['id']}: unexpected nodes {unexpected_nodes}")
        if len(normalized_ids) < min_signal_count:
            failures.append(f"{case['id']}: expected at least {min_signal_count} signals, got {len(normalized_ids)}")
        if not has_expected_role:
            failures.append(f"{case['id']}: top roles missing expected any of {role_expectations}, got {top_role_ids}")

        status = "PASS" if not any(message.startswith(f"{case['id']}:") for message in failures) else "FAIL"
        print(f"[{status}] {case['id']} normalized={sorted(normalized_ids)} top_roles={top_role_ids}")

    if failures:
        raise SystemExit("\n".join(failures))

    print(f"nl benchmark passed ({len(cases)} cases)")


if __name__ == "__main__":
    main()
