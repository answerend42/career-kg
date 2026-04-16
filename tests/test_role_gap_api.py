from __future__ import annotations

import unittest
from pathlib import Path

from backend.app.api.recommend import RecommendationService


ROOT = Path(__file__).resolve().parents[1]


class RoleGapApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.service = RecommendationService(ROOT)

    def test_role_gap_returns_missing_requirements_and_what_if_scenarios(self) -> None:
        result = self.service.role_gap(
            {
                "signals": [
                    {"entity": "偏好后端", "score": 0.9},
                ],
                "target_role_id": "role_backend_engineer",
                "scenario_limit": 3,
            }
        )
        target = result["target_role"]
        self.assertEqual(target["job_id"], "role_backend_engineer")
        self.assertIn("后端工程能力", target["missing_requirements"])
        self.assertGreater(len(target["priority_suggestions"]), 0)
        self.assertGreater(len(target["what_if_scenarios"]), 0)
        self.assertGreater(target["what_if_scenarios"][0]["predicted_score"], target["current_score"])
        self.assertGreater(target["what_if_scenarios"][0]["delta_score"], 0.0)
        self.assertGreater(len(target["what_if_scenarios"][0]["boosts"]), 0)

    def test_role_gap_rejects_unknown_target_role(self) -> None:
        with self.assertRaises(ValueError):
            self.service.role_gap(
                {
                    "signals": [
                        {"entity": "Python", "score": 0.8},
                    ],
                    "target_role_id": "role_not_exists",
                }
            )

    def test_role_gap_ml_target_parses_goal_and_negative_evidence_consistently(self) -> None:
        result = self.service.role_gap(
            {
                "text": "我会一点 Python 和 SQL，熟悉 Docker、Linux，想转机器学习，但数学基础很弱，也没做过训练项目。",
                "target_role_id": "role_ml_engineer",
                "scenario_limit": 3,
            }
        )
        normalized_map = {item["node_id"]: item["score"] for item in result["normalized_inputs"]}

        self.assertIn("interest_ml", normalized_map)
        self.assertLessEqual(normalized_map["knowledge_math_foundation"], 0.22)
        self.assertIn("constraint_dislike_math_theory", normalized_map)
        self.assertNotIn("project_model_training", normalized_map)


if __name__ == "__main__":
    unittest.main()
