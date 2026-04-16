# 行动模板库

## 目标

行动模板层负责把成长路径中的抽象步骤，映射成可执行的项目、练习、课程或作品集动作。

它不替代知识图谱推理，而是承接 `learning_path[*]` 的结果：

- 图谱负责找出“先补什么”
- 模板库负责回答“具体去做什么”

## 数据文件

- Source：`data/sources/action_templates.json`
- Runtime：`data/demo/action_templates.json`

模板库通过 `scripts/build_graph.py` 从 source 同步到 demo，供运行时读取。

## 字段规范

每条模板至少包含：

- `template_id`
- `title`
- `action_type`
  - `project / practice / course / portfolio`
- `summary`
- `focus_node_ids`
  - 该模板优先服务哪些成长路径 focus 节点
- `evidence_node_ids`
  - 该模板能直接补哪些证据节点
- `target_role_ids`
  - 可选，用于提升岗位特异性
- `direction_ids`
  - 可选，用于方向层步骤
- `effort_level`
  - `low / medium / high`
- `deliverables`
  - 建议交付物，前端直接展示
- `tags`

## 匹配规则

`ActionTemplateMatcher` 当前采用启发式打分：

1. `focus_node_id` 命中权重最高
2. `boosts[*].node_id` 命中其次
3. `direction_ids` 和 `target_role_ids` 作为加成，而不是单独决定匹配
4. 单个通用知识点不会单独触发模板，避免“数据库原理一命中就给数据工程模板”这类误匹配
5. 每一步默认返回 1 到 2 个模板，并尽量避免跨步骤重复

## 当前模板设计取舍

- 项目型模板优先级高于课程型模板，因为更容易回到证据节点和作品集价值。
- 模板库规模当前故意控制在“小而精”，先保证解释性和稳定性。
- 后续如果要扩容，可以优先补：
  - 机器学习方向更多实验模板
  - 平台/云原生方向更多上线模板
  - 移动端/嵌入式方向的专项模板

## 输出字段

接口层会把模板匹配结果挂到：

- `target_role.learning_path[*].recommended_actions`

每个行动卡片包含：

- `action_key`
- `template_id`
- `title`
- `action_type`
- `summary`
- `effort_level`
- `deliverables`
- `tags`
- `matched_node_ids`
- `matched_node_names`
- `simulation_node_ids`
- `reason`

其中 `reason` 用于解释“为什么它适合当前这一步”。
`simulation_node_ids` 则用于 action simulation：当用户点击“模拟这个动作”时，后端会把这些证据节点作为轻量注入目标重新跑一遍图推理。
`action_key` 则用于在前端做“加入方案 / 单独模拟 / 组合模拟”时精确绑定具体行动卡，避免同一个模板在多步成长路径里重复出现时发生歧义。
如果同一个 `template_id` 在多步成长路径里重复出现，前端与 API 应优先使用 `action_key`，避免把后续步骤的上下文误用到当前点击的动作上。
