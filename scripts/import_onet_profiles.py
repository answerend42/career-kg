from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any
from urllib.request import Request, urlopen


USER_AGENT = "Mozilla/5.0 (compatible; CareerKGImporter/1.0; +https://www.onetonline.org/)"
PLACEHOLDER_SUMMARY_MARKERS = (
    "a subset of this occupation's profile is available.",
    "data collection is currently underway",
)


@dataclass(slots=True)
class OnetSourceSnapshot:
    source_title: str
    summary_excerpt: str
    sample_job_titles: list[str]


class OnetPageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_title = False
        self.in_paragraph = False
        self.title_parts: list[str] = []
        self.current_paragraph: list[str] = []
        self.paragraphs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "title":
            self.in_title = True
        elif tag == "p":
            self.in_paragraph = True
            self.current_paragraph = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.in_title = False
        elif tag == "p":
            text = " ".join("".join(self.current_paragraph).split())
            if text:
                self.paragraphs.append(text)
            self.in_paragraph = False

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_parts.append(data)
        elif self.in_paragraph:
            self.current_paragraph.append(data)

    def build_snapshot(self) -> OnetSourceSnapshot:
        title = " ".join("".join(self.title_parts).split())
        meaningful_paragraphs = [
            paragraph
            for paragraph in self.paragraphs
            if paragraph
            and paragraph.lower() != "back to top"
            and not paragraph.startswith("Example apprenticeship titles")
            and not paragraph.startswith("Specific title(s)")
            and not paragraph.startswith("How much education")
            and not paragraph.startswith("Source:")
        ]
        summary_candidates = [
            paragraph
            for paragraph in meaningful_paragraphs
            if not self._is_placeholder_summary(paragraph)
        ]
        summary_excerpt = summary_candidates[0] if summary_candidates else (meaningful_paragraphs[0] if meaningful_paragraphs else "")
        sample_job_titles: list[str] = []
        for paragraph in meaningful_paragraphs[1:6]:
            if paragraph.startswith("Sample of reported job titles:"):
                raw_titles = paragraph.split(":", 1)[1]
                sample_job_titles = [item.strip() for item in raw_titles.split(",") if item.strip()][:6]
                break
        return OnetSourceSnapshot(
            source_title=title,
            summary_excerpt=summary_excerpt,
            sample_job_titles=sample_job_titles,
        )

    @staticmethod
    def _is_placeholder_summary(paragraph: str) -> bool:
        lowered = paragraph.lower()
        return any(marker in lowered for marker in PLACEHOLDER_SUMMARY_MARKERS)


def fetch_onet_snapshot(url: str) -> OnetSourceSnapshot:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    html = urlopen(request).read().decode("utf-8", errors="ignore")
    parser = OnetPageParser()
    parser.feed(html)
    return parser.build_snapshot()


def import_onet_profiles(manifest: list[dict[str, Any]], snapshot_date: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    raw_profiles: list[dict[str, Any]] = []
    imported_profiles: list[dict[str, Any]] = []

    for entry in manifest:
        snapshot = fetch_onet_snapshot(entry["source_url"])
        raw_profile = {
            "profile_id": entry["profile_id"],
            "source_type": entry["source_type"],
            "source_id": entry["source_id"],
            "source_url": entry["source_url"],
            "source_title": snapshot.source_title,
            "snapshot_date": snapshot_date,
            "summary_excerpt": snapshot.summary_excerpt,
            "sample_job_titles": snapshot.sample_job_titles,
            "mapped_node_ids": entry["mapped_node_ids"],
            "profile_tags": entry.get("profile_tags", []),
            "source_note": entry.get("source_note", ""),
        }
        raw_profiles.append(raw_profile)
        imported_profiles.append(
            {
                "profile_id": raw_profile["profile_id"],
                "source_type": raw_profile["source_type"],
                "source_id": raw_profile["source_id"],
                "source_url": raw_profile["source_url"],
                "source_title": raw_profile["source_title"],
                "snapshot_date": raw_profile["snapshot_date"],
                "evidence_snippet": raw_profile["summary_excerpt"],
                "sample_job_titles": raw_profile["sample_job_titles"],
                "mapped_node_ids": raw_profile["mapped_node_ids"],
                "profile_tags": raw_profile["profile_tags"],
            }
        )

    return raw_profiles, imported_profiles
