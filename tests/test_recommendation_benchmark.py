from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.run_recommendation_benchmark import (
    BENCHMARK_PATH,
    QUALITY_THRESHOLDS,
    ROOT,
    evaluate_case,
    summarize_results,
    validate_thresholds,
)
from backend.app.api.recommend import RecommendationService


class RecommendationBenchmarkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.service = RecommendationService(ROOT)
        cls.cases = json.loads(BENCHMARK_PATH.read_text(encoding="utf-8"))

    def test_benchmark_cases_cover_multiple_directions(self) -> None:
        self.assertGreaterEqual(len(self.cases), 8)
        case_ids = {case["id"] for case in self.cases}
        self.assertIn("backend_nl", case_ids)
        self.assertIn("security_structured", case_ids)
        self.assertIn("frontend_structured", case_ids)

    def test_recommendation_benchmark_thresholds_pass(self) -> None:
        results = [evaluate_case(self.service, case) for case in self.cases]
        summary = summarize_results(results)

        self.assertGreaterEqual(summary["hit_at_3"], QUALITY_THRESHOLDS["hit_at_3"])
        self.assertGreaterEqual(summary["hit_at_5"], QUALITY_THRESHOLDS["hit_at_5"])
        self.assertEqual(summary["forbidden_role_violations"], QUALITY_THRESHOLDS["forbidden_role_violations"])
        self.assertGreaterEqual(summary["explanation_coverage"], QUALITY_THRESHOLDS["explanation_coverage"])
        self.assertGreaterEqual(summary["provenance_coverage"], QUALITY_THRESHOLDS["provenance_coverage"])
        self.assertFalse(validate_thresholds(summary))
        self.assertTrue(all(result["matched_role_name"] for result in results if result["case_pass"]))

    def test_evaluate_case_surfaces_failure_reasons(self) -> None:
        class FakeRecommendationService:
            def recommend(self, payload: dict[str, object]) -> dict[str, object]:
                return {
                    "recommendations": [
                        {
                            "job_id": "role_forbidden",
                            "job_name": "Forbidden Role",
                            "score": 0.91,
                            "paths": [],
                            "provenance_count": 0,
                            "source_types": [],
                        }
                    ]
                }

        result = evaluate_case(
            FakeRecommendationService(),
            {
                "id": "failing_case",
                "text": "irrelevant",
                "top_k": 5,
                "expected_roles_any": ["role_backend_engineer"],
                "forbidden_roles": ["role_forbidden"],
                "expected_explanation_nodes_any": ["cap_backend_engineering"],
                "expected_source_types_any": ["onet_online"],
                "min_provenance_count": 2,
            },
        )

        self.assertFalse(result["case_pass"])
        self.assertEqual(result["matched_role_name"], None)
        self.assertEqual(len(result["failure_reasons"]), 4)
        self.assertIn("expected role missing from Top-5", result["failure_reasons"][0])
        self.assertIn("forbidden roles appeared", result["failure_reasons"][1])
        self.assertIn("missing expected explanation nodes", result["failure_reasons"][2])
        self.assertIn("provenance requirement unmet", result["failure_reasons"][3])


if __name__ == "__main__":
    unittest.main()
