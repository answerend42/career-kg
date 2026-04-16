# Career KG

一个以知识图谱为核心的计算机职业推荐系统原型。当前版本已经具备后端推理闭环、可编译的数据流水线和可演示前端工作台：输入解析、节点确认、职业排序、路径解释和传播可视化都可以直接运行。

## 当前能力

- 使用 `data/sources/* -> scripts/build_graph.py -> data/seeds/*` 的流水线，构建 `362` 个节点、`1044` 条边、`50` 个职业节点的分层知识图谱。
- 支持两类输入：
  - 自然语言描述
  - 结构化信号列表
- 推荐分数由图上传播、聚合、门槛与抑制规则得到，不依赖 LLM 直接给职业结论。
- 输出包含：
  - 标准化后的输入节点
  - Top-K 职业推荐
  - 每个职业的匹配分数
  - 关键贡献路径
  - 节点传播快照，便于前端做可视化
- 已提供前端工作台，支持输入确认、节点微调、二次重算与传播图查看。

## 目录

- `backend/app`: 推荐服务、推理引擎、解释器、输入解析
- `frontend`: 静态前端工作台与构建脚本
- `data/sources`: 可编辑的图谱源数据、模板和别名
- `data/ontology`: 节点类型与边类型本体
- `data/seeds`: 生成后的图谱节点与边
- `data/dictionaries`: 别名词典、自然语言模式词典和解析短语规则
- `scripts/bootstrap_demo_data.py`: 生成 demo source 数据并编译图谱
- `scripts/build_graph.py`: 从 source 数据编译图谱 seed 与词典
- `scripts/run_nl_benchmark.py`: 回归口语化自然语言 benchmark
- `scripts/validate_graph.py`: 校验 DAG 和图谱规模
- `docs/data_pipeline.md`: 图谱数据流水线说明
- `tests`: 单元测试

## 快速开始

1. 生成 demo 源数据并编译图谱

```bash
python3 scripts/bootstrap_demo_data.py
```

如果你已经修改了 `data/sources/*`，可以直接重新编译：

```bash
python3 scripts/build_graph.py
```

2. 运行图校验

```bash
python3 scripts/validate_graph.py
```

3. 构建前端静态资源

```bash
npm --prefix frontend run build
```

4. 启动本地 HTTP 服务

```bash
python3 -m backend.app.main --serve --host 127.0.0.1 --port 8080
```

打开 `http://127.0.0.1:8080/` 即可进入前端工作台。

5. 运行示例推荐

```bash
python3 -m backend.app.main --input-file data/demo/sample_request.json
```

6. 运行测试

```bash
python3 -m unittest discover -s tests -v
```

7. 运行自然语言 benchmark

```bash
python3 scripts/run_nl_benchmark.py
```

8. 运行 recommendation benchmark

```bash
python3 scripts/run_recommendation_benchmark.py
```

## 接口

`POST /api/recommend` 与 `POST /recommend` 都可用，请求体支持这些字段：

```json
{
  "text": "我熟悉 Python 和 MySQL，做过 Flask 项目，会一点 Linux，更喜欢后端。",
  "signals": [
    {"entity": "Python", "score": 0.9},
    {"entity": "SQL", "score": 0.7}
  ],
  "top_k": 5,
  "include_snapshot": true
}
```

- `text`: 自然语言描述，可为空。
- `signals`: 结构化信号列表，也支持 `{ "Python": 0.9, "SQL": 0.7 }` 这种对象写法。
- `top_k`: 返回的职业数量，范围会被裁剪到 `1-20`。
- `include_snapshot`: 是否返回传播快照，支持 JSON 布尔值。

`GET /api/catalog` 会返回：

- evidence 节点目录
- role 节点目录
- 图谱统计信息
- 示例请求

`POST /api/recommend` 还会返回可直接用于展示 provenance 的字段：

- `recommendations[*].source_refs`
  - 当前职业节点绑定的外部职业画像来源
- `recommendations[*].provenance_count`
  - 当前职业节点命中的来源条数
- `propagation_snapshot.nodes[*].metadata.source_refs`
  - 传播图节点详情中的来源锚点
- `graph_stats.source_profile_count`
  - 已接入的外部职业画像数量
- `graph_stats.source_type_count`
  - 当前接入的来源类型数量
- `graph_stats.source_profile_count_by_type`
  - 各来源类型对应的职业画像数量
- `graph_stats.nodes_with_provenance`
  - 编译后带来源锚点的节点数量

`POST /api/role-gap` 与 `POST /role-gap` 用于分析指定目标岗位的差距，请求体示例：

```json
{
  "text": "我熟悉 Python、SQL，会一点 Linux，想往机器学习方向转。",
  "signals": [
    {"entity": "不喜欢高数学理论", "score": 0.8}
  ],
  "target_role_id": "role_ml_engineer",
  "scenario_limit": 3
}
```

- `target_role_id`: 目标岗位节点 ID，必须是 role 节点。
- `scenario_limit`: what-if 模拟返回条数，范围会被裁剪到 `1-5`。

响应重点字段：

- `target_role.current_score`
- `target_role.missing_requirements`
- `target_role.priority_suggestions`
- `target_role.learning_path`
- `target_role.learning_path[*].recommended_actions`
- `target_role.what_if_scenarios`

`POST /api/action-simulate` 与 `POST /action-simulate` 用于模拟“执行某个成长路径行动后会怎样”，请求体示例：

```json
{
  "target_role_id": "role_backend_engineer",
  "action_key": "step-1:backend_rest_service_project",
  "template_id": "backend_rest_service_project",
  "signals": [
    {"entity": "Python", "score": 0.8},
    {"entity": "偏好后端", "score": 0.9}
  ]
}
```

- `action_key` 或 `action_keys`
  - 推荐从 `learning_path[*].recommended_actions[*].action_key` 直接传回，能精确定位用户点击的是哪一步里的哪张行动卡；当前最多支持 2 个 action 组成组合方案。
- `template_id` 或 `template_ids`
  - 兼容唯一模板场景；如果同一个模板在多步成长路径里重复出现，服务端会要求改用 `action_key` 以避免模拟到错误步骤。

响应重点字段：

- `simulation.current_score`
- `simulation.predicted_score`
- `simulation.delta_score`
- `simulation.bundle_size`
- `simulation.bundle_summary`
- `simulation.overlap_node_names`
- `simulation.injected_boosts`
- `simulation.activated_nodes`
- `simulation.before_top_roles`
- `simulation.after_top_roles`
- `simulation.target_role_rank_before`
- `simulation.target_role_rank_after`

## 工作台流程

1. 用户输入自然语言和结构化信号。
2. 前端调用 `/api/recommend` 获取 `normalized_inputs`。
3. 用户在“节点确认”面板里微调节点分值。
4. 用户可选择目标岗位，调用 `/api/role-gap` 查看差距、成长路径、推荐行动模板和 what-if 模拟。
5. 用户既可单独模拟某个行动，也可把最多 2 个行动加入方案篮子，再调用 `/api/action-simulate` 比较组合收益、重复覆盖和岗位排序变化。
6. 用户可采纳当前模拟方案，把 `simulation.injected_boosts` 写回确认节点层，再调用 `/api/recommend` 重算推荐。
7. 页面展示新的职业排序、关键路径、限制项和传播图。

## 真实来源数据

项目当前接入了多类公开职业知识来源，并把来源信息编译进知识图谱节点元数据：

- 原始快照：`data/sources/raw/onet_profiles.json`
- 原始快照：`data/sources/raw/roadmap_profiles.json`
- 来源清洗结果：`data/sources/imported_profiles.json`
- 导入脚本：`scripts/import_external_profiles.py`

刷新来源数据的推荐命令顺序：

```bash
python3 scripts/import_external_profiles.py
python3 scripts/build_graph.py
python3 scripts/validate_graph.py
```

前端工作台会在推荐卡片和传播图节点详情中展示这些来源锚点，便于课程演示时说明“为什么这些岗位和节点被建进图谱”。
当前推荐卡片还会展示来源类型 badge，例如 `O*NET` 和 `roadmap.sh`，让“多来源融合”在 UI 上可直接感知。

## 评测

当前仓库包含两套质量护栏：

- `python3 scripts/run_nl_benchmark.py`
  - 验证自然语言解析与候选岗位召回
- `python3 scripts/run_recommendation_benchmark.py`
  - 验证端到端推荐质量、解释覆盖和 provenance 覆盖

运行 recommendation benchmark 后会生成：

- `data/demo/recommendation_benchmark_report.json`
- `data/demo/recommendation_benchmark_report.md`

Markdown 报告会直接列出每条 case 的匹配岗位名、Top 推荐摘要和失败原因，便于课堂展示和回归排查。

更详细的指标说明见 [docs/evaluation.md](/Users/ans42/Code/auto-evol-project/projects/career-kg/docs/evaluation.md)。

## 推荐链路

1. 结构化输入和自然语言输入都先被映射到标准节点。
2. 图谱加载器读取 DAG 数据并构建入边/出边索引。
3. 推理引擎按拓扑序传播分数，处理：
   - `supports`
   - `requires`
   - `prefers`
   - `inhibits`
   - `evidences`
4. 职业节点输出匹配分数。
5. 解释器回溯高贡献路径，生成可解释理由。

更详细设计见 [docs/architecture.md](/Users/ans42/Code/auto-evol-project/projects/career-kg/docs/architecture.md)、[docs/data_pipeline.md](/Users/ans42/Code/auto-evol-project/projects/career-kg/docs/data_pipeline.md)、[docs/recommendation_flow.md](/Users/ans42/Code/auto-evol-project/projects/career-kg/docs/recommendation_flow.md)、[docs/frontend_workflow.md](/Users/ans42/Code/auto-evol-project/projects/career-kg/docs/frontend_workflow.md)、[docs/gap_analysis.md](/Users/ans42/Code/auto-evol-project/projects/career-kg/docs/gap_analysis.md)、[docs/learning_path.md](/Users/ans42/Code/auto-evol-project/projects/career-kg/docs/learning_path.md) 和 [docs/action_templates.md](/Users/ans42/Code/auto-evol-project/projects/career-kg/docs/action_templates.md)。
