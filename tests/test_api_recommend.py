from __future__ import annotations

import unittest
from pathlib import Path

from backend.app.api.recommend import RecommendationService


ROOT = Path(__file__).resolve().parents[1]


class RecommendationApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.service = RecommendationService(ROOT)

    def test_natural_language_input_maps_to_expected_nodes(self) -> None:
        payload = {
            "text": "我熟悉 Python 和 MySQL，做过 Flask 项目，会一点 Linux，不太擅长数学，更喜欢写后端接口。",
            "top_k": 5,
        }
        result = self.service.recommend(payload)
        normalized_ids = {item["node_id"] for item in result["normalized_inputs"]}
        self.assertIn("skill_python", normalized_ids)
        self.assertIn("tool_mysql", normalized_ids)
        self.assertIn("interest_backend", normalized_ids)
        self.assertIn("constraint_dislike_math_theory", normalized_ids)
        self.assertIsNotNone(result["propagation_snapshot"])
        self.assertGreater(len(result["propagation_snapshot"]["nodes"]), 0)
        self.assertGreater(len(result["recommendations"][0]["paths"]), 0)

    def test_negative_preferences_do_not_create_positive_frontend_signals(self) -> None:
        payload = {
            "text": "我不喜欢前端，也不想写 React，但是熟悉 Python 和 MySQL。",
            "top_k": 5,
        }
        result = self.service.recommend(payload)
        normalized_ids = {item["node_id"] for item in result["normalized_inputs"]}
        self.assertNotIn("interest_frontend", normalized_ids)
        self.assertNotIn("tool_react", normalized_ids)
        top_ids = [item["job_id"] for item in result["recommendations"][:3]]
        self.assertNotIn("role_frontend_engineer", top_ids)

    def test_non_object_payload_falls_back_to_default_request(self) -> None:
        result = self.service.recommend(["not", "an", "object"])  # type: ignore[arg-type]
        self.assertEqual(result["normalized_inputs"], [])
        self.assertEqual(len(result["recommendations"]), 5)

    def test_include_snapshot_string_false_disables_snapshot(self) -> None:
        result = self.service.recommend({"include_snapshot": "false"})
        self.assertIsNone(result["propagation_snapshot"])


if __name__ == "__main__":
    unittest.main()
