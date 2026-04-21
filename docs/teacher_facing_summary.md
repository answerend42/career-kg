# Teacher-Facing Summary

CareerKG is not only a recommendation demo. It is structured as a knowledge engineering pipeline that separates source knowledge, canonical graph construction, occupation alignment, and runtime recommendation.

## 30-Second Explanation

We build two graph layers. The first layer is a canonical reference KG built from structured sources such as O*NET and ESCO plus semi-structured sources such as roadmap pages. It stores concepts, terms, triples, provenance, confidence, and occupation alignment. The second layer is a serving recommendation KG compiled from that canonical layer into the existing five-layer graph: evidence -> ability -> composite -> direction -> role. The backend uses the serving graph for deterministic recommendation, explanation, gap analysis, and simulation, while each important path can trace back to canonical facts and source evidence.

## What Exists Now

The current system already has a working serving graph:

| Component | File |
| --- | --- |
| Curated evidence, abilities, directions, and roles | `data/sources/*.json` |
| External profile snippets | `data/sources/imported_profiles.json` |
| O*NET and roadmap raw-ish snapshots | `data/sources/raw/*.json` |
| Runtime seed graph | `data/seeds/nodes.json`, `data/seeds/edges.json` |
| Runtime dictionaries | `data/dictionaries/*.json` |
| Graph compiler | `scripts/build_graph.py` |
| Source and runtime validators | `scripts/source_validation.py`, `scripts/validate_graph.py` |
| Recommendation and explanation services | `backend/app/services/inference_engine.py`, `backend/app/services/explainer.py` |

The current graph is application-ready. The new canonical documentation explains how it should become more knowledge-engineering-complete.

## What The New KG Pipeline Adds

| Layer | Teacher-facing answer |
| --- | --- |
| Raw | We preserve source snapshots before extraction, including URL, snapshot time, content hash, and license notes. |
| Staging | We clean documents, split sections and sentences, and record mention candidates with offsets. |
| Canonical | We store concepts, terms, triples, confidence, and provenance separately from runtime scoring. |
| Alignment | We map internal roles to O*NET / ESCO / ISCO occupations with SKOS-style mapping types and review status. |
| Serving | We compile a lightweight graph that the backend can score deterministically and explain path-by-path. |

## Example Chain

```text
O*NET Data Scientists profile
  -> raw snapshot with source URL and snapshot time
  -> staging sentence containing "natural language processing"
  -> mention linked to canonical skill concept
  -> triple: Data Scientists requires_skill Natural Language Processing
  -> alignment: role_nlp_engineer closeMatch O*NET Data Scientists
  -> serving path: skill_nlp -> ability_nlp_foundations -> cap_ml_engineering -> role_nlp_engineer
  -> recommendation explanation shown to the user
```

This is the key defense: the recommendation path is not just a UI path. It is backed by canonical source facts and provenance.

## Why Structured Sources Come First

For O*NET and ESCO, many occupation-skill facts are already structured. The pipeline should map those fields directly instead of pretending everything is extracted by NLP. NLP is used where it adds value:

| Source type | Method |
| --- | --- |
| O*NET / ESCO structured fields | Direct schema mapping into canonical concepts and triples. |
| O*NET / ESCO labels and alternative labels | Term lexicon construction. |
| Roadmap pages and job descriptions | Document normalization, mention extraction, entity linking, and relation candidates. |
| Noisy extracted facts | Review queue before high-impact compile. |

The principle is: structured first, NLP second, human review last.

## How Occupation Alignment Works

Internal roles such as `role_backend_engineer` are pedagogical and product-facing. External occupations such as O*NET codes are standard career taxonomy concepts. Alignment connects them:

```text
role_backend_engineer closeMatch O*NET 15-1252.00 Software Developers
```

Each mapping should include:

| Field | Purpose |
| --- | --- |
| `mapping_type` | Exact, close, broad, narrow, related, or unmapped. |
| `confidence` | Numeric confidence score. |
| `evidence` | Title similarity, skill overlap, task overlap, family prior, and crosswalk support. |
| `review_status` | Whether the mapping was automatically generated, needs review, or was reviewed. |
| `provenance_ref_ids` | Source records behind the mapping. |

## How The Runtime Graph Is Used

The backend does not need to query the full canonical graph at request time. It uses the compiled serving graph:

| Runtime step | Existing implementation |
| --- | --- |
| Load graph | `backend/app/services/graph_loader.py` reads `data/seeds/*`. |
| Parse input | `backend/app/services/nl_parser.py` and dictionaries normalize user signals. |
| Propagate scores | `backend/app/services/inference_engine.py` computes node activations. |
| Explain results | `backend/app/services/explainer.py` returns contribution paths. |
| Analyze gaps | `backend/app/services/role_gap_analyzer.py` finds missing requirements. |
| Simulate actions | `backend/app/services/action_simulator.py` evaluates learning actions. |

The graph is static after compile, but each user request creates a dynamic activation subgraph. That activation subgraph is what drives recommendations and front-end graph animation.

## Validation Story

The validation story has three levels:

| Level | Validation |
| --- | --- |
| Current source and serving graph | `python3 scripts/source_validation.py`, `python3 scripts/build_graph.py`, `python3 scripts/validate_graph.py` |
| Current behavior | `python3 scripts/run_nl_benchmark.py`, `python3 scripts/run_recommendation_benchmark.py`, `python3 scripts/run_planning_benchmark.py`, `PYTHONPATH=. python -m unittest discover -s tests -v` |
| Future canonical layer | `validate_canonical_kg.py`, `benchmark_alignment.py`, and `compile_serving_graph.py` should check schemas, provenance, alignment coverage, and compile safety. |

The important point is that validation is not only "the script runs." It checks schema, reachability, relation legality, provenance coverage, confidence, review policy, and runtime recommendation behavior.

## What To Say If Asked About LLMs

CareerKG does not need an LLM in the final recommendation chain. The core recommendation is deterministic graph inference. If models are added later, they should be limited to candidate ranking, noisy relation reranking, reviewer assistance, or summarizing provenance cards. Final role scoring and gap analysis should remain graph-based so the system can be inspected and defended.

## Files Added By This Documentation Pass

| File | Purpose |
| --- | --- |
| `docs/kg_construction_pipeline.md` | End-to-end raw -> staging -> canonical -> alignment -> serving graph pipeline. |
| `docs/canonical_schema.md` | Concept, term, mention, triple, provenance, alignment, and serving metadata schemas. |
| `docs/occupation_alignment.md` | Internal role to external occupation alignment design. |
| `docs/canonical_vs_serving_graph.md` | Separation between source-of-truth KG and runtime recommendation graph. |
| `docs/provenance_and_validation.md` | Provenance model and validation checklist. |
| `docs/teacher_facing_summary.md` | Short explanation for course presentation or defense. |

