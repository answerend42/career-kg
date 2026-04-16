# 图谱数据流水线

## 目标

当前仓库把图谱定义拆成“可编辑 source 数据”和“运行时 seed 产物”两层，避免继续把所有节点和边硬编码在一个大脚本里。

## 目录结构

- `data/sources/skills.json`
  - 证据层节点，按 `skill/tool/knowledge/project/interest/soft_skill/constraint` 分类
- `data/sources/capability_templates.json`
  - `ability/composite/direction` 三层模板
- `data/sources/roles.json`
  - `standalone_roles` 与 `specializations`
- `data/sources/relations.json`
  - 默认边权、specialization 默认聚合器、自然语言偏好模式
- `data/sources/aliases.json`
  - 额外别名覆盖
- `data/sources/parsing_patterns.json`
  - 口语化短语规则、项目动作词和解析增强模式
- `data/sources/nl_benchmark.json`
  - parser/API 回归用的自然语言 benchmark
- `data/sources/recommendation_benchmark.json`
  - 端到端推荐质量 benchmark
- `data/sources/sample_request.json`
  - 示例输入

## 构建命令

初始化 demo 数据并编译：

```bash
python3 scripts/bootstrap_demo_data.py
```

仅重新编译 source 数据：

```bash
python3 scripts/build_graph.py
```

校验编译结果：

```bash
python3 scripts/validate_graph.py
```

## 编译结果

`scripts/build_graph.py` 会生成：

- `data/ontology/node_types.json`
- `data/ontology/edge_types.json`
- `data/seeds/nodes.json`
- `data/seeds/edges.json`
- `data/dictionaries/skill_aliases.json`
- `data/dictionaries/preference_patterns.json`
- `data/dictionaries/parsing_patterns.json`
- `data/demo/sample_request.json`
- `data/demo/nl_benchmark.json`
- `data/demo/recommendation_benchmark.json`

运行时只读取这些编译产物，`backend/app/services/graph_loader.py` 不直接消费 source 文件。

## specialization 机制

`roles.json` 中的 `specializations` 会自动展开为 3 个节点：

1. 技术栈能力节点 `ability_*_stack`
2. 专项复合能力节点 `cap_*`
3. 具体职业节点 `role_*`

这样可以用统一模板快速扩充职业族，同时保留：

- 技术栈证据
- 上游基础能力
- 岗位方向
- 偏好与抑制项

## 扩容建议

新增职业时，优先按下面顺序改：

1. 在 `skills.json` 补原子技能、工具、项目和别名
2. 在 `capability_templates.json` 补基础能力或方向
3. 在 `roles.json` 新增通用岗位或 specialization
4. 如涉及口语化输入，补 `parsing_patterns.json` 和 `nl_benchmark.json`
5. 运行 `python3 scripts/build_graph.py`
6. 运行 `python3 scripts/validate_graph.py`、测试、`python3 scripts/run_nl_benchmark.py` 和 `python3 scripts/run_recommendation_benchmark.py`

如果后续引入爬虫或外部职位数据，建议先落到 `data/sources/raw/` 或中间清洗脚本，再统一映射到当前 source schema。

## 外部职业画像接入

当前仓库已经接入一条可复用的数据流水线，用来把公开职业画像映射到图谱节点：

1. `data/sources/raw/onet_manifest.json`
   - 声明外部来源 URL、外部 occupation id、映射到哪些图节点
2. `data/sources/raw/roadmap_manifest.json`
   - 声明 roadmap.sh role roadmap 页面与图节点映射
3. `python3 scripts/import_external_profiles.py`
   - 抓取 O*NET 页面并生成：
   - `data/sources/raw/onet_profiles.json`
   - 抓取 roadmap.sh 页面并生成：
   - `data/sources/raw/roadmap_profiles.json`
   - `data/sources/imported_profiles.json`
4. `python3 scripts/build_graph.py`
   - 把 imported profiles 的 `source_refs` 合并进 capability / direction / role 节点的 metadata
5. `python3 scripts/validate_graph.py`
   - 校验 imported profiles、raw snapshot、来源多样性和编译后 provenance 覆盖率

### 当前 provenance 字段

编译后的节点 metadata 会保留以下字段，供 API 和前端工作台展示：

- `origin`
- `source_file`
- `provenance_count`
- `source_types`
- `source_type_count`
- `latest_snapshot_date`
- `source_refs[*].profile_id`
- `source_refs[*].source_type`
- `source_refs[*].source_id`
- `source_refs[*].source_title`
- `source_refs[*].source_url`
- `source_refs[*].snapshot_date`
- `source_refs[*].evidence_snippet`
- `source_refs[*].sample_job_titles`

这样前端既能展示“图谱规模”，也能展示“这些岗位/方向节点实际锚定了哪些公开职业资料”。
在当前实现里，同一个节点可以同时被 `onet_online` 和 `roadmap_sh` 两类来源共同支撑，前端会按来源类型分组展示。
