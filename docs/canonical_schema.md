# Canonical Schema

The canonical schema describes the durable reference KG that sits above the current serving graph. The backend still consumes `data/seeds/nodes.json` and `data/seeds/edges.json`; canonical records are the traceable source of truth that future compile scripts should use to generate those runtime seeds.

## Design Rules

| Rule | Reason |
| --- | --- |
| Keep external IDs | O*NET codes, ESCO URIs, and ISCO codes are evidence, not display labels. |
| Separate concepts from terms | A concept is a thing in the graph; a term is a surface form used to mention it. |
| Make triples evidence-bearing | Every canonical edge must have confidence and provenance. |
| Treat alignment as data | Internal roles and external occupations may be exact, close, broad, narrow, or related matches. |
| Compile serving graph separately | Runtime nodes optimize recommendation and explanation, not source fidelity. |

## Concept

Concepts are canonical nodes. They can represent external occupations, skills, knowledge, abilities, tools, tasks, source documents, or local pedagogical concepts.

Recommended file:

```text
data/canonical/concepts.jsonl
```

Schema:

```json
{
  "concept_id": "ext_onet_occ_15_2051_00",
  "concept_type": "occupation_external",
  "scheme": "onet",
  "external_id": "15-2051.00",
  "uri": "https://www.onetonline.org/link/summary/15-2051.00",
  "preferred_label": "Data Scientists",
  "alt_labels": ["Data Scientist", "Data Science Specialist"],
  "language": "en",
  "description": "Develop and implement analytics applications...",
  "status": "active",
  "source_ref_ids": ["prov_onet_15_2051_00_snapshot"],
  "metadata": {
    "family": "data",
    "version": "2026-04-21"
  }
}
```

Allowed `concept_type` values:

| Type | Description |
| --- | --- |
| `occupation_external` | O*NET, ESCO, or ISCO occupation. |
| `skill_external` | External skill concept. |
| `knowledge_external` | External knowledge concept. |
| `ability_external` | External ability concept. |
| `tool_external` | External tool or technology concept. |
| `task_external` | External task or work activity concept. |
| `source_document` | Raw or normalized document used as evidence. |
| `internal_evidence` | Local evidence node compatible with `data/sources/skills.json`. |
| `internal_ability` | Local ability compatible with `data/sources/capability_templates.json`. |
| `internal_composite` | Local composite capability. |
| `internal_direction` | Local direction. |
| `internal_role` | Local role compatible with `data/sources/roles.json`. |

ID conventions:

| Prefix | Example |
| --- | --- |
| `ext_onet_occ_` | `ext_onet_occ_15_2051_00` |
| `ext_esco_occ_` | `ext_esco_occ_2511` |
| `ext_skill_` | `ext_skill_data_visualization` |
| `doc_` | `doc_roadmap_backend_2026_04_21` |
| Existing internal IDs | `role_backend_engineer`, `ability_api_design`, `skill_python` |

## Term

Terms map text surfaces to concepts. They are used by staging extraction and by future runtime dictionary generation.

Recommended file:

```text
data/canonical/terms.jsonl
```

Schema:

```json
{
  "term_id": "term_nodejs_alt_001",
  "concept_id": "tool_nodejs",
  "surface": "node.js",
  "normalized": "nodejs",
  "language": "en",
  "term_type": "alt_label",
  "source": "local_alias",
  "source_ref_ids": ["prov_data_sources_skills"],
  "metadata": {
    "case_sensitive": false,
    "token_pattern": null
  }
}
```

Allowed `term_type` values:

| Type | Meaning |
| --- | --- |
| `preferred_label` | Main display label for a concept. |
| `alt_label` | Valid synonym or alias. |
| `hidden_label` | Match-only label, usually noisy or deprecated. |
| `acronym` | Abbreviation such as `nlp`, `db`, or `qa`. |
| `code_token` | Language or tool token such as `c++`, `.net`, or `node`. |

Current repository inputs:

| File | Term source |
| --- | --- |
| `data/sources/skills.json` | Evidence labels and aliases. |
| `data/sources/roles.json` | Role labels and aliases. |
| `data/sources/aliases.json` | Local alias overrides. |
| `data/sources/parsing_patterns.json` | Runtime phrase patterns. |

## Mention

Mentions are staging records, not canonical graph facts. They preserve where a term or candidate concept appeared.

Recommended file:

```text
data/staging/mentions.jsonl
```

Schema:

```json
{
  "mention_id": "mention_onet_15_2051_0001",
  "doc_id": "doc_onet_15_2051_00",
  "section_id": "summary",
  "surface": "data modeling",
  "normalized": "data modeling",
  "span": [181, 194],
  "candidate_concepts": [
    {
      "concept_id": "ext_skill_data_modeling",
      "score": 0.88,
      "match_method": "term_exact"
    }
  ],
  "chosen_concept_id": "ext_skill_data_modeling",
  "link_status": "auto_high_confidence"
}
```

## Triple

Triples are canonical graph edges. A triple is not valid unless it has confidence and provenance.

Recommended file:

```text
data/canonical/triples.jsonl
```

Schema:

```json
{
  "triple_id": "triple_onet_15_2051_requires_nlp",
  "head_id": "ext_onet_occ_15_2051_00",
  "relation": "requires_skill",
  "tail_id": "ext_skill_natural_language_processing",
  "confidence": 0.96,
  "extraction_method": "structured_onet_field",
  "source_doc_id": "doc_onet_15_2051_00",
  "evidence_span": [195, 222],
  "evidence_text": "natural language processing",
  "provenance_ref_ids": ["prov_onet_15_2051_00_snapshot"],
  "review_status": "auto_accepted",
  "metadata": {
    "source_section": "summary"
  }
}
```

Relation vocabulary:

| Relation | Domain | Range |
| --- | --- | --- |
| `broader_than` | Any concept | Any concept in same taxonomy family |
| `narrower_than` | Any concept | Any concept in same taxonomy family |
| `same_as` | Any concept | Equivalent concept |
| `close_match` | Any concept | Similar concept |
| `related_match` | Any concept | Related concept |
| `requires_skill` | Occupation or role | Skill |
| `requires_knowledge` | Occupation or role | Knowledge |
| `requires_ability` | Occupation or role | Ability |
| `uses_tool` | Occupation, role, task, or skill | Tool |
| `has_task` | Occupation or role | Task |
| `mentioned_in` | Concept | Source document |
| `derived_from` | Concept or triple | Source document or concept |
| `supported_by` | Concept or triple | Provenance or document |
| `essential_for` | Skill, knowledge, ability, or task | Occupation or role |
| `optional_for` | Skill, knowledge, ability, or task | Occupation or role |

Serving relations are narrower:

| Serving relation | Current file |
| --- | --- |
| `supports` | `data/ontology/edge_types.json` |
| `requires` | `data/ontology/edge_types.json` |
| `prefers` | `data/ontology/edge_types.json` |
| `inhibits` | `data/ontology/edge_types.json` |
| `evidences` | `data/ontology/edge_types.json` |

Canonical relations should compile into serving relations when building `data/seeds/edges.json`.

## Provenance

Provenance records explain where a concept, term, triple, or alignment came from.

Recommended file:

```text
data/canonical/provenance.jsonl
```

Schema:

```json
{
  "provenance_id": "prov_onet_15_2051_00_snapshot",
  "source_name": "onet",
  "source_type": "official_profile",
  "source_url": "https://www.onetonline.org/link/summary/15-2051.00",
  "source_title": "15-2051.00 - Data Scientists",
  "external_id": "15-2051.00",
  "snapshot_time": "2026-04-21T00:00:00Z",
  "retrieved_by": "scripts/import_external_profiles.py",
  "content_hash": "sha256:...",
  "license_note": "record source license or access constraints",
  "evidence_text": "Develop and implement a set of techniques...",
  "raw_path": "data/raw/onet/html/15-2051.00.html",
  "staging_path": "data/staging/onet/15-2051.00.json"
}
```

Current bridge:

| Current field | Future provenance field |
| --- | --- |
| `profile_id` in `data/sources/imported_profiles.json` | `provenance_id` or source grouping key |
| `source_type` | `source_type` |
| `source_id` | `external_id` |
| `source_url` | `source_url` |
| `source_title` | `source_title` |
| `snapshot_date` | `snapshot_time` |
| `evidence_snippet` | `evidence_text` |

## Alignment

Alignment records map internal roles to external occupations. They should use SKOS-style mapping semantics.

Recommended file:

```text
data/alignment/occupation_alignment.json
```

Schema:

```json
{
  "alignment_id": "align_role_backend_engineer_onet_15_1252_00",
  "internal_concept_id": "role_backend_engineer",
  "internal_label": "Backend Engineer",
  "external_scheme": "onet",
  "external_concept_id": "ext_onet_occ_15_1252_00",
  "external_id": "15-1252.00",
  "external_label": "Software Developers",
  "mapping_type": "closeMatch",
  "confidence": 0.87,
  "evidence": {
    "title_similarity": 0.72,
    "skill_overlap": 0.81,
    "task_overlap": 0.66,
    "family_prior": 0.91,
    "crosswalk_support": false
  },
  "candidate_rank": 1,
  "review_status": "reviewed",
  "reviewer": "team",
  "reviewed_at": "2026-04-21",
  "provenance_ref_ids": ["prov_onet_15_1252_00_snapshot"]
}
```

Allowed `mapping_type` values:

| Type | Meaning |
| --- | --- |
| `exactMatch` | Internal role and external occupation are effectively equivalent. |
| `closeMatch` | Strong practical match, but not identical scope. |
| `broadMatch` | Internal role is broader than the external occupation. |
| `narrowMatch` | Internal role is narrower than the external occupation. |
| `relatedMatch` | Related enough for explanation or enrichment, not direct role identity. |
| `unmapped` | No acceptable candidate. |

## Serving Derivation Metadata

When canonical records are compiled into runtime seeds, each generated node and edge should include derivation metadata.

Node metadata:

```json
{
  "derived_from_canonical_ids": ["ext_onet_occ_15_1252_00"],
  "derived_from_external_schemes": ["onet"],
  "derivation_method": "occupation_alignment_compile",
  "support_count": 12,
  "provenance_refs": ["prov_onet_15_1252_00_snapshot"],
  "alignment_status": "reviewed"
}
```

Edge metadata:

```json
{
  "derived_from_triple_ids": ["triple_onet_15_2051_requires_nlp"],
  "canonical_relation": "requires_skill",
  "compile_rule": "requires_skill_to_supports",
  "confidence": 0.96,
  "provenance_refs": ["prov_onet_15_2051_00_snapshot"]
}
```

This extends the current metadata already present in `data/seeds/nodes.json` and `data/seeds/edges.json`, where `metadata.source_file`, `metadata.category`, and imported profile refs are used for traceability.

## Minimum Validation Rules

| Check | Required condition |
| --- | --- |
| Concept ID uniqueness | No duplicate `concept_id`. |
| External ID uniqueness | Unique within `scheme` and `concept_type`, unless explicitly merged. |
| Term target existence | Every `term.concept_id` exists. |
| Triple endpoints | Every `head_id` and `tail_id` exists. |
| Relation domain/range | Relation matches allowed domain and range. |
| Provenance coverage | Every triple has at least one `provenance_ref_id`. |
| Alignment target existence | Internal and external concepts exist or are explicitly marked unresolved. |
| Confidence bounds | All confidence values are between `0.0` and `1.0`. |
| Review policy | Low-confidence extraction cannot compile into high-impact serving edges without review. |

