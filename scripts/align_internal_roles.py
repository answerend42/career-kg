#!/usr/bin/env python3

from __future__ import annotations

import argparse
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

from build_term_lexicon import external_occ_id, strip_onet_code
from normalize_raw_documents import ROOT, PIPELINE_DATE, PIPELINE_VERSION, read_json, tokenize_text, write_json


NODES_PATH = ROOT / "data" / "seeds" / "nodes.json"
EDGES_PATH = ROOT / "data" / "seeds" / "edges.json"
ALIASES_PATH = ROOT / "data" / "dictionaries" / "skill_aliases.json"
ONET_PROFILES_PATH = ROOT / "data" / "sources" / "raw" / "onet_profiles.json"
LINKS_PATH = ROOT / "data" / "canonical" / "entity_links.json"
DEFAULT_OUTPUT = ROOT / "data" / "alignment" / "occupation_alignment.json"


def jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def load_nodes() -> dict[str, dict[str, Any]]:
    return {str(node.get("id")): node for node in read_json(NODES_PATH, default=[]) if isinstance(node, dict) and node.get("id")}


def role_tokens(role: dict[str, Any], aliases: dict[str, list[str]]) -> set[str]:
    metadata = role.get("metadata", {}) if isinstance(role.get("metadata"), dict) else {}
    text_parts = [role.get("id", ""), role.get("name", ""), role.get("description", ""), metadata.get("family", "")]
    text_parts.extend(aliases.get(str(role.get("id", "")), []))
    return tokenize_text(" ".join(str(part) for part in text_parts))


def profile_tokens(profile: dict[str, Any]) -> set[str]:
    text_parts = [
        strip_onet_code(str(profile.get("source_title", ""))),
        profile.get("summary_excerpt", ""),
        profile.get("source_note", ""),
        " ".join(str(item) for item in profile.get("sample_job_titles", [])),
        " ".join(str(item) for item in profile.get("profile_tags", [])),
    ]
    return tokenize_text(" ".join(str(part) for part in text_parts))


def upstream_evidence_by_role(nodes: dict[str, dict[str, Any]]) -> dict[str, set[str]]:
    incoming: dict[str, set[str]] = defaultdict(set)
    for edge in read_json(EDGES_PATH, default=[]):
        if isinstance(edge, dict):
            incoming[str(edge.get("target", ""))].add(str(edge.get("source", "")))

    evidence_nodes = {node_id for node_id, node in nodes.items() if str(node.get("layer")) == "evidence"}
    roles = [node_id for node_id, node in nodes.items() if str(node.get("layer")) == "role"]
    result: dict[str, set[str]] = {}
    for role_id in roles:
        seen: set[str] = set()
        evidence: set[str] = set()
        queue: deque[str] = deque([role_id])
        while queue:
            current = queue.popleft()
            for parent in incoming.get(current, set()):
                if parent in seen:
                    continue
                seen.add(parent)
                if parent in evidence_nodes:
                    evidence.add(parent)
                else:
                    queue.append(parent)
        result[role_id] = evidence
    return result


def profile_linked_evidence() -> dict[str, set[str]]:
    payload = read_json(LINKS_PATH, default={"links": []})
    linked: dict[str, set[str]] = defaultdict(set)
    for link in payload.get("links", []):
        if not isinstance(link, dict):
            continue
        doc_id = str(link.get("doc_id", ""))
        concept_id = str(link.get("chosen_concept_id", ""))
        if concept_id.startswith(("skill_", "tool_", "knowledge_", "project_", "soft_skill_", "language_")):
            linked[doc_id].add(concept_id)
    return linked


def mapping_type(score: float, crosswalk_support: bool, skill_overlap: float) -> str:
    if score >= 0.93 and (crosswalk_support or skill_overlap >= 0.2):
        return "exactMatch"
    if score >= 0.76:
        return "closeMatch"
    if crosswalk_support:
        return "broadMatch"
    if score >= 0.45:
        return "relatedMatch"
    return "unmapped"


def review_status(score: float, crosswalk_support: bool) -> str:
    if crosswalk_support:
        return "reviewed"
    if score >= 0.82:
        return "auto_high_confidence"
    if score >= 0.45:
        return "needs_review"
    return "unmapped"


def align_roles() -> dict[str, Any]:
    nodes = load_nodes()
    aliases = read_json(ALIASES_PATH, default={})
    profiles = [profile for profile in read_json(ONET_PROFILES_PATH, default=[]) if isinstance(profile, dict)]
    role_evidence = upstream_evidence_by_role(nodes)
    linked_evidence = profile_linked_evidence()

    roles = sorted((node for node in nodes.values() if str(node.get("layer")) == "role"), key=lambda node: str(node.get("id")))
    mappings: list[dict[str, Any]] = []
    review_queue: list[dict[str, Any]] = []

    for role in roles:
        role_id = str(role.get("id", ""))
        role_meta = role.get("metadata", {}) if isinstance(role.get("metadata"), dict) else {}
        family = str(role_meta.get("family", ""))
        role_token_set = role_tokens(role, aliases)
        candidates: list[dict[str, Any]] = []
        for profile in profiles:
            profile_id = str(profile.get("profile_id", ""))
            profile_token_set = profile_tokens(profile)
            profile_tags = {str(tag).casefold() for tag in profile.get("profile_tags", [])}
            title_similarity = jaccard(role_token_set, profile_token_set)
            role_skills = role_evidence.get(role_id, set())
            profile_skills = linked_evidence.get(profile_id, set())
            skill_overlap = jaccard(role_skills, profile_skills)
            family_prior = 1.0 if family and family.casefold() in profile_tags else 0.0
            if not family_prior and role_token_set & profile_tags:
                family_prior = 0.55
            crosswalk_support = role_id in {str(item) for item in profile.get("mapped_node_ids", [])}
            crosswalk_bonus = 1.0 if crosswalk_support else 0.0
            score = round(
                min(0.99, 0.34 * title_similarity + 0.26 * skill_overlap + 0.2 * family_prior + 0.2 * crosswalk_bonus),
                4,
            )
            if crosswalk_support:
                curated_floor = 0.84 + 0.05 * family_prior + min(0.04, title_similarity) + min(0.04, skill_overlap)
                score = round(max(score, min(0.95, curated_floor)), 4)
            candidates.append(
                {
                    "crosswalk_support": crosswalk_support,
                    "evidence": {
                        "crosswalk_support": crosswalk_support,
                        "family_prior": round(family_prior, 4),
                        "skill_overlap": round(skill_overlap, 4),
                        "title_similarity": round(title_similarity, 4),
                    },
                    "external_id": str(profile.get("source_id", "")),
                    "external_label": strip_onet_code(str(profile.get("source_title", ""))),
                    "external_scheme": "onet",
                    "profile_id": profile_id,
                    "score": score,
                }
            )

        candidates.sort(key=lambda item: (-float(item["score"]), not bool(item["crosswalk_support"]), str(item["external_id"])))
        for rank, candidate in enumerate(candidates[:3], start=1):
            score = float(candidate["score"])
            crosswalk_support = bool(candidate["crosswalk_support"])
            mtype = mapping_type(score, crosswalk_support, float(candidate["evidence"]["skill_overlap"]))
            status = review_status(score, crosswalk_support)
            record = {
                "candidate_rank": rank,
                "confidence": score,
                "evidence": candidate["evidence"],
                "external_concept_id": external_occ_id({"source_type": "onet", "source_id": candidate["external_id"]}),
                "external_id": candidate["external_id"],
                "external_label": candidate["external_label"],
                "external_scheme": "onet",
                "internal_concept_id": role_id,
                "internal_label": str(role.get("name", "")),
                "mapping_type": mtype,
                "review_status": status,
                "reviewed_at": PIPELINE_DATE if crosswalk_support else "",
                "reviewer": "curated_manifest" if crosswalk_support else "",
            }
            mappings.append(record)
            if status == "needs_review":
                review_queue.append(record)

    accepted = [item for item in mappings if item["candidate_rank"] == 1 and item["mapping_type"] != "unmapped"]
    return {
        "accepted_top1_count": len(accepted),
        "mapping_semantics": ["exactMatch", "closeMatch", "broadMatch", "narrowMatch", "relatedMatch"],
        "mappings": mappings,
        "pipeline_date": PIPELINE_DATE,
        "pipeline_version": PIPELINE_VERSION,
        "review_queue": review_queue,
        "review_queue_count": len(review_queue),
        "role_count": len(roles),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Align internal career roles to O*NET occupation profiles.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    payload = align_roles()
    write_json(args.output, payload)
    print(f"aligned {payload['role_count']} roles -> {args.output.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
