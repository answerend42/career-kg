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


BENCHMARK_PATH = ROOT / "data" / "demo" / "planning_benchmark.json"
REPORT_JSON_PATH = ROOT / "data" / "demo" / "planning_benchmark_report.json"
REPORT_MD_PATH = ROOT / "data" / "demo" / "planning_benchmark_report.md"
QUALITY_THRESHOLDS = {
    "gap_coverage": 1.0,
    "learning_path_coverage": 0.85,
    "action_template_coverage": 1.0,
    "simulation_positive_rate": 0.85,
    "adopt_non_regression_rate": 1.0,
    "focus_match_rate": 0.85,
}


def format_role_label(role_id: str | None, role_name: str | None) -> str:
    if role_name and role_id:
        return f"{role_name} ({role_id})"
    if role_name:
        return role_name
    return role_id or "-"


def build_role_gap_payload(case: dict[str, Any]) -> dict[str, Any]:
    return {
        "text": case.get("text", ""),
        "signals": case.get("signals", []),
        "target_role_id": case["target_role_id"],
        "scenario_limit": int(case.get("scenario_limit", 3)),
    }


def build_recommend_payload(text: str, signals: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "text": text,
        "signals": signals,
        "top_k": 20,
        "include_snapshot": False,
    }


def classify_adopt_basis(
    require_non_worse_score: bool,
    require_non_worse_rank: bool,
    score_ok: bool,
    rank_ok: bool,
) -> str:
    if require_non_worse_score and require_non_worse_rank:
        if score_ok and rank_ok:
            return "score+rank"
        if score_ok:
            return "score_only"
        if rank_ok:
            return "rank_only"
        return "regressed"
    if require_non_worse_score:
        return "score_required" if score_ok else "regressed"
    if require_non_worse_rank:
        return "rank_required" if rank_ok else "regressed"
    return "not_required"


def merge_adopted_signals(
    normalized_inputs: list[dict[str, Any]],
    injected_boosts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    merged: dict[str, float] = {}
    for item in normalized_inputs:
        node_id = str(item.get("node_id", "")).strip()
        if not node_id:
            continue
        merged[node_id] = max(merged.get(node_id, 0.0), float(item.get("score", 0.0) or 0.0))
    for boost in injected_boosts:
        node_id = str(boost.get("node_id", "")).strip()
        if not node_id:
            continue
        merged[node_id] = max(merged.get(node_id, 0.0), float(boost.get("to_score", 0.0) or 0.0))
    return [
        {"entity": node_id, "score": round(score, 4)}
        for node_id, score in sorted(merged.items())
    ]


def find_role_rank(recommend_result: dict[str, Any], target_role_id: str) -> int:
    recommendations = recommend_result.get("recommendations", [])
    for index, item in enumerate(recommendations, start=1):
        if item.get("job_id") == target_role_id:
            return index
    return len(recommendations) + 1


def select_actions(
    learning_path: list[dict[str, Any]],
    simulation_case: dict[str, Any],
) -> tuple[list[str], list[str], list[str]]:
    selectors = simulation_case.get("selectors") or [{"step": 1, "action": 1}]
    action_keys: list[str] = []
    template_ids: list[str] = []
    errors: list[str] = []

    for selector in selectors:
        step_index = int(selector.get("step", 1)) - 1
        action_index = int(selector.get("action", 1)) - 1
        if step_index < 0 or step_index >= len(learning_path):
            errors.append(f"missing learning path step: {step_index + 1}")
            continue
        actions = learning_path[step_index].get("recommended_actions", [])
        if action_index < 0 or action_index >= len(actions):
            errors.append(f"missing recommended action: step={step_index + 1}, action={action_index + 1}")
            continue
        action = actions[action_index]
        action_key = str(action.get("action_key", "")).strip()
        if not action_key:
            errors.append(f"recommended action missing action_key: step={step_index + 1}, action={action_index + 1}")
            continue
        action_keys.append(action_key)
        template_ids.append(str(action.get("template_id", "")).strip())

    return action_keys, template_ids, errors


def evaluate_case(service: RecommendationService, case: dict[str, Any]) -> dict[str, Any]:
    payload = build_role_gap_payload(case)
    failure_reasons: list[str] = []
    target_role_id = str(case["target_role_id"])

    try:
        role_gap_result = service.role_gap(payload)
    except Exception as exc:  # pragma: no cover - defensive path for report generation
        return {
            "id": case["id"],
            "target_role_id": target_role_id,
            "target_role_name": None,
            "current_score": 0.0,
            "gap_ok": False,
            "learning_path_ok": False,
            "action_template_ok": False,
            "simulation_positive": False,
            "adopt_non_regression": False,
            "focus_ok": False,
            "priority_ok": False,
            "missing_ok": False,
            "first_step_relation_ok": False,
            "first_step_delta_positive": False,
            "selected_action_keys": [],
            "selected_template_ids": [],
            "simulation_bundle_size": 0,
            "simulation_delta_score": 0.0,
            "simulation_rank_before": None,
            "simulation_rank_after": None,
            "adopted_score": 0.0,
            "adopted_score_delta": 0.0,
            "adopted_rank_before": None,
            "adopted_rank_after": None,
            "adopt_basis": "not_evaluated",
            "focus_node_ids": [],
            "priority_node_ids": [],
            "missing_requirements": [],
            "case_pass": False,
            "failure_reasons": [f"role_gap failed: {exc}"],
        }

    target = role_gap_result.get("target_role", {})
    learning_path = target.get("learning_path", [])
    focus_node_ids = [str(step.get("focus_node_id", "")) for step in learning_path if step.get("focus_node_id")]
    priority_node_ids = [str(item.get("node_id", "")) for item in target.get("priority_suggestions", []) if item.get("node_id")]
    missing_requirements = [str(item) for item in target.get("missing_requirements", []) if str(item).strip()]
    first_step = learning_path[0] if learning_path else {}
    first_step_action_templates = [
        str(item.get("template_id", ""))
        for item in first_step.get("recommended_actions", [])
        if item.get("template_id")
    ]

    expected_missing = {str(item) for item in case.get("expected_missing_requirements_any", [])}
    expected_priority_nodes = {str(item) for item in case.get("expected_priority_nodes_any", [])}
    expected_focus_nodes = {str(item) for item in case.get("expected_focus_nodes_any", [])}
    expected_action_templates = {str(item) for item in case.get("expected_action_template_ids_any", [])}
    expected_boost_nodes = {str(item) for item in case.get("expected_simulation_boost_nodes_any", [])}
    expected_relation = str(case.get("expected_first_step_relation", "")).strip()

    gap_ok = target.get("job_id") == target_role_id
    learning_path_ok = len(learning_path) >= int(case.get("min_learning_path_steps", 1))
    action_template_ok = bool(learning_path) and all(step.get("recommended_actions") for step in learning_path)
    priority_ok = not expected_priority_nodes or bool(expected_priority_nodes & set(priority_node_ids))
    focus_ok = not expected_focus_nodes or bool(expected_focus_nodes & set(focus_node_ids))
    missing_ok = not expected_missing or bool(expected_missing & set(missing_requirements))
    first_step_relation_ok = not expected_relation or first_step.get("relation") == expected_relation
    first_step_delta_positive = bool(first_step) and float(first_step.get("expected_score_delta", 0.0) or 0.0) > 0.0
    first_step_action_ok = not expected_action_templates or bool(expected_action_templates & set(first_step_action_templates))

    if not gap_ok:
        failure_reasons.append(f"target role mismatch: expected {target_role_id}, got {target.get('job_id')}")
    if not learning_path_ok:
        failure_reasons.append("learning_path is empty or shorter than expected")
    if not action_template_ok:
        failure_reasons.append("learning_path contains step without recommended_actions")
    if not missing_ok:
        failure_reasons.append(
            "missing expected requirements: "
            f"expected any of {sorted(expected_missing)}, got {missing_requirements}"
        )
    if not priority_ok:
        failure_reasons.append(
            "priority suggestions missing expected nodes: "
            f"expected any of {sorted(expected_priority_nodes)}, got {priority_node_ids}"
        )
    if not focus_ok:
        failure_reasons.append(
            "learning_path missing expected focus nodes: "
            f"expected any of {sorted(expected_focus_nodes)}, got {focus_node_ids}"
        )
    if not first_step_relation_ok:
        failure_reasons.append(
            "first learning path relation mismatch: "
            f"expected {expected_relation}, got {first_step.get('relation')}"
        )
    if not first_step_delta_positive:
        failure_reasons.append("first learning path step does not provide positive expected_score_delta")
    if not first_step_action_ok:
        failure_reasons.append(
            "first step missing expected action templates: "
            f"expected any of {sorted(expected_action_templates)}, got {first_step_action_templates}"
        )

    simulation_case = case.get("simulation", {})
    selected_action_keys, selected_template_ids, selection_errors = select_actions(learning_path, simulation_case)
    if selection_errors:
        failure_reasons.extend(selection_errors)

    simulation_bundle_size = 0
    simulation_delta_score = 0.0
    simulation_rank_before: int | None = None
    simulation_rank_after: int | None = None
    simulation_positive = False
    simulation_boost_ok = not expected_boost_nodes
    adopted_score = float(target.get("current_score", 0.0) or 0.0)
    adopted_score_delta = 0.0
    adopted_rank_before: int | None = None
    adopted_rank_after: int | None = None
    adopt_non_regression = False
    adopt_basis = "not_evaluated"

    if selected_action_keys:
        try:
            simulation_result = service.action_simulate(
                {
                    "target_role_id": target_role_id,
                    "text": case.get("text", ""),
                    "signals": case.get("signals", []),
                    "action_keys": selected_action_keys,
                }
            )
        except Exception as exc:  # pragma: no cover - defensive path for report generation
            failure_reasons.append(f"action_simulate failed: {exc}")
        else:
            simulation = simulation_result.get("simulation", {})
            simulation_bundle_size = int(simulation.get("bundle_size", 0) or 0)
            simulation_delta_score = float(simulation.get("delta_score", 0.0) or 0.0)
            simulation_rank_before = int(simulation.get("target_role_rank_before", 0) or 0)
            simulation_rank_after = int(simulation.get("target_role_rank_after", 0) or 0)
            require_positive_delta = bool(simulation_case.get("require_positive_delta", True))
            expected_bundle_size = int(simulation_case.get("expected_bundle_size", len(selected_action_keys)))
            simulation_positive = simulation_delta_score > 0.0 if require_positive_delta else simulation_delta_score >= 0.0
            if simulation_bundle_size != expected_bundle_size:
                failure_reasons.append(
                    f"simulation bundle size mismatch: expected {expected_bundle_size}, got {simulation_bundle_size}"
                )
            if list(simulation.get("template_ids", [])) != selected_template_ids:
                failure_reasons.append(
                    f"simulation template ids mismatch: expected {selected_template_ids}, got {simulation.get('template_ids', [])}"
                )
            boosted_node_ids = {
                str(item.get("node_id", ""))
                for item in simulation.get("injected_boosts", [])
                if item.get("node_id")
            }
            simulation_boost_ok = not expected_boost_nodes or bool(expected_boost_nodes & boosted_node_ids)
            if not simulation_positive:
                failure_reasons.append(
                    f"simulation delta is not positive enough: delta_score={simulation_delta_score:.4f}"
                )
            if not simulation_boost_ok:
                failure_reasons.append(
                    "simulation missing expected boost nodes: "
                    f"expected any of {sorted(expected_boost_nodes)}, got {sorted(boosted_node_ids)}"
                )

            adopted_signals = merge_adopted_signals(
                role_gap_result.get("normalized_inputs", []),
                simulation.get("injected_boosts", []),
            )
            try:
                adopted_role_gap = service.role_gap(
                    {
                        "target_role_id": target_role_id,
                        "signals": adopted_signals,
                        "scenario_limit": int(case.get("scenario_limit", 3)),
                    }
                )
                base_recommend = service.recommend(build_recommend_payload(case.get("text", ""), case.get("signals", [])))
                adopted_recommend = service.recommend(build_recommend_payload("", adopted_signals))
            except Exception as exc:  # pragma: no cover - defensive path for report generation
                failure_reasons.append(f"adopt recompute failed: {exc}")
            else:
                adopted_target = adopted_role_gap.get("target_role", {})
                adopted_score = float(adopted_target.get("current_score", 0.0) or 0.0)
                adopted_score_delta = round(adopted_score - float(target.get("current_score", 0.0) or 0.0), 4)
                adopted_rank_before = find_role_rank(base_recommend, target_role_id)
                adopted_rank_after = find_role_rank(adopted_recommend, target_role_id)
                require_non_worse_score = bool(case.get("require_non_worse_score_after_adopt", True))
                require_non_worse_rank = bool(case.get("require_non_worse_rank_after_adopt", True))
                score_ok = not require_non_worse_score or adopted_score_delta >= 0.0
                rank_ok = not require_non_worse_rank or adopted_rank_after <= adopted_rank_before
                adopt_basis = classify_adopt_basis(
                    require_non_worse_score,
                    require_non_worse_rank,
                    score_ok,
                    rank_ok,
                )
                adopt_non_regression = score_ok or rank_ok
                if not adopt_non_regression:
                    failure_reasons.append(
                        "adopted profile regressed on both score and rank: "
                        f"score {target.get('current_score', 0.0):.4f}->{adopted_score:.4f}, "
                        f"rank {adopted_rank_before}->{adopted_rank_after}"
                    )

    case_pass = (
        gap_ok
        and learning_path_ok
        and action_template_ok
        and priority_ok
        and focus_ok
        and missing_ok
        and first_step_relation_ok
        and first_step_delta_positive
        and first_step_action_ok
        and simulation_positive
        and simulation_boost_ok
        and adopt_non_regression
        and not selection_errors
    )

    return {
        "id": case["id"],
        "target_role_id": target_role_id,
        "target_role_name": target.get("job_name"),
        "current_score": float(target.get("current_score", 0.0) or 0.0),
        "gap_ok": gap_ok,
        "learning_path_ok": learning_path_ok,
        "action_template_ok": action_template_ok,
        "simulation_positive": simulation_positive,
        "adopt_non_regression": adopt_non_regression,
        "focus_ok": focus_ok,
        "priority_ok": priority_ok,
        "missing_ok": missing_ok,
        "first_step_relation_ok": first_step_relation_ok,
        "first_step_delta_positive": first_step_delta_positive,
        "selected_action_keys": selected_action_keys,
        "selected_template_ids": selected_template_ids,
        "simulation_bundle_size": simulation_bundle_size,
        "simulation_delta_score": round(simulation_delta_score, 4),
        "simulation_rank_before": simulation_rank_before,
        "simulation_rank_after": simulation_rank_after,
        "adopted_score": round(adopted_score, 4),
        "adopted_score_delta": round(adopted_score_delta, 4),
        "adopted_rank_before": adopted_rank_before,
        "adopted_rank_after": adopted_rank_after,
        "adopt_basis": adopt_basis,
        "focus_node_ids": focus_node_ids,
        "priority_node_ids": priority_node_ids,
        "missing_requirements": missing_requirements,
        "case_pass": case_pass,
        "failure_reasons": failure_reasons,
    }


def summarize_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    total_cases = len(results)
    gap_count = sum(1 for item in results if item["gap_ok"])
    learning_path_count = sum(1 for item in results if item["learning_path_ok"])
    action_template_count = sum(1 for item in results if item["action_template_ok"])
    simulation_count = sum(1 for item in results if item["simulation_positive"])
    adopt_count = sum(1 for item in results if item["adopt_non_regression"])
    focus_count = sum(1 for item in results if item["focus_ok"])
    pass_count = sum(1 for item in results if item["case_pass"])

    return {
        "total_cases": total_cases,
        "gap_coverage": gap_count / total_cases if total_cases else 0.0,
        "learning_path_coverage": learning_path_count / total_cases if total_cases else 0.0,
        "action_template_coverage": action_template_count / total_cases if total_cases else 0.0,
        "simulation_positive_rate": simulation_count / total_cases if total_cases else 0.0,
        "adopt_non_regression_rate": adopt_count / total_cases if total_cases else 0.0,
        "focus_match_rate": focus_count / total_cases if total_cases else 0.0,
        "pass_rate": pass_count / total_cases if total_cases else 0.0,
        "pass_count": pass_count,
    }


def validate_thresholds(summary: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    for metric, threshold in QUALITY_THRESHOLDS.items():
        if summary[metric] < threshold:
            failures.append(f"{metric} below threshold: {summary[metric]:.2f}")
    return failures


def build_markdown_report(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Planning Benchmark Report",
        "",
        f"- Generated At: `{payload['generated_at']}`",
        f"- Total Cases: `{summary['total_cases']}`",
        f"- Gap Coverage: `{summary['gap_coverage']:.2f}`",
        f"- Learning Path Coverage: `{summary['learning_path_coverage']:.2f}`",
        f"- Action Template Coverage: `{summary['action_template_coverage']:.2f}`",
        f"- Simulation Positive Rate: `{summary['simulation_positive_rate']:.2f}`",
        f"- Adopt Non-Regression Rate: `{summary['adopt_non_regression_rate']:.2f}`",
        f"- Focus Match Rate: `{summary['focus_match_rate']:.2f}`",
        f"- Pass Rate: `{summary['pass_rate']:.2f}`",
        "",
        "## Thresholds",
        "",
        f"- Gap Coverage >= `{payload['thresholds']['gap_coverage']:.2f}`",
        f"- Learning Path Coverage >= `{payload['thresholds']['learning_path_coverage']:.2f}`",
        f"- Action Template Coverage >= `{payload['thresholds']['action_template_coverage']:.2f}`",
        f"- Simulation Positive Rate >= `{payload['thresholds']['simulation_positive_rate']:.2f}`",
        f"- Adopt Non-Regression Rate >= `{payload['thresholds']['adopt_non_regression_rate']:.2f}`",
        f"- Focus Match Rate >= `{payload['thresholds']['focus_match_rate']:.2f}`",
        "",
        "Adopt Basis uses OR semantics: `score+rank`, `score_only`, `rank_only`, `regressed`.",
        "",
        "## Cases",
        "",
        "| Case | Status | Target Role | Focus Nodes | Selected Actions | Sim Delta | Adopt Delta | Adopt Basis | Rank Change | Failure Reasons |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for result in payload["results"]:
        focus_label = ", ".join(result.get("focus_node_ids", [])[:2]) or "-"
        actions_label = ", ".join(result.get("selected_template_ids", [])[:2]) or "-"
        rank_before = result.get("adopted_rank_before")
        rank_after = result.get("adopted_rank_after")
        rank_label = (
            f"{rank_before} -> {rank_after}"
            if rank_before is not None and rank_after is not None
            else "-"
        )
        failure_label = "; ".join(result.get("failure_reasons", [])) or "-"
        lines.append(
            f"| {result['id']} | {'PASS' if result['case_pass'] else 'FAIL'} | "
            f"{format_role_label(result.get('target_role_id'), result.get('target_role_name'))} | "
            f"{focus_label} | {actions_label} | {result['simulation_delta_score']:.4f} | "
            f"{result['adopted_score_delta']:.4f} | {result.get('adopt_basis', 'not_evaluated')} | "
            f"{rank_label} | {failure_label} |"
        )
    return "\n".join(lines) + "\n"


def write_report(payload: dict[str, Any]) -> None:
    REPORT_JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    REPORT_MD_PATH.write_text(build_markdown_report(payload), encoding="utf-8")


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
            f"[{status}] {result['id']} target={result['target_role_id']} "
            f"sim_delta={result['simulation_delta_score']:.4f} "
            f"adopt_delta={result['adopted_score_delta']:.4f} "
            f"rank={result['adopted_rank_before']}->{result['adopted_rank_after']} "
            f"adopt_basis={result.get('adopt_basis', 'not_evaluated')}"
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
        "planning benchmark summary "
        f"gap={summary['gap_coverage']:.2f} path={summary['learning_path_coverage']:.2f} "
        f"actions={summary['action_template_coverage']:.2f} sim={summary['simulation_positive_rate']:.2f} "
        f"adopt={summary['adopt_non_regression_rate']:.2f}"
    )
    print(f"reports written to {REPORT_JSON_PATH.relative_to(ROOT)} and {REPORT_MD_PATH.relative_to(ROOT)}")

    if failures:
        raise SystemExit("\n".join(failures))


if __name__ == "__main__":
    main()
