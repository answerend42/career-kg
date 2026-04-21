# 评测与质量护栏

## Benchmark 列表

项目当前有三类 benchmark：

- `scripts/run_nl_benchmark.py`
  - 验证自然语言解析是否能稳定映射到关键节点
- `scripts/run_recommendation_benchmark.py`
  - 验证端到端推荐质量、解释覆盖和 provenance 覆盖
- `scripts/run_planning_benchmark.py`
  - 验证 `role-gap -> learning_path -> recommended_actions -> action_simulate -> adopt` 这条规划链路

## Recommendation Benchmark

### 数据文件

- `data/sources/recommendation_benchmark.json`
  - benchmark 原始定义
- `data/demo/recommendation_benchmark.json`
  - 编译后的演示副本

每条 case 支持以下字段：

- `id`
- `text`
- `signals`
- `top_k`
- `expected_roles_any`
- `expected_near_miss_roles_any`
- `expected_bridge_anchor_ids_any`
- `expected_bridge_roles_any`
- `forbidden_roles`
- `expected_explanation_nodes_any`
- `expected_source_types_any`
- `min_provenance_count`

### 当前指标

`scripts/run_recommendation_benchmark.py` 会输出并校验这些聚合指标：

- `hit_at_3`
- `hit_at_5`
- `fallback_coverage`
- `forbidden_role_violations`
- `explanation_coverage`
- `provenance_coverage`
- `pass_rate`

当前阈值：

- `hit_at_3 >= 0.75`
- `hit_at_5 >= 0.90`
- `fallback_coverage >= 1.00`
- `forbidden_role_violations = 0`
- `explanation_coverage >= 0.80`
- `provenance_coverage >= 0.80`

### 运行方式

```bash
python3 scripts/run_recommendation_benchmark.py
```

脚本会写出两份报告：

- `data/demo/recommendation_benchmark_report.json`
- `data/demo/recommendation_benchmark_report.md`

对于常规 case，脚本继续检查 top-k 命中、解释节点和 provenance 覆盖。

对于稀疏输入 / 兜底 case，脚本会重点检查：

- 是否命中了预期的 near miss 岗位
- 是否给出了预期的 bridge anchor
- bridge recommendation 是否把用户引导到了合理的相关岗位

## Planning Benchmark

### 数据文件

- `data/sources/planning_benchmark.json`
  - 规划链路 benchmark 原始定义
- `data/demo/planning_benchmark.json`
  - 编译后的演示副本

每条 case 支持以下字段：

- `id`
- `text`
- `signals`
- `target_role_id`
- `expected_missing_requirements_any`
- `expected_priority_nodes_any`
- `expected_focus_nodes_any`
- `expected_first_step_relation`
- `expected_action_template_ids_any`
- `expected_simulation_boost_nodes_any`
- `simulation.selectors[*].step`
- `simulation.selectors[*].action`
- `simulation.expected_bundle_size`
- `simulation.require_positive_delta`
- `require_non_worse_score_after_adopt`
- `require_non_worse_rank_after_adopt`

`adopt_non_regression` 采用 OR 语义：

- `score+rank`: 得分和推荐排名都不退化
- `score_only`: 得分不退化，但排名变差
- `rank_only`: 排名不退化，但得分下降
- `regressed`: 得分和排名都退化

### 当前指标

`scripts/run_planning_benchmark.py` 会输出并校验这些聚合指标：

- `gap_coverage`
- `learning_path_coverage`
- `action_template_coverage`
- `simulation_positive_rate`
- `adopt_non_regression_rate`
- `focus_match_rate`
- `pass_rate`

当前阈值：

- `gap_coverage >= 1.00`
- `learning_path_coverage >= 0.85`
- `action_template_coverage >= 1.00`
- `simulation_positive_rate >= 0.85`
- `adopt_non_regression_rate >= 1.00`
- `focus_match_rate >= 0.85`

### 运行方式

```bash
python3 scripts/run_planning_benchmark.py
```

脚本会写出两份报告：

- `data/demo/planning_benchmark_report.json`
- `data/demo/planning_benchmark_report.md`

Markdown 报告会附带每条 case 的目标岗位、关键 focus 节点、选中的行动模板、动作模拟增益、采纳后得分变化和失败原因。
其中 `Adopt Basis` 列会显式标注该 case 是靠 `score+rank`、`score_only`、`rank_only` 还是 `regressed` 通过/失败的。
这样既可以作为开发回归护栏，也可以直接作为课程展示材料。
