#!/usr/bin/env python3

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.api.recommend import RecommendationService


BENCHMARK_PATH = ROOT / "data" / "demo" / "recommendation_benchmark.json"
REPORT_JSON_PATH = ROOT / "data" / "demo" / "recommendation_benchmark_report.json"
REPORT_MD_PATH = ROOT / "data" / "demo" / "recommendation_benchmark_report.md"
QUALITY_THRESHOLDS = {
    "hit_at_3": 0.75,
    "hit_at_5": 0.9,
    "forbidden_role_violations": 0,
    "explanation_coverage": 0.8,
    "provenance_coverage": 0.8,
    "fallback_coverage": 1.0,
}


def flatten_path_node_ids(recommendation: dict[str, Any]) -> set[str]:
    node_ids: set[str] = set()
    for path in recommendation.get("paths", []):
        node_ids.update(str(node_id) for node_id in path.get("node_ids", []))
    return node_ids


def find_first_matching_recommendation(result: dict[str, Any], expected_roles_any: list[str]) -> dict[str, Any] | None:
    expected = set(expected_roles_any)
    for recommendation in result.get("recommendations", []):
        if recommendation.get("job_id") in expected:
            return recommendation
    return None


def format_role_label(role_id: str | None, role_name: str | None) -> str:
    if role_name and role_id:
        return f"{role_name} ({role_id})"
    if role_name:
        return role_name
    return role_id or "-"


def evaluate_case(service: RecommendationService, case: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "text": case.get("text", ""),
        "signals": case.get("signals", []),
        "top_k": int(case.get("top_k", 6)),
        "include_snapshot": False,
    }
    result = service.recommend(payload)
    recommendations = result.get("recommendations", [])
    near_miss_roles = result.get("near_miss_roles", [])
    bridge_recommendations = result.get("bridge_recommendations", [])
    top_roles = [
        {
            "job_id": str(item.get("job_id", "")),
            "job_name": str(item.get("job_name", "")),
            "score": float(item.get("score", 0.0)),
        }
        for item in recommendations[: payload["top_k"]]
    ]
    top_role_ids = [item["job_id"] for item in recommendations]
    expected_roles_any = [str(role_id) for role_id in case.get("expected_roles_any", [])]
    expected_near_miss_roles = [str(role_id) for role_id in case.get("expected_near_miss_roles_any", [])]
    expected_bridge_anchor_ids = [str(node_id) for node_id in case.get("expected_bridge_anchor_ids_any", [])]
    expected_bridge_roles = [str(role_id) for role_id in case.get("expected_bridge_roles_any", [])]
    forbidden_roles = {str(role_id) for role_id in case.get("forbidden_roles", [])}
    expected_explanation_nodes = {str(node_id) for node_id in case.get("expected_explanation_nodes_any", [])}
    expected_source_types = {str(source_type) for source_type in case.get("expected_source_types_any", [])}
    matched_recommendation = find_first_matching_recommendation(result, expected_roles_any)
    near_miss_ids = [str(item.get("job_id", "")) for item in near_miss_roles]
    bridge_anchor_ids = [str(item.get("anchor_id", "")) for item in bridge_recommendations]
    bridge_role_ids = [
        str(role.get("job_id", ""))
        for item in bridge_recommendations
        for role in item.get("related_roles", [])
    ]

    hit_at_3 = bool(expected_roles_any) and any(role_id in set(expected_roles_any) for role_id in top_role_ids[:3])
    hit_at_5 = bool(expected_roles_any) and any(role_id in set(expected_roles_any) for role_id in top_role_ids[:5])
    forbidden_hits = [role_id for role_id in top_role_ids[: payload["top_k"]] if role_id in forbidden_roles]

    explanation_nodes = flatten_path_node_ids(matched_recommendation) if matched_recommendation else set()
    explanation_ok = not expected_explanation_nodes or bool(explanation_nodes & expected_explanation_nodes)
    matched_explanation_nodes = sorted(explanation_nodes & expected_explanation_nodes)

    provenance_count = int(matched_recommendation.get("provenance_count", 0)) if matched_recommendation else 0
    source_types = [str(source_type) for source_type in matched_recommendation.get("source_types", [])] if matched_recommendation else []
    provenance_ok = provenance_count >= int(case.get("min_provenance_count", 0))
    if expected_source_types:
        provenance_ok = provenance_ok and bool(set(source_types) & expected_source_types)

    near_miss_ok = not expected_near_miss_roles or any(role_id in set(expected_near_miss_roles) for role_id in near_miss_ids)
    bridge_anchor_ok = not expected_bridge_anchor_ids or any(node_id in set(expected_bridge_anchor_ids) for node_id in bridge_anchor_ids)
    bridge_role_ok = not expected_bridge_roles or any(role_id in set(expected_bridge_roles) for role_id in bridge_role_ids)
    fallback_expected = bool(expected_near_miss_roles or expected_bridge_anchor_ids or expected_bridge_roles)
    fallback_ok = near_miss_ok and bridge_anchor_ok and bridge_role_ok

    failure_reasons: list[str] = []
    if expected_roles_any and not hit_at_5:
        failure_reasons.append(
            "expected role missing from Top-5: "
            f"expected any of {expected_roles_any}, got {top_role_ids[:5]}"
        )
    if forbidden_hits:
        failure_reasons.append(f"forbidden roles appeared: {forbidden_hits}")
    if expected_roles_any and not explanation_ok:
        failure_reasons.append(
            "missing expected explanation nodes: "
            f"expected any of {sorted(expected_explanation_nodes)}, got {sorted(explanation_nodes)}"
        )
    if expected_roles_any and not provenance_ok:
        failure_reasons.append(
            "provenance requirement unmet: "
            f"count={provenance_count}, source_types={source_types}, "
            f"min_count={int(case.get('min_provenance_count', 0))}, "
            f"expected_source_types={sorted(expected_source_types)}"
        )
    if fallback_expected and not near_miss_ok:
        failure_reasons.append(
            f"expected near miss roles missing: expected any of {expected_near_miss_roles}, got {near_miss_ids}"
        )
    if fallback_expected and not bridge_anchor_ok:
        failure_reasons.append(
            f"expected bridge anchors missing: expected any of {expected_bridge_anchor_ids}, got {bridge_anchor_ids}"
        )
    if fallback_expected and not bridge_role_ok:
        failure_reasons.append(
            f"expected bridge related roles missing: expected any of {expected_bridge_roles}, got {bridge_role_ids}"
        )

    role_case_pass = (not expected_roles_any or hit_at_5) and not forbidden_hits and explanation_ok and provenance_ok
    case_pass = role_case_pass and (not fallback_expected or fallback_ok)
    return {
        "id": case["id"],
        "payload": payload,
        "top_roles": top_roles,
        "top_role_ids": top_role_ids[: payload["top_k"]],
        "near_miss_ids": near_miss_ids,
        "bridge_anchor_ids": bridge_anchor_ids,
        "bridge_role_ids": bridge_role_ids,
        "matched_role_id": matched_recommendation.get("job_id") if matched_recommendation else None,
        "matched_role_name": matched_recommendation.get("job_name") if matched_recommendation else None,
        "matched_source_types": source_types,
        "matched_provenance_count": provenance_count,
        "matched_explanation_nodes": matched_explanation_nodes,
        "hit_at_3": hit_at_3,
        "hit_at_5": hit_at_5,
        "forbidden_hits": forbidden_hits,
        "explanation_ok": explanation_ok,
        "provenance_ok": provenance_ok,
        "fallback_expected": fallback_expected,
        "fallback_ok": fallback_ok,
        "case_pass": case_pass,
        "failure_reasons": failure_reasons,
    }


def summarize_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    total_cases = len(results)
    role_metric_cases = [result for result in results if not result["fallback_expected"]]
    fallback_cases = [result for result in results if result["fallback_expected"]]
    hit_at_3_count = sum(1 for result in role_metric_cases if result["hit_at_3"])
    hit_at_5_count = sum(1 for result in role_metric_cases if result["hit_at_5"])
    explanation_count = sum(1 for result in role_metric_cases if result["explanation_ok"])
    provenance_count = sum(1 for result in role_metric_cases if result["provenance_ok"])
    fallback_count = sum(1 for result in fallback_cases if result["fallback_ok"])
    forbidden_role_violations = sum(len(result["forbidden_hits"]) for result in results)
    pass_count = sum(1 for result in results if result["case_pass"])
    role_metric_total = len(role_metric_cases)

    return {
        "total_cases": total_cases,
        "hit_at_3": hit_at_3_count / role_metric_total if role_metric_total else 0.0,
        "hit_at_5": hit_at_5_count / role_metric_total if role_metric_total else 0.0,
        "forbidden_role_violations": forbidden_role_violations,
        "explanation_coverage": explanation_count / role_metric_total if role_metric_total else 0.0,
        "provenance_coverage": provenance_count / role_metric_total if role_metric_total else 0.0,
        "fallback_coverage": fallback_count / len(fallback_cases) if fallback_cases else 1.0,
        "pass_rate": pass_count / total_cases if total_cases else 0.0,
        "pass_count": pass_count,
    }


def validate_thresholds(summary: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if summary["hit_at_3"] < QUALITY_THRESHOLDS["hit_at_3"]:
        failures.append(f"hit_at_3 below threshold: {summary['hit_at_3']:.2f}")
    if summary["hit_at_5"] < QUALITY_THRESHOLDS["hit_at_5"]:
        failures.append(f"hit_at_5 below threshold: {summary['hit_at_5']:.2f}")
    if summary["forbidden_role_violations"] != QUALITY_THRESHOLDS["forbidden_role_violations"]:
        failures.append(f"forbidden_role_violations expected 0, got {summary['forbidden_role_violations']}")
    if summary["explanation_coverage"] < QUALITY_THRESHOLDS["explanation_coverage"]:
        failures.append(f"explanation_coverage below threshold: {summary['explanation_coverage']:.2f}")
    if summary["provenance_coverage"] < QUALITY_THRESHOLDS["provenance_coverage"]:
        failures.append(f"provenance_coverage below threshold: {summary['provenance_coverage']:.2f}")
    if summary["fallback_coverage"] < QUALITY_THRESHOLDS["fallback_coverage"]:
        failures.append(f"fallback_coverage below threshold: {summary['fallback_coverage']:.2f}")
    return failures


def write_report(payload: dict[str, Any]) -> None:
    REPORT_JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = payload["summary"]
    lines = [
        "# Recommendation Benchmark Report",
        "",
        f"- Generated At: `{payload['generated_at']}`",
        f"- Total Cases: `{summary['total_cases']}`",
        f"- Hit@3: `{summary['hit_at_3']:.2f}`",
        f"- Hit@5: `{summary['hit_at_5']:.2f}`",
        f"- Forbidden Role Violations: `{summary['forbidden_role_violations']}`",
        f"- Explanation Coverage: `{summary['explanation_coverage']:.2f}`",
        f"- Provenance Coverage: `{summary['provenance_coverage']:.2f}`",
        f"- Fallback Coverage: `{summary['fallback_coverage']:.2f}`",
        f"- Pass Rate: `{summary['pass_rate']:.2f}`",
        "",
        "## Thresholds",
        "",
        f"- Hit@3 >= `{payload['thresholds']['hit_at_3']:.2f}`",
        f"- Hit@5 >= `{payload['thresholds']['hit_at_5']:.2f}`",
        f"- Forbidden Role Violations = `{payload['thresholds']['forbidden_role_violations']}`",
        f"- Explanation Coverage >= `{payload['thresholds']['explanation_coverage']:.2f}`",
        f"- Provenance Coverage >= `{payload['thresholds']['provenance_coverage']:.2f}`",
        f"- Fallback Coverage >= `{payload['thresholds']['fallback_coverage']:.2f}`",
        "",
        "## Cases",
        "",
        "| Case | Status | Matched Role | Top Recommendations | Provenance | Failure Reasons |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for result in payload["results"]:
        top_recommendations = ", ".join(
            format_role_label(item["job_id"], item["job_name"])
            for item in result.get("top_roles", [])[:3]
        ) or "-"
        matched_role = format_role_label(result.get("matched_role_id"), result.get("matched_role_name"))
        if result.get("fallback_expected") and not result.get("matched_role_id"):
            fallback_labels = result.get("near_miss_ids", [])[:2] + result.get("bridge_anchor_ids", [])[:2]
            matched_role = ", ".join(fallback_labels) or matched_role
        provenance_label = (
            f"{result['matched_provenance_count']} / {', '.join(result['matched_source_types'])}"
            if result.get("matched_source_types")
            else str(result["matched_provenance_count"])
        )
        failure_label = "; ".join(result.get("failure_reasons", [])) or "-"
        lines.append(
            f"| {result['id']} | {'PASS' if result['case_pass'] else 'FAIL'} | {matched_role} | "
            f"{top_recommendations} | {provenance_label} | {failure_label} |"
        )
    REPORT_MD_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    cases = json.loads(BENCHMARK_PATH.read_text(encoding="utf-8"))
    service = RecommendationService(ROOT)
    results = [evaluate_case(service, case) for case in cases]
    summary = summarize_results(results)
    failures = [
        f"{result['id']}: {'; '.join(result['failure_reasons'])}"
        for result in results
        if not result["case_pass"]
    ]
    failures.extend(validate_thresholds(summary))

    for result in results:
        status = "PASS" if result["case_pass"] else "FAIL"
        failure_suffix = f" failures={result['failure_reasons']}" if result["failure_reasons"] else ""
        print(
            f"[{status}] {result['id']} matched={result['matched_role_id']} "
            f"top_roles={result['top_role_ids']} source_types={result['matched_source_types']}"
            f"{failure_suffix}"
        )

    report_payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "summary": summary,
        "thresholds": QUALITY_THRESHOLDS,
        "results": results,
    }
    write_report(report_payload)

    print(
        "recommendation benchmark summary "
        f"hit@3={summary['hit_at_3']:.2f} hit@5={summary['hit_at_5']:.2f} "
        f"explanation={summary['explanation_coverage']:.2f} provenance={summary['provenance_coverage']:.2f}"
    )
    print(f"reports written to {REPORT_JSON_PATH.relative_to(ROOT)} and {REPORT_MD_PATH.relative_to(ROOT)}")

    if failures:
        raise SystemExit("\n".join(failures))


if __name__ == "__main__":
    main()
