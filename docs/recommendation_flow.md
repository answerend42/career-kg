# 推荐流程

## 输入阶段

系统支持两种入口：

- 自然语言输入
  - 通过 `backend/app/services/nl_parser.py` 使用别名词典与上下文模式抽取节点
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

## 响应结构

`POST /recommend` 返回以下关键字段：

- `normalized_inputs`
- `recommendations`
- `propagation_snapshot`
- `parsing_notes`
- `unresolved_entities`
- `graph_stats`

这使得后续前端既能展示结果列表，也能展示传播路径和节点热度。
