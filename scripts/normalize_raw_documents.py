#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PIPELINE_VERSION = "20260421"
PIPELINE_DATE = "2026-04-21"

RAW_DIR = ROOT / "data" / "sources" / "raw"
DEFAULT_OUTPUT = ROOT / "data" / "staging" / "normalized_documents.json"


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def read_json(path: Path, default: Any | None = None) -> Any:
    if not path.exists():
        if default is not None:
            return default
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    ensure_parent(path)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def stable_sha256(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def stable_id(*parts: Any) -> str:
    text = "_".join(str(part) for part in parts if str(part).strip())
    text = text.lower()
    text = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "item"


def clean_text(value: Any) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("\u2019", "'").replace("\u201c", '"').replace("\u201d", '"')
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalized_key(value: Any) -> str:
    text = clean_text(value).casefold()
    text = text.replace(".net", "dotnet").replace("node.js", "nodejs")
    text = text.replace("c++", "cpp").replace("c#", "csharp")
    text = re.sub(r"[^a-z0-9\u4e00-\u9fff+#]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def tokenize_text(value: Any) -> set[str]:
    text = normalized_key(value)
    tokens = set(re.findall(r"[a-z0-9+#]{2,}|[\u4e00-\u9fff]{2,}", text))
    tokens.update(token for token in text.split() if len(token) >= 2)
    return tokens


def split_sentences(text: str) -> list[str]:
    if not text:
        return []
    chunks = re.split(r"(?<=[.!?。！？])\s+|(?<=[。！？])", text)
    return [chunk.strip() for chunk in chunks if chunk.strip()]


def infer_language(*values: Any) -> str:
    text = " ".join(clean_text(value) for value in values)
    has_cjk = bool(re.search(r"[\u4e00-\u9fff]", text))
    has_ascii_word = bool(re.search(r"[A-Za-z]{3,}", text))
    if has_cjk and has_ascii_word:
        return "mixed"
    if has_cjk:
        return "zh"
    return "en"


def section(section_id: str, section_type: str, text: str, raw_field: str) -> dict[str, Any] | None:
    cleaned = clean_text(text)
    if not cleaned:
        return None
    return {
        "raw_field": raw_field,
        "section_id": section_id,
        "section_type": section_type,
        "sentences": split_sentences(cleaned),
        "text": cleaned,
    }


def iter_profile_files(raw_dir: Path) -> list[Path]:
    return sorted(path for path in raw_dir.glob("*_profiles.json") if path.is_file())


def normalize_profile(profile: dict[str, Any], source_file: Path) -> dict[str, Any]:
    profile_id = str(profile.get("profile_id") or stable_id(profile.get("source_type"), profile.get("source_id")))
    source_type = str(profile.get("source_type") or source_file.stem)
    doc_id = stable_id(profile_id)
    title = clean_text(profile.get("source_title") or profile_id)

    sections: list[dict[str, Any]] = []
    candidates = [
        ("title", "title", title, "source_title"),
        ("description", "description", profile.get("page_description", ""), "page_description"),
        ("summary", "summary", profile.get("summary_excerpt") or profile.get("evidence_snippet", ""), "summary_excerpt"),
        ("source_note", "note", profile.get("source_note", ""), "source_note"),
    ]
    for raw_id, section_type, text, raw_field in candidates:
        item = section(f"{doc_id}_{raw_id}", section_type, text, raw_field)
        if item:
            sections.append(item)

    job_titles = [clean_text(item) for item in profile.get("sample_job_titles", []) if clean_text(item)]
    if job_titles:
        item = section(f"{doc_id}_sample_job_titles", "sample_job_titles", "; ".join(job_titles), "sample_job_titles")
        if item:
            sections.append(item)

    tags = [clean_text(item) for item in profile.get("profile_tags", []) if clean_text(item)]
    if tags:
        item = section(f"{doc_id}_tags", "tags", ", ".join(tags), "profile_tags")
        if item:
            sections.append(item)

    language = infer_language(title, *(item["text"] for item in sections))
    return {
        "content_type": "application/json; profile",
        "doc_id": doc_id,
        "external_id": str(profile.get("source_id", "")),
        "language": language,
        "license_note": "Derived from locally saved public profile metadata; verify upstream terms before redistribution.",
        "mapped_node_ids": sorted(str(item) for item in profile.get("mapped_node_ids", []) if str(item).strip()),
        "profile_id": profile_id,
        "profile_tags": tags,
        "raw_path": str(source_file.relative_to(ROOT)),
        "sample_job_titles": job_titles,
        "sections": sections,
        "sha256": stable_sha256(profile),
        "snapshot_time": str(profile.get("snapshot_date") or profile.get("published_date") or ""),
        "source_name": source_type,
        "source_url": str(profile.get("source_url", "")),
        "title": title,
    }


def normalize_documents(raw_dir: Path = RAW_DIR) -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []
    for path in iter_profile_files(raw_dir):
        payload = read_json(path, default=[])
        if not isinstance(payload, list):
            continue
        for profile in payload:
            if isinstance(profile, dict):
                documents.append(normalize_profile(profile, path))
    documents.sort(key=lambda item: (item["source_name"], item["doc_id"]))
    return documents


def build_payload(documents: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "document_count": len(documents),
        "documents": documents,
        "pipeline_date": PIPELINE_DATE,
        "pipeline_version": PIPELINE_VERSION,
        "source": "data/sources/raw/*_profiles.json",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Normalize raw external profile snapshots into sectioned documents.")
    parser.add_argument("--raw-dir", type=Path, default=RAW_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    documents = normalize_documents(args.raw_dir)
    write_json(args.output, build_payload(documents))
    print(f"normalized {len(documents)} documents -> {args.output.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
