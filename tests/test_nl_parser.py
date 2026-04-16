from __future__ import annotations

import json
import unittest
from pathlib import Path

from backend.app.services.graph_loader import GraphLoader
from backend.app.services.nl_parser import LightweightNLParser


ROOT = Path(__file__).resolve().parents[1]


class NLParserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        loader = GraphLoader(ROOT)
        cls.parser = LightweightNLParser(
            loader.load_graph(),
            loader.load_aliases(),
            loader.load_preference_patterns(),
            loader.load_parsing_patterns(),
        )

    def test_colloquial_backend_sentence_hits_phrase_rules(self) -> None:
        result = self.parser.parse_detailed("我主攻接口开发，平时会写脚本清洗数据，也能接受 Linux 环境，不想做纯前端页面。")
        normalized_ids = {item.node_id for item in result.signals}
        self.assertIn("interest_backend", normalized_ids)
        self.assertIn("project_data_pipeline", normalized_ids)
        self.assertIn("tool_linux", normalized_ids)
        self.assertIn("constraint_dislike_ui_polish", normalized_ids)
        self.assertNotIn("interest_frontend", normalized_ids)
        self.assertGreater(len(result.debug["rule_hits"]), 0)

    def test_negative_page_wording_does_not_create_frontend_interest(self) -> None:
        result = self.parser.parse_detailed("我不太想写页面，但会一点 React。")
        normalized_ids = {item.node_id for item in result.signals}
        self.assertIn("constraint_dislike_ui_polish", normalized_ids)
        self.assertIn("tool_react", normalized_ids)
        self.assertNotIn("interest_frontend", normalized_ids)

    def test_demo_benchmark_expected_nodes_are_recalled(self) -> None:
        benchmark = json.loads((ROOT / "data" / "demo" / "nl_benchmark.json").read_text(encoding="utf-8"))
        for case in benchmark:
            with self.subTest(case=case["id"]):
                result = self.parser.parse_detailed(case["text"])
                normalized_ids = {item.node_id for item in result.signals}
                for expected_id in case.get("expected_nodes", []):
                    self.assertIn(expected_id, normalized_ids)
                for unexpected_id in case.get("unexpected_nodes", []):
                    self.assertNotIn(unexpected_id, normalized_ids)
                self.assertGreaterEqual(len(normalized_ids), int(case.get("min_signal_count", 0)))


if __name__ == "__main__":
    unittest.main()
