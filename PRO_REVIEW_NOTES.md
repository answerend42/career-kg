# Pro Review Notes

This archive contains the current Career KG project code for deeper review.

## Primary Review Focus

1. Backend retrieval and matching quality
   - Many user inputs still fail to recall useful graph nodes.
   - Career recommendations and real external sources are not aligned well enough.
   - Please inspect natural-language parsing, alias coverage, scoring thresholds, fallback behavior, and external profile mapping.

2. Frontend quality
   - The current UI has been simplified into a page-by-page demo flow, but there is still room to improve clarity, visual hierarchy, interaction affordances, and graph readability.
   - Please review the React/Vite implementation under `frontend/src`.

3. Knowledge graph generation logic
   - The major open question is how the graph is generated from raw/source data into runtime graph nodes and edges.
   - Please clarify what raw data should be collected.
   - Please clarify what final graph schema and node/edge structure should be generated.
   - Please inspect whether `data/sources`, `scripts/build_graph.py`, validation scripts, and runtime `data/seeds` form a clear and defensible pipeline.

## Important Paths

- `backend/app`: backend API, parser, inference, explanation, role gap, and action planning logic.
- `frontend/src`: current frontend workbench implementation.
- `data/sources`: editable canonical source data.
- `data/sources/raw`: external source manifests and imported snapshots.
- `data/seeds`: generated runtime graph nodes and edges.
- `data/dictionaries`: generated parsing and alias dictionaries.
- `scripts`: graph build, import, validation, and benchmark scripts.
- `tests`: backend and graph behavior regression tests.
- `docs`: architecture, data pipeline, evaluation, frontend workflow, and planning notes.

## Suggested First Pass

1. Run the test and benchmark commands from `README.md` and `docs/baseline_status.md`.
2. Trace one failed natural-language input from frontend payload to parser output, normalized signals, inference scores, and final recommendations.
3. Trace one career node from external source manifest to imported profile, source metadata, seed node, inference output, and frontend display.
4. Decide whether the source schema should be formalized further before expanding the graph.
