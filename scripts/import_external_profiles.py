#!/usr/bin/env python3

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.import_onet_profiles import import_onet_profiles
from scripts.import_roadmap_profiles import import_roadmap_profiles


RAW_DIR = ROOT / "data" / "sources" / "raw"
IMPORTED_OUTPUT_PATH = ROOT / "data" / "sources" / "imported_profiles.json"
SOURCE_CONFIGS = [
    {
        "manifest_path": RAW_DIR / "onet_manifest.json",
        "raw_output_path": RAW_DIR / "onet_profiles.json",
        "importer": import_onet_profiles,
    },
    {
        "manifest_path": RAW_DIR / "roadmap_manifest.json",
        "raw_output_path": RAW_DIR / "roadmap_profiles.json",
        "importer": import_roadmap_profiles,
    },
]


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def merge_imported_profiles(profile_groups: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for profiles in profile_groups:
        for profile in profiles:
            profile_id = str(profile["profile_id"])
            if profile_id in merged:
                raise ValueError(f"duplicate imported profile id detected: {profile_id}")
            merged[profile_id] = profile
    return sorted(
        merged.values(),
        key=lambda item: (str(item.get("source_type", "")), str(item.get("profile_id", ""))),
    )


def main() -> None:
    ensure_dir(RAW_DIR)
    snapshot_date = date.today().isoformat()
    imported_profile_groups: list[list[dict[str, Any]]] = []

    for source_config in SOURCE_CONFIGS:
        manifest = load_json(source_config["manifest_path"])
        raw_profiles, imported_profiles = source_config["importer"](manifest, snapshot_date)
        write_json(source_config["raw_output_path"], raw_profiles)
        imported_profile_groups.append(imported_profiles)

    merged_profiles = merge_imported_profiles(imported_profile_groups)
    write_json(IMPORTED_OUTPUT_PATH, merged_profiles)
    source_types = sorted({str(profile.get("source_type", "")) for profile in merged_profiles if profile.get("source_type")})
    print(
        f"imported {len(merged_profiles)} external profiles into {IMPORTED_OUTPUT_PATH.relative_to(ROOT)} "
        f"across {len(source_types)} source types"
    )


if __name__ == "__main__":
    main()
