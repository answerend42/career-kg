#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path
from statistics import mean
from typing import Any

from normalize_raw_documents import ROOT, PIPELINE_DATE, PIPELINE_VERSION, read_json, write_json


ALIGNMENT_PATH = ROOT / "data" / "alignment" / "occupation_alignment.json"
DEFAULT_OUTPUT = ROOT / "data" / "runtime" / "alignment_benchmark.json"


def benchmark_alignment(alignment_path: Path = ALIGNMENT_PATH) -> dict[str, Any]:
    payload = read_json(alignment_path, default={"mappings": [], "role_count": 0})
    mappings = [item for item in payload.get("mappings", []) if isinstance(item, dict)]
    top1 = [item for item in mappings if int(item.get("candidate_rank", 0)) == 1]
    accepted = [item for item in top1 if str(item.get("mapping_type")) != "unmapped"]
    reviewed = [item for item in accepted if str(item.get("review_status")) == "reviewed"]
    high_conf = [item for item in accepted if float(item.get("confidence", 0)) >= 0.76]
    needs_review = [item for item in mappings if str(item.get("review_status")) == "needs_review"]

    type_counts: dict[str, int] = {}
    for item in accepted:
        key = str(item.get("mapping_type", "unknown"))
        type_counts[key] = type_counts.get(key, 0) + 1

    confidences = [float(item.get("confidence", 0)) for item in accepted]
    role_count = int(payload.get("role_count") or len(top1))
    coverage = len(accepted) / role_count if role_count else 0.0
    reviewed_coverage = len(reviewed) / role_count if role_count else 0.0
    high_confidence_rate = len(high_conf) / role_count if role_count else 0.0

    return {
        "accepted_top1_count": len(accepted),
        "average_accepted_confidence": round(mean(confidences), 4) if confidences else 0.0,
        "coverage": round(coverage, 4),
        "high_confidence_rate": round(high_confidence_rate, 4),
        "mapping_type_counts": dict(sorted(type_counts.items())),
        "needs_review_count": len(needs_review),
        "pipeline_date": PIPELINE_DATE,
        "pipeline_version": PIPELINE_VERSION,
        "review_queue_sample": needs_review[:20],
        "reviewed_coverage": round(reviewed_coverage, 4),
        "risk_flags": [
            flag
            for flag, active in [
                ("coverage_below_80_percent", coverage < 0.8),
                ("reviewed_coverage_below_30_percent", reviewed_coverage < 0.3),
                ("needs_review_nonempty", bool(needs_review)),
            ]
            if active
        ],
        "role_count": role_count,
        "top1_count": len(top1),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Benchmark occupation alignment coverage and review risk.")
    parser.add_argument("--alignment", type=Path, default=ALIGNMENT_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    result = benchmark_alignment(args.alignment)
    write_json(args.output, result)
    print(
        "alignment coverage "
        f"{result['coverage']:.2%}, reviewed {result['reviewed_coverage']:.2%}, "
        f"needs_review={result['needs_review_count']} -> {args.output.relative_to(ROOT)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
