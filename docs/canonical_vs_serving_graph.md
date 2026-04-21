# Canonical vs Serving Graph

CareerKG should use two graph layers:

```text
canonical reference KG -> serving recommendation KG
```

The canonical graph preserves source fidelity. The serving graph optimizes deterministic recommendation, explanation, gap analysis, and front-end visualization.

## Why Two Graphs

| Need | Canonical KG | Serving KG |
| --- | --- | --- |
| Explain where facts came from | Primary responsibility | Carries compact provenance refs |
| Preserve O*NET / ESCO / ISCO IDs | Primary responsibility | References derived IDs in metadata |
| Store term and alias semantics | Primary responsibility | Uses compiled dictionaries |
| Run recommendation scoring | Not primary | Primary responsibility |
| Support front-end animation | Not primary | Primary responsibility |
| Keep backend stable | Indirect | Directly loaded by backend |

The current repository already has the serving graph. `backend/app/services/graph_loader.py` loads:

```text
data/seeds/nodes.json
data/seeds/edges.json
data/dictionaries/skill_aliases.json
data/dictionaries/preference_patterns.json
data/dictionaries/parsing_patterns.json
```

`scripts/build_graph.py` currently generates those files from `data/sources/*`. The target architecture inserts canonical construction and alignment before serving compile.

## Canonical KG

Canonical KG stores stable career knowledge:

| Record | Example |
| --- | --- |
| Concept | `ext_onet_occ_15_2051_00`, `ext_skill_data_visualization`, `role_data_engineer` |
| Term | `Node.js`, `nodejs`, `后端`, `backend engineer` |
| Triple | `ext_onet_occ_15_2051_00 requires_skill ext_skill_nlp` |
| Provenance | O*NET profile snapshot, ESCO dump row, roadmap page section |
| Alignment | `role_nlp_engineer closeMatch ext_onet_occ_15_2051_00` |

Canonical data should live under:

```text
data/raw/
data/staging/
data/canonical/
data/alignment/
```

It can be JSONL, JSON, CSV, Parquet, RDF, or Turtle, but the semantics must remain explicit: concept identity, term labels, relation type, provenance, confidence, and alignment type.

## Serving KG

Serving KG keeps the application graph shape:

```text
evidence -> ability -> composite -> direction -> role
```

Current runtime nodes look like:

```json
{
  "id": "skill_python",
  "name": "Python",
  "layer": "evidence",
  "node_type": "skill",
  "aggregator": "source",
  "description": "Python programming skill.",
  "params": {},
  "metadata": {
    "origin": "curated",
    "source_file": "skills.json",
    "category": "skill"
  }
}
```

Current runtime edges look like:

```json
{
  "source": "skill_python",
  "target": "ability_programming_fundamentals",
  "relation": "supports",
  "weight": 0.17,
  "note": "This node positively supports programming fundamentals.",
  "metadata": {
    "source_file": "capability_templates.json",
    "relation_group": "supports"
  }
}
```

Serving graph relations are intentionally small:

| Relation | Meaning |
| --- | --- |
| `supports` | Positive contribution. |
| `requires` | Gate or prerequisite contribution. |
| `prefers` | Preference contribution. |
| `inhibits` | Negative or penalty contribution. |
| `evidences` | Direct evidence relation. |

This small relation set keeps `backend/app/services/inference_engine.py` deterministic and explainable.

## Compile Boundary

Canonical facts should compile into serving graph facts through explicit rules.

| Canonical input | Compile output |
| --- | --- |
| `skill_external` or `tool_external` concept | Evidence node or alias for an existing evidence node. |
| `occupation_external requires_skill skill_external` | Serving support path into ability, composite, direction, or role. |
| `occupation_external has_task task_external` | Ability or composite evidence if task maps to local capability. |
| `term alt_label concept` | Dictionary alias in `data/dictionaries/skill_aliases.json`. |
| `internal_role closeMatch occupation_external` | Role metadata and role-specific support facts. |
| `provenance` | Compact `provenance_refs` on serving nodes and edges. |

Compile should be deterministic:

```text
data/canonical/concepts.jsonl
data/canonical/terms.jsonl
data/canonical/triples.jsonl
data/canonical/provenance.jsonl
data/alignment/occupation_alignment.json
  -> scripts/compile_serving_graph.py
  -> data/seeds/nodes.json
  -> data/seeds/edges.json
  -> data/dictionaries/*.json
```

Until `scripts/compile_serving_graph.py` exists, `scripts/build_graph.py` remains the runtime compiler.

## Serving Metadata Contract

Serving nodes and edges should carry derivation metadata without forcing the backend to understand the full canonical schema.

Recommended node metadata:

```json
{
  "origin": "canonical+curated",
  "source_file": "compile_serving_graph.py",
  "derived_from_canonical_ids": ["ext_onet_occ_15_1252_00"],
  "derived_from_external_schemes": ["onet"],
  "derivation_method": "occupation_alignment_compile",
  "support_count": 12,
  "provenance_refs": ["prov_onet_15_1252_00_snapshot"],
  "alignment_status": "reviewed"
}
```

Recommended edge metadata:

```json
{
  "source_file": "compile_serving_graph.py",
  "relation_group": "supports",
  "derived_from_triple_ids": ["triple_onet_15_2051_requires_nlp"],
  "canonical_relation": "requires_skill",
  "compile_rule": "requires_skill_to_supports",
  "confidence": 0.96,
  "provenance_refs": ["prov_onet_15_2051_00_snapshot"]
}
```

This is compatible with the current loader because node and edge metadata are already dictionaries.

## Runtime Use

The serving graph powers four runtime behaviors.

| Behavior | Current service | Serving graph role |
| --- | --- | --- |
| Recommendation | `backend/app/services/inference_engine.py` | Propagates user evidence through topological order and ranks role nodes. |
| Explanation | `backend/app/services/explainer.py` | Finds high-contribution paths into recommended roles. |
| Gap analysis | `backend/app/services/role_gap_analyzer.py` | Compares active evidence with requirements and missing nodes. |
| Simulation | `backend/app/services/action_simulator.py` | Adds or boosts evidence and reruns propagation. |

The canonical graph is not queried directly during normal recommendation. It explains how the serving graph was built and provides provenance for teacher-facing and debugging views.

## Dynamic Use of a Static KG

The base serving graph is static after compile, but each user request creates a dynamic activation subgraph:

```text
user text
  -> normalized input evidence
  -> activated ability / composite / direction nodes
  -> scored role nodes
  -> explanation paths and propagation snapshot
```

This is how the system uses a KG dynamically without making the final recommendation an LLM output.

## Migration Path

| Step | Keep stable | Add |
| --- | --- | --- |
| 1 | Current `scripts/build_graph.py` and `data/seeds/*` | New docs and layer directories. |
| 2 | Current external profile import | Raw snapshots under `data/raw/` and staging records under `data/staging/`. |
| 3 | Current source schema | Canonical concepts, terms, triples, and provenance. |
| 4 | Current `mapped_node_ids` as hints | Explicit `data/alignment/occupation_alignment.json`. |
| 5 | Current backend loader | Compile canonical KG into existing seed format. |
| 6 | Current API response shape | Add compact provenance and derivation metadata where useful. |

## Validation Split

| Layer | Validation |
| --- | --- |
| Source | `python3 scripts/source_validation.py` |
| Current serving graph | `python3 scripts/build_graph.py` and `python3 scripts/validate_graph.py` |
| Runtime behavior | `python3 scripts/run_nl_benchmark.py`, `python3 scripts/run_recommendation_benchmark.py`, `python3 scripts/run_planning_benchmark.py` |
| Future canonical KG | `python3 scripts/validate_canonical_kg.py` |
| Future alignment | `python3 scripts/benchmark_alignment.py` |
| Future compile | `python3 scripts/compile_serving_graph.py` |

