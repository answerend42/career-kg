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
- 图谱统计信息
- 示例请求

## 工作台流程

1. 用户输入自然语言和结构化信号。
2. 前端调用 `/api/recommend` 获取 `normalized_inputs`。
3. 用户在“节点确认”面板里微调节点分值。
4. 前端使用确认后的节点再次调用 `/api/recommend`。
5. 页面展示职业排序、关键路径、限制项和传播图。

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

更详细设计见 [docs/architecture.md](/Users/ans42/Code/auto-evol-project/projects/career-kg/docs/architecture.md)、[docs/data_pipeline.md](/Users/ans42/Code/auto-evol-project/projects/career-kg/docs/data_pipeline.md)、[docs/recommendation_flow.md](/Users/ans42/Code/auto-evol-project/projects/career-kg/docs/recommendation_flow.md) 和 [docs/frontend_workflow.md](/Users/ans42/Code/auto-evol-project/projects/career-kg/docs/frontend_workflow.md)。
