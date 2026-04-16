# 目标岗位差距分析

## 目标

`/api/role-gap` 让系统不只回答“推荐什么岗位”，还回答“如果我想冲某个岗位，还差什么、先补什么最值、顺序怎么排”。

## 输入

接口复用现有输入方式：

- `text`
- `signals`
- `target_role_id`
- `scenario_limit`

其中 `target_role_id` 必填，必须对应 role 节点。

## 分析流程

1. 先复用现有推荐链路，把输入归一化到标准节点。
2. 用同一套图推理得到全图 `states`。
3. 只针对目标岗位提取：
   - `paths`
   - `limitations`
   - `missing_requirements`
   - `parent_contributions`
4. 从目标岗位的 `requires` 和弱 `supports` 父节点里生成 `priority_suggestions`。
5. 用同一批建议节点做多步成长路径编排：
   - 优先硬前置
   - 再看单步增益
   - 避免重复复用同一批 boost 节点
6. 对建议节点向上游追溯叶子证据节点，构造 what-if 候选。
7. 对候选证据节点做轻量注入重算，得到 `what_if_scenarios`。

## 为什么模拟补“证据节点”

图里很多中间能力节点使用 `soft_and` 聚合器。  
如果直接给中间能力节点打分，可能不会真正抬升目标岗位分数。

因此 what-if 模拟采用：

- 先找到建议能力节点的上游叶子证据
- 再对这些证据节点做“补到中等偏上水平”的注入

这样更符合当前图结构，也更接近真实用户的成长动作，例如补项目、补工具、补基础知识。

## 关键返回字段

- `target_role.current_score`
- `target_role.gap_summary`
- `target_role.missing_requirements`
- `target_role.priority_suggestions`
- `target_role.learning_path`
- `target_role.what_if_scenarios`

## 前端使用方式

前端工作台在“目标岗位分析”面板中：

1. 从 `catalog.role_nodes` 里选择目标岗位
2. 调用 `/api/role-gap`
3. 展示：
   - 当前分数
   - 关键缺口
   - 优先补齐建议
   - 成长路径时间线
   - what-if 模拟卡片

## 当前边界

- 成长路径和 what-if 都是启发式规则，不是全局最优解搜索器。
- 当前更适合作为课程展示和成长规划辅助，而不是严格的学习路径优化器。
- 如果后续需要更强的规划能力，可以继续接：
  - case benchmark
  - 多轮动作组合搜索
  - 与课程/项目模板库的映射
