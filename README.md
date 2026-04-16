# Career KG

一个以知识图谱为核心的计算机职业推荐系统原型。当前版本已经完成首轮后端闭环：输入标准化、轻量自然语言解析、基于 DAG 图谱的前向传播、职业排序与路径解释。

## 当前能力

- 使用 `data/seeds/nodes.json` 和 `data/seeds/edges.json` 构建 128 个节点、275 条边的分层知识图谱。
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

## 目录

- `backend/app`: 推荐服务、推理引擎、解释器、输入解析
- `data/ontology`: 节点类型与边类型本体
- `data/seeds`: 生成后的图谱节点与边
- `data/dictionaries`: 别名词典和自然语言模式词典
- `scripts/bootstrap_demo_data.py`: 生成 demo 图谱和词典
- `scripts/validate_graph.py`: 校验 DAG 和图谱规模
- `tests`: 单元测试

## 快速开始

1. 生成种子数据

```bash
python3 scripts/bootstrap_demo_data.py
```

2. 运行图校验

```bash
python3 scripts/validate_graph.py
```

3. 运行示例推荐

```bash
python3 -m backend.app.main --input-file data/demo/sample_request.json
```

4. 启动本地 HTTP 服务

```bash
python3 -m backend.app.main --serve --host 127.0.0.1 --port 8080
```

请求示例：

```bash
curl -X POST http://127.0.0.1:8080/recommend \
  -H 'Content-Type: application/json' \
  -d @data/demo/sample_request.json
```

5. 运行测试

```bash
python3 -m unittest discover -s tests -v
```

## 请求格式

`POST /recommend` 需要一个 JSON 对象，请求体支持这些字段：

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

更详细设计见 [docs/architecture.md](/Users/ans42/Code/auto-evol-project/projects/career-kg/docs/architecture.md) 和 [docs/recommendation_flow.md](/Users/ans42/Code/auto-evol-project/projects/career-kg/docs/recommendation_flow.md)。
