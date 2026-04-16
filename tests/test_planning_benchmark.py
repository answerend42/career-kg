from __future__ import annotations

import json
import unittest
from pathlib import Path

from backend.app.api.recommend import RecommendationService
from scripts.run_planning_benchmark import (
    BENCHMARK_PATH,
    QUALITY_THRESHOLDS,
    ROOT,
    build_markdown_report,
    classify_adopt_basis,
    evaluate_case,
    merge_adopted_signals,
    summarize_results,
    validate_thresholds,
)


class PlanningBenchmarkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.service = RecommendationService(ROOT)
        cls.cases = json.loads(BENCHMARK_PATH.read_text(encoding="utf-8"))

    def test_benchmark_cases_cover_multiple_directions(self) -> None:
        self.assertGreaterEqual(len(self.cases), 6)
        case_ids = {case["id"] for case in self.cases}
        self.assertIn("backend_bundle_nl", case_ids)
        self.assertIn("appsec_structured", case_ids)
        self.assertIn("devops_nl", case_ids)

    def test_planning_benchmark_thresholds_pass(self) -> None:
        results = [evaluate_case(self.service, case) for case in self.cases]
        summary = summarize_results(results)

        self.assertGreaterEqual(summary["gap_coverage"], QUALITY_THRESHOLDS["gap_coverage"])
        self.assertGreaterEqual(summary["learning_path_coverage"], QUALITY_THRESHOLDS["learning_path_coverage"])
        self.assertGreaterEqual(summary["action_template_coverage"], QUALITY_THRESHOLDS["action_template_coverage"])
        self.assertGreaterEqual(summary["simulation_positive_rate"], QUALITY_THRESHOLDS["simulation_positive_rate"])
        self.assertGreaterEqual(summary["adopt_non_regression_rate"], QUALITY_THRESHOLDS["adopt_non_regression_rate"])
        self.assertGreaterEqual(summary["focus_match_rate"], QUALITY_THRESHOLDS["focus_match_rate"])
        self.assertFalse(validate_thresholds(summary))
        self.assertTrue(all(result["case_pass"] for result in results))

    def test_merge_adopted_signals_prefers_higher_scores(self) -> None:
        merged = merge_adopted_signals(
            [
                {"node_id": "skill_python", "score": 0.6},
                {"node_id": "tool_linux", "score": 0.7},
            ],
            [
                {"node_id": "tool_linux", "to_score": 0.5},
                {"node_id": "project_ci_cd_platform", "to_score": 0.8},
                {"node_id": "skill_python", "to_score": 0.9},
            ],
        )

        self.assertEqual(
            merged,
            [
                {"entity": "project_ci_cd_platform", "score": 0.8},
                {"entity": "skill_python", "score": 0.9},
                {"entity": "tool_linux", "score": 0.7},
            ],
        )

    def test_classify_adopt_basis_marks_score_only_cases(self) -> None:
        self.assertEqual(classify_adopt_basis(True, True, True, True), "score+rank")
        self.assertEqual(classify_adopt_basis(True, True, True, False), "score_only")
        self.assertEqual(classify_adopt_basis(True, True, False, True), "rank_only")
        self.assertEqual(classify_adopt_basis(True, True, False, False), "regressed")

    def test_markdown_report_exposes_adopt_basis_for_rank_drop_cases(self) -> None:
        results = [evaluate_case(self.service, case) for case in self.cases]
        score_only_cases = [result for result in results if result.get("adopt_basis") == "score_only"]

        self.assertTrue(score_only_cases)

        report = build_markdown_report(
            {
                "generated_at": "2026-04-17T00:00:00",
                "summary": summarize_results(results),
                "thresholds": QUALITY_THRESHOLDS,
                "results": results,
            }
        )

        self.assertIn("Adopt Basis uses OR semantics", report)
        self.assertIn("| Adopt Basis |", report)
        self.assertIn("score_only", report)

    def test_evaluate_case_surfaces_failure_reasons(self) -> None:
        class FakePlanningService:
            def role_gap(self, payload: dict[str, object]) -> dict[str, object]:
                return {
                    "target_role": {
                        "job_id": "role_backend_engineer",
                        "job_name": "后端开发工程师",
                        "current_score": 0.0,
                        "missing_requirements": [],
                        "priority_suggestions": [],
                        "learning_path": [],
                    },
                    "normalized_inputs": [],
                }

        result = evaluate_case(
            FakePlanningService(),
            {
                "id": "failing_case",
                "target_role_id": "role_backend_engineer",
                "expected_missing_requirements_any": ["后端工程能力"],
                "expected_priority_nodes_any": ["cap_backend_engineering"],
                "expected_focus_nodes_any": ["cap_backend_engineering"],
                "expected_first_step_relation": "requires",
                "expected_action_template_ids_any": ["backend_gateway_hardening_project"],
                "simulation": {
                    "selectors": [{"step": 1, "action": 1}],
                    "expected_bundle_size": 1,
                    "require_positive_delta": True,
                },
            },
        )

        self.assertFalse(result["case_pass"])
        self.assertFalse(result["learning_path_ok"])
        self.assertFalse(result["priority_ok"])
        self.assertFalse(result["focus_ok"])
        self.assertGreaterEqual(len(result["failure_reasons"]), 5)
        self.assertIn("learning_path is empty or shorter than expected", result["failure_reasons"][0])
        self.assertTrue(any("priority suggestions missing expected nodes" in item for item in result["failure_reasons"]))
        self.assertTrue(any("missing expected requirements" in item for item in result["failure_reasons"]))
        self.assertTrue(any("missing learning path step" in item for item in result["failure_reasons"]))


if __name__ == "__main__":
    unittest.main()
