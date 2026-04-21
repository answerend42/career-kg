#!/usr/bin/env python3

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

from normalize_raw_documents import ROOT, PIPELINE_DATE, PIPELINE_VERSION, normalized_key, read_json, stable_id, write_json


DOCUMENTS_PATH = ROOT / "data" / "staging" / "normalized_documents.json"
LEXICON_PATH = ROOT / "data" / "canonical" / "term_lexicon.json"
DEFAULT_OUTPUT = ROOT / "data" / "canonical" / "entity_links.json"

SOURCE_BASE_SCORE = {
    "seed_node_name": 0.95,
    "external_profile_title": 0.95,
    "seed_alias": 0.89,
    "rule_expansion": 0.86,
    "external_job_title": 0.82,
    "external_profile_tag": 0.68,
}

SECTION_PRIOR = {
    "title": 0.04,
    "sample_job_titles": 0.03,
    "summary": 0.02,
    "description": 0.01,
    "tags": 0.0,
}


def should_match_term(term: dict[str, Any]) -> bool:
    normalized = str(term.get("normalized", ""))
    if len(normalized) >= 2:
        return True
    return normalized in {"c", "r"}


def term_pattern(surface: str) -> re.Pattern[str]:
    escaped = re.escape(surface)
    if re.fullmatch(r"[A-Za-z0-9+#. -]+", surface):
        return re.compile(rf"(?<![A-Za-z0-9+#]){escaped}(?![A-Za-z0-9+#])", re.IGNORECASE)
    return re.compile(escaped, re.IGNORECASE)


def score_candidate(term: dict[str, Any], section_type: str, exact_preferred: bool) -> float:
    score = SOURCE_BASE_SCORE.get(str(term.get("source")), 0.62)
    score += SECTION_PRIOR.get(section_type, 0.0)
    if exact_preferred:
        score += 0.02
    return round(min(score, 0.99), 4)


def status_for_score(score: float, candidate_count: int) -> str:
    if score >= 0.88 and candidate_count <= 6:
        return "auto_high_confidence"
    if score >= 0.65:
        return "auto_low_confidence"
    return "needs_review"


def load_terms(path: Path) -> list[dict[str, Any]]:
    payload = read_json(path, default={"terms": []})
    terms = [term for term in payload.get("terms", []) if isinstance(term, dict) and should_match_term(term)]
    terms.sort(key=lambda term: (-len(str(term.get("surface", ""))), str(term.get("normalized", "")), str(term.get("concept_id", ""))))
    return terms


def link_section(doc: dict[str, Any], section: dict[str, Any], terms: list[dict[str, Any]]) -> list[dict[str, Any]]:
    text = str(section.get("text", ""))
    if not text:
        return []
    matches: dict[tuple[int, int, str], list[dict[str, Any]]] = {}
    for term in terms:
        surface = str(term.get("surface", ""))
        if not surface:
            continue
        for match in term_pattern(surface).finditer(text):
            mention = text[match.start() : match.end()]
            if normalized_key(mention) != str(term.get("normalized", "")):
                continue
            key = (match.start(), match.end(), normalized_key(mention))
            exact_preferred = bool(term.get("preferred")) and normalized_key(surface) == normalized_key(mention)
            score = score_candidate(term, str(section.get("section_type", "")), exact_preferred)
            matches.setdefault(key, []).append(
                {
                    "concept_id": str(term.get("concept_id", "")),
                    "concept_type": str(term.get("concept_type", "")),
                    "matched_by": str(term.get("source", "")),
                    "score": score,
                    "term_id": str(term.get("term_id", "")),
                }
            )

    links: list[dict[str, Any]] = []
    occupied: list[tuple[int, int]] = []
    for (start, end, normalized), candidates in sorted(matches.items(), key=lambda item: (item[0][0], -(item[0][1] - item[0][0]))):
        if any(start < existing_end and end > existing_start for existing_start, existing_end in occupied):
            continue
        deduped = {
            candidate["concept_id"]: candidate
            for candidate in sorted(candidates, key=lambda item: (-float(item["score"]), str(item["concept_id"])))
            if candidate["concept_id"]
        }
        ranked = sorted(deduped.values(), key=lambda item: (-float(item["score"]), str(item["concept_id"])))[:8]
        if not ranked:
            continue
        chosen = ranked[0]
        occupied.append((start, end))
        links.append(
            {
                "candidate_concepts": ranked,
                "chosen_concept_id": chosen["concept_id"],
                "doc_id": str(doc.get("doc_id", "")),
                "evidence": {
                    "matched_by": chosen["matched_by"],
                    "section_id": str(section.get("section_id", "")),
                    "section_type": str(section.get("section_type", "")),
                    "source_name": str(doc.get("source_name", "")),
                },
                "link_id": f"link_{stable_id(doc.get('doc_id'), section.get('section_id'), start, end, chosen['concept_id'])}",
                "link_status": status_for_score(float(chosen["score"]), len(ranked)),
                "mention": text[start:end],
                "normalized_mention": normalized,
                "score": chosen["score"],
                "span": [start, end],
            }
        )
    return links


def link_entities(documents_path: Path = DOCUMENTS_PATH, lexicon_path: Path = LEXICON_PATH) -> list[dict[str, Any]]:
    documents_payload = read_json(documents_path, default={"documents": []})
    terms = load_terms(lexicon_path)
    links: list[dict[str, Any]] = []
    for doc in documents_payload.get("documents", []):
        if not isinstance(doc, dict):
            continue
        for doc_section in doc.get("sections", []):
            if isinstance(doc_section, dict):
                links.extend(link_section(doc, doc_section, terms))
    links.sort(key=lambda item: (str(item["doc_id"]), str(item["evidence"]["section_id"]), item["span"][0], str(item["chosen_concept_id"])))
    return links


def build_payload(links: list[dict[str, Any]]) -> dict[str, Any]:
    status_counts: dict[str, int] = {}
    for link in links:
        status = str(link["link_status"])
        status_counts[status] = status_counts.get(status, 0) + 1
    review_queue = [link for link in links if link["link_status"] != "auto_high_confidence"]
    return {
        "link_count": len(links),
        "link_status_counts": dict(sorted(status_counts.items())),
        "links": links,
        "pipeline_date": PIPELINE_DATE,
        "pipeline_version": PIPELINE_VERSION,
        "review_queue": review_queue,
        "review_queue_count": len(review_queue),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Link normalized document mentions to canonical/internal concepts.")
    parser.add_argument("--documents", type=Path, default=DOCUMENTS_PATH)
    parser.add_argument("--lexicon", type=Path, default=LEXICON_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    links = link_entities(args.documents, args.lexicon)
    write_json(args.output, build_payload(links))
    print(f"linked {len(links)} mentions -> {args.output.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
