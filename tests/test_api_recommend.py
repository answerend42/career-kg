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
        self.assertEqual(result["recommendations"], [])

    def test_include_snapshot_string_false_disables_snapshot(self) -> None:
        result = self.service.recommend({"include_snapshot": "false"})
        self.assertIsNone(result["propagation_snapshot"])

    def test_catalog_exposes_evidence_nodes_and_sample_request(self) -> None:
        catalog = self.service.catalog()
        self.assertGreaterEqual(len(catalog["evidence_nodes"]), 150)
        self.assertIn("graph_stats", catalog)
        self.assertIn("sample_request", catalog)
        self.assertIn("text", catalog["sample_request"])
        python_node = next((item for item in catalog["evidence_nodes"] if item["id"] == "skill_python"), None)
        self.assertIsNotNone(python_node)
        self.assertIn("python", python_node["aliases"])

    def test_sample_request_filters_out_zero_score_roles(self) -> None:
        payload = self.service.sample_request()
        payload["top_k"] = 6
        result = self.service.recommend(payload)
        self.assertGreater(len(result["recommendations"]), 0)
        self.assertTrue(all(item["score"] >= 0.05 for item in result["recommendations"]))

    def test_colloquial_sentence_returns_debug_and_nonempty_recommendations(self) -> None:
        payload = {
            "text": "我主攻接口开发，平时会写脚本清洗数据，也能接受 Linux 环境，不想做纯前端页面。",
            "top_k": 6,
        }
        result = self.service.recommend(payload)
        normalized_ids = {item["node_id"] for item in result["normalized_inputs"]}
        self.assertIn("interest_backend", normalized_ids)
        self.assertIn("project_data_pipeline", normalized_ids)
        self.assertIn("constraint_dislike_ui_polish", normalized_ids)
        self.assertGreater(len(result["recommendations"]), 0)
        self.assertIn("parsing_debug", result)
        self.assertGreater(len(result["parsing_debug"]["rule_hits"]), 0)
        top_ids = [item["job_id"] for item in result["recommendations"][:3]]
        self.assertNotIn("role_frontend_engineer", top_ids)

    def test_empty_input_does_not_return_zero_score_pseudo_recommendations(self) -> None:
        result = self.service.recommend({"text": "", "signals": [], "top_k": 6})
        self.assertEqual(result["normalized_inputs"], [])
        self.assertEqual(result["recommendations"], [])


if __name__ == "__main__":
    unittest.main()
