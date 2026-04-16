from __future__ import annotations

import json
import re
from dataclasses import dataclass
from html import unescape
from typing import Any
from urllib.request import Request, urlopen


USER_AGENT = "Mozilla/5.0 (compatible; CareerKGImporter/1.0; +https://roadmap.sh/)"
JSON_LD_PATTERN = re.compile(
    r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)
META_DESCRIPTION_PATTERN = re.compile(
    r'<meta[^>]+name="description"[^>]+content="([^"]+)"',
    re.IGNORECASE,
)
TAG_PATTERN = re.compile(r"<[^>]+>")


@dataclass(slots=True)
class RoadmapSourceSnapshot:
    source_title: str
    page_description: str
    evidence_excerpt: str
    sample_job_titles: list[str]
    published_date: str


def _normalize_text(value: str) -> str:
    return " ".join(TAG_PATTERN.sub(" ", unescape(value)).split())


def _extract_json_ld_items(html: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for raw_block in JSON_LD_PATTERN.findall(html):
        try:
            payload = json.loads(unescape(raw_block))
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            items.append(payload)
        elif isinstance(payload, list):
            items.extend(item for item in payload if isinstance(item, dict))
    return items


def parse_roadmap_snapshot(html: str, sample_job_titles: list[str] | None = None) -> RoadmapSourceSnapshot:
    json_ld_items = _extract_json_ld_items(html)

    blog_post = next((item for item in json_ld_items if item.get("@type") == "BlogPosting"), {})
    faq_page = next((item for item in json_ld_items if item.get("@type") == "FAQPage"), {})

    meta_match = META_DESCRIPTION_PATTERN.search(html)
    meta_description = _normalize_text(meta_match.group(1)) if meta_match else ""
    source_title = _normalize_text(str(blog_post.get("headline", ""))) or _normalize_text(str(blog_post.get("name", "")))
    published_date = _normalize_text(str(blog_post.get("dateModified", ""))) or _normalize_text(str(blog_post.get("datePublished", "")))
    page_description = _normalize_text(str(blog_post.get("description", ""))) or meta_description

    evidence_excerpt = ""
    for question in faq_page.get("mainEntity", []):
        answer_text = _normalize_text(str(question.get("acceptedAnswer", {}).get("text", "")))
        if answer_text:
            evidence_excerpt = answer_text
            break
    if not evidence_excerpt:
        evidence_excerpt = page_description

    return RoadmapSourceSnapshot(
        source_title=source_title,
        page_description=page_description,
        evidence_excerpt=evidence_excerpt,
        sample_job_titles=list(sample_job_titles or [])[:6],
        published_date=published_date,
    )


def fetch_roadmap_snapshot(url: str, sample_job_titles: list[str] | None = None) -> RoadmapSourceSnapshot:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    html = urlopen(request).read().decode("utf-8", errors="ignore")
    return parse_roadmap_snapshot(html, sample_job_titles=sample_job_titles)


def import_roadmap_profiles(manifest: list[dict[str, Any]], snapshot_date: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    raw_profiles: list[dict[str, Any]] = []
    imported_profiles: list[dict[str, Any]] = []

    for entry in manifest:
        snapshot = fetch_roadmap_snapshot(entry["source_url"], sample_job_titles=entry.get("sample_job_titles", []))
        raw_profile = {
            "profile_id": entry["profile_id"],
            "source_type": entry["source_type"],
            "source_id": entry["source_id"],
            "source_url": entry["source_url"],
            "source_title": snapshot.source_title,
            "snapshot_date": snapshot_date,
            "page_description": snapshot.page_description,
            "summary_excerpt": snapshot.evidence_excerpt,
            "sample_job_titles": snapshot.sample_job_titles,
            "mapped_node_ids": entry["mapped_node_ids"],
            "profile_tags": entry.get("profile_tags", []),
            "source_note": entry.get("source_note", ""),
            "published_date": snapshot.published_date,
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
