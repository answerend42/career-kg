# Baseline Status

记录时间：`2026-04-21`

## 改造前基线（补录）

以下命令在开始按照 `careerkg_codex_package` 改造前已执行并通过，用于确认仓库最初可运行：

```bash
PYTHONPATH=. python -m unittest discover -s tests -v
PYTHONPATH=. python scripts/run_nl_benchmark.py
PYTHONPATH=. python scripts/run_recommendation_benchmark.py
PYTHONPATH=. python scripts/run_planning_benchmark.py
npm --prefix frontend install
npm --prefix frontend run build
```

补录结果：

- 单元测试通过：`46` 项
- 自然语言 benchmark 通过
- recommendation benchmark 通过
- planning benchmark 通过
- 前端依赖安装通过
- 前端构建通过

## 改造后回归

本轮改造完成后，按同一组命令重新验证：

```bash
PYTHONPATH=. python -m unittest discover -s tests -v
PYTHONPATH=. python scripts/run_nl_benchmark.py
PYTHONPATH=. python scripts/run_recommendation_benchmark.py
PYTHONPATH=. python scripts/run_planning_benchmark.py
npm --prefix frontend install
npm --prefix frontend run build
```

### 结果

| Command | Result | Notes |
| --- | --- | --- |
| `PYTHONPATH=. python -m unittest discover -s tests -v` | PASS | `51` tests passed |
| `PYTHONPATH=. python scripts/run_nl_benchmark.py` | PASS | `7/7` cases passed |
| `PYTHONPATH=. python scripts/run_recommendation_benchmark.py` | PASS | `13/13` cases passed, `fallback_coverage=1.00` |
| `PYTHONPATH=. python scripts/run_planning_benchmark.py` | PASS | `6/6` cases passed |
| `npm --prefix frontend install` | PASS | up to date, `0` vulnerabilities |
| `npm --prefix frontend run build` | PASS | generated `frontend/dist/index.html` and bundled assets |

### 额外验证

- `python scripts/source_validation.py`: PASS
- `python scripts/build_graph.py`: PASS
- 本地服务 smoke test：`GET /health -> 200`，`GET / -> 200`

### 当前图谱快照

- Nodes: `365`
- Edges: `1053`
- Role nodes: `50`
- Nodes with provenance: `102`

### 当前 benchmark 摘要

- Recommendation:
  - `hit_at_3=1.00`
  - `hit_at_5=1.00`
  - `explanation_coverage=1.00`
  - `provenance_coverage=1.00`
  - `fallback_coverage=1.00`
  - `pass_rate=1.00`
- Planning:
  - `gap_coverage=1.00`
  - `learning_path_coverage=1.00`
  - `action_template_coverage=1.00`
  - `simulation_positive_rate=1.00`
  - `adopt_non_regression_rate=1.00`
  - `focus_match_rate=1.00`
  - `pass_rate=1.00`
