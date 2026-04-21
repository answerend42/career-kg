from __future__ import annotations

import unittest
from pathlib import Path

from scripts.source_validation import validate_sources


ROOT = Path(__file__).resolve().parents[1]


class SourceValidationTests(unittest.TestCase):
    def test_validate_sources_accepts_current_bundle(self) -> None:
        summary = validate_sources(ROOT)
        self.assertGreaterEqual(summary["skill_items"], 150)
        self.assertGreaterEqual(summary["template_items"], 70)
        self.assertGreaterEqual(summary["role_items"], 40)
        self.assertGreaterEqual(summary["known_node_ids"], 300)


if __name__ == "__main__":
    unittest.main()
