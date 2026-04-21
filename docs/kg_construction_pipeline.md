# KG Construction Pipeline

This document explains how CareerKG should move from raw career knowledge to the runtime graph used by the application. It is intentionally tied to the current repository, where `scripts/build_graph.py` already compiles `data/sources/*` into `data/seeds/nodes.json` and `data/seeds/edges.json`.

## Current State

The repository already has a working serving graph:

| Layer | Current files | Purpose |
| --- | --- | --- |
| Source authoring | `data/sources/skills.json`, `data/sources/capability_templates.json`, `data/sources/roles.json`, `data/sources/relations.json` | Curated source schema for evidence, abilities, composites, directions, and roles. |
| External source anchors | `data/sources/raw/onet_manifest.json`, `data/sources/raw/roadmap_manifest.json` | Declares O*NET and roadmap pages plus current `mapped_node_ids`. |
| Imported evidence | `data/sources/imported_profiles.json`, `data/sources/raw/onet_profiles.json`, `data/sources/raw/roadmap_profiles.json` | Stores imported profile snippets and provenance-like source refs. |
| Build | `scripts/source_validation.py`, `scripts/build_graph.py` | Validates source data and compiles runtime seeds and dictionaries. |
| Runtime graph | `data/seeds/nodes.json`, `data/seeds/edges.json`, `data/dictionaries/*.json` | Loaded by `backend/app/services/graph_loader.py`. |
| Runtime validation | `scripts/validate_graph.py` | Checks scale, reachability, relation validity, metadata, and imported profile coverage. |

This is enough for a deterministic recommendation demo, but the external sources are still mostly source anchors. The target pipeline adds a canonical reference KG between raw data and the serving graph.

## Target Pipeline

The target chain is:

```text
raw documents
  -> staging documents and mentions
  -> canonical concepts, terms, triples, and provenance
  -> occupation alignment
  -> runtime / serving graph
  -> recommendation, explanation, gap analysis, and simulation
```

The layer directories are:

| Directory | Role |
| --- | --- |
| `data/raw/` | Immutable snapshots of external data, downloads, HTML, CSV, JSON, and API responses. |
| `data/staging/` | Cleaned documents, sections, sentence spans, mention candidates, and extraction candidates. |
| `data/canonical/` | Canonical concepts, term lexicons, triples, provenance records, and validation reports. |
| `data/alignment/` | Internal role to external occupation mappings, review queues, and benchmark reports. |
| `data/runtime/` | Optional compiled serving artifacts before or alongside the existing `data/seeds/*` files. |

`data/seeds/*` remains the application-facing runtime graph until the backend is changed. The canonical layer should compile into the same runtime seed shape so `backend/app/services/graph_loader.py` and downstream services can remain stable.

## Stage A: Raw Zone

Raw files are snapshots, not cleaned data. They should be append-only and include enough metadata to reproduce extraction:

```json
{
  "doc_id": "onet_15_2051_00_2026_04_21",
  "source_name": "onet",
  "source_url": "https://www.onetonline.org/link/summary/15-2051.00",
  "snapshot_time": "2026-04-21T00:00:00Z",
  "content_type": "html",
  "license_note": "source license or access note",
  "sha256": "content hash",
  "language": "en",
  "raw_path": "data/raw/onet/html/15-2051.00.html"
}
```

Current bridge: `data/sources/raw/onet_profiles.json` and `data/sources/raw/roadmap_profiles.json` already act as raw-ish profile snapshots. Future import scripts should write raw snapshots under `data/raw/` first, then produce staging and canonical records.

## Stage B: Staging Normalization

Staging normalizes documents without deciding final graph facts. It should preserve document structure and offsets:

```json
{
  "doc_id": "roadmap_backend_2026_04_21",
  "source_name": "roadmap_sh",
  "title": "Backend Developer Roadmap",
  "sections": [
    {
      "section_id": "summary_01",
      "section_type": "summary",
      "text": "A backend developer designs APIs and services.",
      "char_start": 0,
      "char_end": 48
    }
  ]
}
```

Expected staging outputs:

| Output | Purpose |
| --- | --- |
| Clean documents | Boilerplate removed, sections retained. |
| Sentence spans | Stable offsets for evidence spans. |
| Mention candidates | Text spans that may link to canonical concepts. |
| Relation candidates | Candidate subject-relation-object facts before validation. |

## Stage C: Term Lexicon

The term lexicon connects real text to canonical concepts. It should be built from:

| Source | Current repository hook |
| --- | --- |
| O*NET titles, skills, knowledge, abilities | Future structured imports under `data/raw/onet/` and `data/canonical/`. |
| ESCO preferred and alternative labels | Future structured imports under `data/raw/esco/` and `data/canonical/`. |
| Curated local aliases | `data/sources/skills.json`, `data/sources/roles.json`, `data/sources/aliases.json`. |
| Runtime parser patterns | `data/sources/parsing_patterns.json` and generated `data/dictionaries/parsing_patterns.json`. |

Example term record:

```json
{
  "term_id": "term_nodejs",
  "surface": "Node.js",
  "normalized": "nodejs",
  "language": "en",
  "term_type": "alt_label",
  "concept_id": "tool_nodejs",
  "concept_type": "tool",
  "source_ref_ids": ["prov_esco_nodejs_alt_label"]
}
```

## Stage D: Entity Candidate Extraction

Entity extraction should be recall-oriented. A mention may have multiple candidates:

```json
{
  "mention_id": "mention_roadmap_backend_001",
  "doc_id": "roadmap_backend_2026_04_21",
  "surface": "API design",
  "normalized": "api design",
  "span": [29, 39],
  "candidate_concepts": [
    {
      "concept_id": "ability_api_design",
      "match_method": "alias_exact",
      "score": 0.92
    }
  ]
}
```

The current user-input parser in `backend/app/services/nl_parser.py` is runtime parsing. Canonical extraction is different: it parses external source documents to build the graph, not user requests.

## Stage E: Entity Linking

Entity linking chooses a canonical concept or marks the mention for review:

```json
{
  "mention_id": "mention_roadmap_backend_001",
  "chosen_concept_id": "ability_api_design",
  "link_score": 0.92,
  "link_status": "auto_high_confidence",
  "review_reason": null,
  "evidence": {
    "section_type": "summary",
    "matched_by": "alias_exact"
  }
}
```

Recommended statuses:

| Status | Meaning |
| --- | --- |
| `auto_high_confidence` | Can be used directly in canonical triples. |
| `auto_low_confidence` | Candidate is stored but should not become a high-confidence fact. |
| `needs_review` | Human review required before compiling. |
| `rejected` | Candidate should not affect canonical or runtime graph. |

## Stage F: Relation Extraction

Structured data should be mapped directly before applying NLP. For example, O*NET skills or ESCO essential skills should become canonical triples with high confidence. NLP should primarily enrich roadmap pages, job descriptions, and free text.

Example triple:

```json
{
  "triple_id": "triple_onet_15_2051_requires_data_visualization",
  "head_id": "ext_onet_occ_15_2051_00",
  "relation": "requires_skill",
  "tail_id": "ext_skill_data_visualization",
  "confidence": 0.96,
  "extraction_method": "structured_onet_field",
  "provenance_ref_ids": ["prov_onet_15_2051_00_skills"]
}
```

Extraction methods should be explicit:

| Method | Intended confidence band |
| --- | --- |
| `structured_onet_field` or `structured_esco_relation` | `0.95` to `1.00` |
| `official_crosswalk` | `0.80` to `0.94` |
| `dependency_rule` or `section_rule` | `0.60` to `0.79` |
| `openie_candidate` or `fuzzy_candidate` | Review queue only unless confirmed. |

## Stage G: Canonical KG

Canonical KG stores durable facts:

| Record type | Documented in |
| --- | --- |
| Concept | `docs/canonical_schema.md` |
| Term | `docs/canonical_schema.md` |
| Triple | `docs/canonical_schema.md` |
| Provenance | `docs/provenance_and_validation.md` |
| Alignment | `docs/occupation_alignment.md` |

Canonical IDs should be stable and scheme-aware. External IDs such as O*NET codes, ESCO URIs, and ISCO codes must not be discarded. Local serving IDs such as `role_backend_engineer` may align to one or more external occupation concepts.

## Stage H: Occupation Alignment

Alignment connects internal pedagogical roles from `data/sources/roles.json` to canonical external occupations. The current `mapped_node_ids` in imported manifests are useful seed hints, but the target alignment layer should record:

| Field | Reason |
| --- | --- |
| `mapping_type` | Distinguishes exact, close, broad, narrow, and related mappings. |
| `confidence` | Prevents weak mappings from silently shaping recommendations. |
| `evidence` | Makes title, skill, task, family, and crosswalk support inspectable. |
| `review_status` | Separates automatic candidates from reviewed alignments. |

See `docs/occupation_alignment.md`.

## Stage I: Runtime / Serving Compile

The serving graph keeps the existing five-layer shape:

```text
evidence -> ability -> composite -> direction -> role
```

Compile rules should map canonical facts into this shape:

| Serving layer | Canonical source |
| --- | --- |
| Evidence | Skills, knowledge, tools, languages, projects, interests, constraints, terms. |
| Ability | Clusters of canonical concepts with teachable names. |
| Composite | Groups of abilities that represent larger capabilities. |
| Direction | Career areas such as backend, data, ML, security, frontend, and product. |
| Role | Internal roles aligned to external occupations. |

The compile target should remain compatible with `data/seeds/nodes.json` and `data/seeds/edges.json`:

```json
{
  "id": "role_backend_engineer",
  "layer": "role",
  "node_type": "role",
  "metadata": {
    "derived_from_canonical_ids": ["ext_onet_occ_15_1252_00"],
    "derived_from_external_schemes": ["onet"],
    "derivation_method": "occupation_alignment_compile",
    "support_count": 12,
    "provenance_refs": ["prov_onet_15_1252_00"],
    "alignment_status": "reviewed"
  }
}
```

## End-to-End Example

One demonstrable chain should look like this:

```text
raw O*NET profile
  -> staging sentence: "Apply data mining, data modeling, natural language processing..."
  -> mention: "natural language processing"
  -> canonical concept: ext_skill_natural_language_processing
  -> canonical triple: ext_onet_occ_15_2051_00 requires_skill ext_skill_natural_language_processing
  -> alignment: role_nlp_engineer closeMatch ext_onet_occ_15_2051_00
  -> serving edge: skill_nlp supports ability_nlp_foundations or cap_ml_engineering
  -> recommendation path shown by GraphExplainer
```

Runtime services that consume the compiled graph:

| Service | Use |
| --- | --- |
| `backend/app/services/graph_loader.py` | Loads `data/seeds/nodes.json`, `data/seeds/edges.json`, and dictionaries. |
| `backend/app/services/inference_engine.py` | Propagates evidence scores through the serving graph. |
| `backend/app/services/explainer.py` | Builds top contribution paths for recommendations. |
| `backend/app/services/role_gap_analyzer.py` | Compares current activation to target role requirements. |
| `backend/app/services/action_simulator.py` | Simulates added evidence from learning actions. |

## Validation Commands

Current validation remains:

```bash
python3 scripts/source_validation.py
python3 scripts/build_graph.py
python3 scripts/validate_graph.py
python3 scripts/run_nl_benchmark.py
python3 scripts/run_recommendation_benchmark.py
python3 scripts/run_planning_benchmark.py
PYTHONPATH=. python -m unittest discover -s tests -v
```

Future canonical validation should add:

```bash
python3 scripts/validate_canonical_kg.py
python3 scripts/benchmark_alignment.py
python3 scripts/compile_serving_graph.py
```

