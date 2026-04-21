# Provenance and Validation

Provenance and validation make the KG defensible. The goal is to answer three questions for every recommendation path:

| Question | Required data |
| --- | --- |
| Where did this fact come from? | Provenance record with source URL, snapshot time, evidence span, and retrieval method. |
| How reliable is it? | Confidence, extraction method, and review status. |
| Did it compile safely into runtime? | Canonical and serving validation reports. |

## Current Provenance Hooks

The repository already has partial provenance through imported profiles:

| Current file | Fields |
| --- | --- |
| `data/sources/imported_profiles.json` | `profile_id`, `source_type`, `source_id`, `source_url`, `source_title`, `snapshot_date`, `evidence_snippet`, `mapped_node_ids`, `profile_tags`. |
| `data/sources/raw/onet_profiles.json` | Raw-ish O*NET profile snapshots. |
| `data/sources/raw/roadmap_profiles.json` | Raw-ish roadmap profile snapshots. |
| `data/seeds/nodes.json` | Node metadata including `origin`, `source_file`, imported source refs when compiled. |
| `data/seeds/edges.json` | Edge metadata including `source_file`, relation group, and sometimes imported refs. |

`scripts/validate_graph.py` already checks imported profile shape, source diversity, graph size, valid relations, reachability, metadata coverage, and provenance-like source refs.

## Target Provenance Record

Recommended file:

```text
data/canonical/provenance.jsonl
```

Schema:

```json
{
  "provenance_id": "prov_onet_15_2051_00_summary_2026_04_21",
  "source_name": "onet",
  "source_type": "official_profile",
  "source_id": "15-2051.00",
  "source_title": "15-2051.00 - Data Scientists",
  "source_url": "https://www.onetonline.org/link/summary/15-2051.00",
  "snapshot_time": "2026-04-21T00:00:00Z",
  "retrieved_by": "scripts/import_external_profiles.py",
  "generated_by": "scripts/extract_relations.py",
  "attributed_to": "O*NET",
  "content_hash": "sha256:...",
  "raw_path": "data/raw/onet/html/15-2051.00.html",
  "staging_path": "data/staging/onet/15-2051.00.json",
  "evidence_span": [195, 222],
  "evidence_text": "natural language processing",
  "license_note": "record source license or access constraints"
}
```

This follows the spirit of PROV-O:

| PROV idea | Local field |
| --- | --- |
| `wasDerivedFrom` | `source_url`, `raw_path`, `source_id` |
| `wasGeneratedBy` | `generated_by`, extraction method on triples |
| `wasAttributedTo` | `attributed_to`, `source_name` |
| Time | `snapshot_time` |
| Evidence | `evidence_span`, `evidence_text` |

## Confidence Policy

Canonical triples and alignments should use confidence bands:

| Band | Meaning | Compile policy |
| --- | --- | --- |
| `0.95` to `1.00` | Structured O*NET / ESCO field or directly curated fact. | Can compile if schema-valid. |
| `0.80` to `0.94` | Official crosswalk or high-confidence schema mapping. | Can compile with provenance. |
| `0.60` to `0.79` | Rule-based extraction from semi-structured text. | Compile only if low-impact or reviewed. |
| `0.40` to `0.59` | Noisy candidate such as OpenIE or fuzzy relation. | Review queue only. |
| Below `0.40` | Too weak. | Do not add to graph. |

Every confidence score should be paired with an `extraction_method`, such as `structured_onet_field`, `structured_esco_relation`, `dependency_rule`, `hearst_pattern`, `openie_candidate`, or `manual_review`.

## Validation Layers

Validation should happen at each boundary:

```text
source validation
  -> raw/staging validation
  -> canonical validation
  -> alignment validation
  -> serving compile validation
  -> runtime behavior benchmarks
```

## Current Validation

Run:

```bash
python3 scripts/source_validation.py
python3 scripts/build_graph.py
python3 scripts/validate_graph.py
```

Current `scripts/validate_graph.py` validates:

| Check | Why it matters |
| --- | --- |
| Valid serving relations | Keeps `InferenceEngine` relation factors safe. |
| Reachable role nodes | Prevents dead role recommendations. |
| Minimum graph scale | Protects demo coverage expectations. |
| Node and edge source metadata | Preserves basic traceability. |
| Direction upstream and downstream coverage | Ensures direction nodes are connected. |
| Imported profile shape | Ensures external profile refs are usable. |
| Imported profile count and source diversity | Prevents external evidence collapse to one source. |
| Provenance node coverage | Ensures imported refs survive compile. |

Runtime regression commands:

```bash
python3 scripts/run_nl_benchmark.py
python3 scripts/run_recommendation_benchmark.py
python3 scripts/run_planning_benchmark.py
PYTHONPATH=. python -m unittest discover -s tests -v
```

## Future Canonical Validation

Future command:

```bash
python3 scripts/validate_canonical_kg.py
```

Required checks:

| Check | Rule |
| --- | --- |
| Concept schema | Required fields exist and values have correct types. |
| Concept uniqueness | No duplicate `concept_id`. |
| External ID uniqueness | No duplicate external IDs within the same scheme and type unless explicitly merged. |
| Term targets | Every `term.concept_id` exists. |
| Mention offsets | Mention spans fit within their staging document section text. |
| Triple endpoints | Every triple head and tail exists. |
| Relation domain/range | Relation is legal for the concept types. |
| Confidence bounds | Confidence values are in `[0.0, 1.0]`. |
| Provenance coverage | Every concept, triple, and alignment has provenance or a documented curated origin. |
| Review gates | Low-confidence facts cannot compile as accepted facts. |
| Hierarchy cycles | `broader_than` and `narrower_than` cannot create unexpected cycles. |
| Orphan concepts | Concepts without terms, triples, provenance, or alignment are reported. |

## Future Alignment Validation

Future command:

```bash
python3 scripts/benchmark_alignment.py
```

Required checks:

| Check | Rule |
| --- | --- |
| Internal role coverage | Important role families have reviewed or explicitly unmapped records. |
| Mapping type validity | Only accepted SKOS-style mapping types are used. |
| Candidate margin | Ambiguous top candidates enter review queue. |
| Crosswalk consistency | O*NET to ESCO / ISCO mappings do not contradict official crosswalk support without review. |
| Review completeness | `reviewed` records include reviewer and date. |
| Provenance coverage | Accepted mappings cite source profiles or canonical concepts. |

Suggested report fields:

```json
{
  "role_count": 50,
  "reviewed_alignment_count": 42,
  "unmapped_count": 3,
  "review_queue_count": 5,
  "average_confidence": 0.84,
  "coverage_by_family": {
    "backend": 1.0,
    "data": 0.92,
    "ml": 0.88
  }
}
```

## Future Serving Compile Validation

Future command:

```bash
python3 scripts/compile_serving_graph.py
python3 scripts/validate_graph.py
```

Compile validation should check:

| Check | Rule |
| --- | --- |
| Seed compatibility | Output still matches `GraphLoader` expectations. |
| Relation compatibility | Only `supports`, `requires`, `prefers`, `inhibits`, and `evidences` appear in runtime edges. |
| Metadata carryover | Canonical IDs, triple IDs, and provenance refs survive compile. |
| Weight bounds | Runtime edge weights stay in expected numeric range. |
| Topological safety | Serving graph remains acyclic for `InferenceEngine`. |
| Role reachability | Every role has upstream evidence paths. |
| Explanation availability | Recommended roles have path explanations. |

## Teacher-Facing Trace Example

Use this shape when explaining a recommendation path:

```text
User input: "I like Python and NLP"
  -> runtime evidence: skill_python, skill_nlp
  -> serving path: skill_nlp -> ability_nlp_foundations -> cap_ml_engineering -> role_nlp_engineer
  -> canonical backing: ext_onet_occ_15_2051_00 requires_skill ext_skill_natural_language_processing
  -> provenance: O*NET Data Scientists profile, snapshot 2026-04-21, evidence span "natural language processing"
  -> alignment: role_nlp_engineer closeMatch ext_onet_occ_15_2051_00, confidence 0.86, reviewed
```

This separates application scoring from knowledge engineering evidence while keeping the final result explainable.

