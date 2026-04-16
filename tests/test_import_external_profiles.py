from __future__ import annotations

import unittest

from scripts.import_external_profiles import OnetPageParser


class OnetPageParserTests(unittest.TestCase):
    def test_placeholder_subset_paragraph_is_not_used_as_summary(self) -> None:
        html = """
        <html>
          <head><title>15-2051.00 - Data Scientists</title></head>
          <body>
            <p>A subset of this occupation's profile is available. Data collection is currently underway to populate other parts of the profile. For more specific occupations, see:</p>
            <p>Develop and implement a set of techniques or analytics applications to transform raw data into meaningful information using data-oriented programming languages and visualization software.</p>
          </body>
        </html>
        """

        parser = OnetPageParser()
        parser.feed(html)
        snapshot = parser.build_snapshot()

        self.assertEqual(snapshot.source_title, "15-2051.00 - Data Scientists")
        self.assertIn("Develop and implement a set of techniques", snapshot.summary_excerpt)
        self.assertNotIn("A subset of this occupation's profile is available", snapshot.summary_excerpt)


if __name__ == "__main__":
    unittest.main()
