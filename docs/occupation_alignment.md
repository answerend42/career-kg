# Occupation Alignment

Occupation alignment explains how internal CareerKG roles map to external occupation knowledge. It replaces the current "manual source attached to node" pattern with explicit mappings, confidence, evidence, and review status.

## Current Repository State

Internal roles live in:

```text
data/sources/roles.json
```

External profile anchors currently live in:

```text
data/sources/raw/onet_manifest.json
data/sources/raw/roadmap_manifest.json
data/sources/imported_profiles.json
```

Those files already connect O*NET or roadmap pages to graph nodes through `mapped_node_ids`. That is useful for a demo and for seeding provenance, but it does not answer:

| Question | Why current `mapped_node_ids` is not enough |
| --- | --- |
| Is the mapping exact or approximate? | A list of node IDs has no `mapping_type`. |
| Why does the mapping exist? | The title, skill, task, and family evidence is not scored separately. |
| Can one internal role map to multiple external occupations? | The current field is a source attachment, not an alignment model. |
| Was it reviewed? | There is no review status or reviewer. |
| Does an official crosswalk support it? | Crosswalk support is not represented. |

## Alignment Goal

The target data product is:

```text
data/alignment/occupation_alignment.json
```

It should map internal role concepts such as `role_backend_engineer` or `role_data_engineer` to external occupation concepts such as O*NET `15-1252.00` or ESCO occupation URIs.

The preferred process is:

```text
internal role
  -> O*NET candidate occupations
  -> ESCO / ISCO via official crosswalk when available
  -> reviewed alignment record
  -> serving graph derivation metadata
```

O*NET is the first alignment target because its occupation granularity fits the current role graph and the repository already imports O*NET profile snippets.

## Mapping Semantics

Use SKOS-style mapping types:

| Mapping type | Use when |
| --- | --- |
| `exactMatch` | The internal role and external occupation are effectively the same scope. |
| `closeMatch` | They are close enough for recommendation and explanation, but differ in scope or naming. |
| `broadMatch` | The internal role is broader than the external occupation. |
| `narrowMatch` | The internal role is narrower than the external occupation. |
| `relatedMatch` | The external occupation is related but should not directly define the role. |
| `unmapped` | No candidate clears the threshold. |

Do not use a boolean `mapped: true`. The distinction matters when compiling serving graph edges and teacher-facing explanations.

## Alignment Record

Example:

```json
{
  "alignment_id": "align_role_data_engineer_onet_15_1243_00",
  "internal_concept_id": "role_data_engineer",
  "internal_label": "Data Engineer",
  "external_scheme": "onet",
  "external_concept_id": "ext_onet_occ_15_1243_00",
  "external_id": "15-1243.00",
  "external_label": "Database Architects",
  "mapping_type": "closeMatch",
  "confidence": 0.84,
  "evidence": {
    "title_similarity": 0.62,
    "alt_label_hit": false,
    "skill_overlap": 0.82,
    "task_overlap": 0.76,
    "family_prior": 0.9,
    "crosswalk_support": false,
    "source_profile_ids": ["onet_database_architects"]
  },
  "candidate_rank": 1,
  "review_status": "reviewed",
  "reviewer": "team",
  "reviewed_at": "2026-04-21",
  "provenance_ref_ids": ["prov_onet_database_architects"]
}
```

Required fields:

| Field | Purpose |
| --- | --- |
| `alignment_id` | Stable record ID. |
| `internal_concept_id` | Existing internal role ID from `data/sources/roles.json`. |
| `external_scheme` | `onet`, `esco`, or `isco`. |
| `external_concept_id` | Canonical external concept ID. |
| `external_id` | Native external identifier such as an O*NET code. |
| `mapping_type` | SKOS-style match type. |
| `confidence` | Numeric score from `0.0` to `1.0`. |
| `evidence` | Decomposed features used to justify the mapping. |
| `review_status` | Whether the mapping is automatic, queued, reviewed, or rejected. |
| `provenance_ref_ids` | Source records used by the mapping. |

## Candidate Generation

Candidate generation should combine lexical and graph evidence. A practical first version can use:

```text
alignment_score =
  0.25 * title_similarity
  + 0.25 * skill_overlap
  + 0.20 * task_overlap
  + 0.15 * family_prior
  + 0.10 * alt_label_hit
  + 0.05 * crosswalk_bonus
```

Feature definitions:

| Feature | Source |
| --- | --- |
| `title_similarity` | Internal role name and aliases from `data/sources/roles.json` compared with O*NET title and sample job titles. |
| `skill_overlap` | Serving evidence and capability requirements compared with external skill concepts. |
| `task_overlap` | External task text compared with role description, capability descriptions, and imported snippets. |
| `family_prior` | Internal role family such as `backend`, `data`, `ml`, `security`, or `frontend`. |
| `alt_label_hit` | Exact or normalized alias match from canonical terms. |
| `crosswalk_bonus` | Official O*NET to ESCO / ISCO support when available. |

Current data that can seed features:

| File | Useful fields |
| --- | --- |
| `data/sources/roles.json` | `id`, `name`, `aliases`, `family`, `description`, `direction_id`, `capability_id`. |
| `data/sources/capability_templates.json` | Ability, composite, and direction membership. |
| `data/sources/imported_profiles.json` | `source_id`, `source_title`, `sample_job_titles`, `evidence_snippet`, `profile_tags`, `mapped_node_ids`. |
| `data/seeds/nodes.json` | Runtime node metadata after compile. |
| `data/seeds/edges.json` | Current support and requirement paths into roles. |

## Decision Policy

| Condition | Result |
| --- | --- |
| Top candidate score >= `0.88` and margin >= `0.08` | Auto candidate for `exactMatch` or high-confidence `closeMatch`. |
| Top candidate score >= `0.72` | Candidate enters review queue. |
| Top two candidates differ by < `0.05` | Candidate enters review queue even if score is high. |
| Score < `0.72` | Mark as `unmapped` or `relatedMatch` only. |
| Official crosswalk exists but title or skill overlap is weak | Do not auto-accept; queue for review. |

Review statuses:

| Status | Meaning |
| --- | --- |
| `auto_candidate` | Candidate generated but not reviewed. |
| `review_needed` | Requires human decision before compile. |
| `reviewed` | Approved by the team. |
| `rejected` | Should not influence serving graph. |
| `unmapped` | No acceptable external match. |

## Output Files

Recommended structure:

```text
data/alignment/
  occupation_alignment.json
  occupation_alignment_candidates.jsonl
  occupation_alignment_review_queue.jsonl
  occupation_alignment_report.json
```

`occupation_alignment.json` should contain only accepted or intentionally unresolved final records. Candidate and review queue files may be regenerated.

## Serving Compile Impact

Alignment should not replace the current five-layer serving graph. It should enrich it.

When compiling a role node such as `role_backend_engineer`, add metadata:

```json
{
  "derived_from_canonical_ids": ["ext_onet_occ_15_1252_00"],
  "derived_from_external_schemes": ["onet"],
  "alignment_type": "closeMatch",
  "alignment_confidence": 0.87,
  "alignment_status": "reviewed",
  "provenance_refs": ["prov_onet_15_1252_00_snapshot"]
}
```

When compiling edges, canonical external skill requirements can support existing internal evidence and ability paths:

```text
ext_onet_occ_15_1252_00 requires_skill ext_skill_api_design
  -> role_backend_engineer closeMatch ext_onet_occ_15_1252_00
  -> skill_api_design supports ability_api_design
  -> ability_api_design supports cap_backend_engineering
  -> cap_backend_engineering supports role_backend_engineer
```

## Validation

Alignment validation should check:

| Check | Failure example |
| --- | --- |
| Internal role exists | `internal_concept_id` not found in `data/sources/roles.json` or canonical concepts. |
| External concept exists | O*NET code has no canonical concept. |
| Mapping type is valid | `mapping_type: "match"` instead of SKOS-style type. |
| Confidence is bounded | Confidence below `0.0` or above `1.0`. |
| Review policy is enforced | Low-confidence mapping compiled as reviewed. |
| Coverage is adequate | Important role families have no accepted mappings. |
| Provenance is present | Alignment has no source profile or canonical provenance record. |

Current commands that still matter:

```bash
python3 scripts/source_validation.py
python3 scripts/build_graph.py
python3 scripts/validate_graph.py
```

Future commands:

```bash
python3 scripts/align_internal_roles.py
python3 scripts/benchmark_alignment.py
python3 scripts/compile_serving_graph.py
```

