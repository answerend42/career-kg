from __future__ import annotations

import unittest

from scripts.import_external_profiles import merge_imported_profiles
from scripts.import_onet_profiles import OnetPageParser
from scripts.import_roadmap_profiles import parse_roadmap_snapshot


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


class RoadmapImporterTests(unittest.TestCase):
    def test_roadmap_snapshot_uses_faq_answer_as_evidence_excerpt(self) -> None:
        html = """
        <html>
          <head>
            <title>Backend Developer Roadmap</title>
            <meta name="description" content="Step by step guide to becoming a modern backend developer in 2026" />
            <script type="application/ld+json">
              [
                {
                  "@context": "https://schema.org",
                  "@type": "BlogPosting",
                  "headline": "Backend Developer Roadmap: What is Backend Development",
                  "description": "Step by step guide to becoming a modern backend developer in 2026",
                  "dateModified": "2026-02-07"
                },
                {
                  "@context": "https://schema.org",
                  "@type": "FAQPage",
                  "mainEntity": [
                    {
                      "@type": "Question",
                      "name": "How to become a Backend Developer?",
                      "acceptedAnswer": {
                        "@type": "Answer",
                        "text": "If you are a complete beginner, you can start by learning a backend programming language such as Python or Go and then learn APIs, databases and deployment."
                      }
                    }
                  ]
                }
              ]
            </script>
          </head>
        </html>
        """
        snapshot = parse_roadmap_snapshot(
            html,
            sample_job_titles=["Backend Developer", "API Engineer"],
        )

        self.assertIn("Backend Developer", snapshot.source_title)
        self.assertIn("backend programming language", snapshot.evidence_excerpt.lower())
        self.assertEqual(snapshot.sample_job_titles, ["Backend Developer", "API Engineer"])
        self.assertTrue(snapshot.published_date)

    def test_merge_imported_profiles_rejects_duplicate_profile_ids(self) -> None:
        with self.assertRaises(ValueError):
            merge_imported_profiles(
                [
                    [{"profile_id": "dup", "source_type": "onet_online"}],
                    [{"profile_id": "dup", "source_type": "roadmap_sh"}],
                ]
            )


if __name__ == "__main__":
    unittest.main()
