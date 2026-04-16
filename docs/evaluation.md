# 评测与质量护栏

## Recommendation Benchmark

项目当前有两类 benchmark：

- `scripts/run_nl_benchmark.py`
  - 主要验证自然语言输入映射是否稳定
- `scripts/run_recommendation_benchmark.py`
  - 主要验证端到端推荐质量是否稳定

## 数据文件

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
- `forbidden_roles`
- `expected_explanation_nodes_any`
- `expected_source_types_any`
- `min_provenance_count`

## 当前指标

`scripts/run_recommendation_benchmark.py` 会输出并校验这些聚合指标：

- `hit_at_3`
- `hit_at_5`
- `forbidden_role_violations`
- `explanation_coverage`
- `provenance_coverage`
- `pass_rate`

当前阈值：

- `hit_at_3 >= 0.75`
- `hit_at_5 >= 0.90`
- `forbidden_role_violations = 0`
- `explanation_coverage >= 0.80`
- `provenance_coverage >= 0.80`

## 运行方式

```bash
python3 scripts/run_recommendation_benchmark.py
```

脚本会写出两份报告：

- `data/demo/recommendation_benchmark_report.json`
- `data/demo/recommendation_benchmark_report.md`

Markdown 报告会附带每条 case 的匹配岗位名、Top 推荐摘要和失败原因。
这样既可以作为开发回归护栏，也可以直接作为课程展示材料。
