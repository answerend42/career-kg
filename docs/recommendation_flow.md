# 推荐流程

## 输入阶段

系统支持两种入口：

- 自然语言输入
  - 通过 `backend/app/services/nl_parser.py` 进行多阶段解析：
    - 句段切分
    - 短语规则命中
    - alias/实体匹配
    - 强度、偏好、否定范围判定
- 结构化输入
  - 通过 `backend/app/services/input_normalizer.py` 直接映射到标准节点

两个入口最后都会归一到 `node_id -> score` 的内部表达。

## 推理阶段

1. 图谱加载器读取节点和边数据。
2. 按拓扑序遍历节点。
3. 对每个节点聚合入边贡献：
   - 正向支持
   - 项目证据
   - 偏好加成
   - 抑制项
   - 前置条件
4. 对不同层使用不同聚合器。
5. 只对职业节点做排序输出。

## 解释阶段

1. 从职业节点向前回溯高贡献父边。
2. 递归展开到证据层。
3. 输出 2-3 条最具代表性的路径。
4. 同时返回门槛、短板和抑制因素。

## 目标岗位分析

`POST /role-gap` 会在同样的输入归一化与图推理结果上，额外执行一层目标导向分析：

1. 用户指定 `target_role_id`
2. 基于该岗位当前 `paths / limitations / missing_requirements` 做定向诊断
3. 从 `requires` 和弱 `supports` 父节点里提炼优先补齐建议
4. 用建议节点和图上的前置关系编排 2-4 步成长路径
5. 对建议节点做轻量注入重算，生成 1-3 个 what-if 模拟场景

## 响应结构

`POST /recommend` 返回以下关键字段：

- `normalized_inputs`
- `recommendations`
- `near_miss_roles`
- `propagation_snapshot`
- `parsing_notes`
- `parsing_debug`
- `unresolved_entities`
- `graph_stats`

其中：

- `parsing_debug` 会返回规则命中、alias 命中、未充分解析的句段和候选信号，方便前端提示与回归调试。
- `near_miss_roles` 会返回“差一点匹配”的岗位、关键缺口和补齐建议，用于 why-not 展示。

`POST /role-gap` 返回以下关键字段：

- `target_role`
- `normalized_inputs`
- `parsing_notes`
- `parsing_debug`
- `unresolved_entities`

其中 `target_role` 里会包含：

- `current_score`
- `gap_summary`
- `missing_requirements`
- `priority_suggestions`
- `learning_path`
- `what_if_scenarios`
