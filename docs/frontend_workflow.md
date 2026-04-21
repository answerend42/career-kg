# 前端工作台流程

## 目标

前端不是单纯展示 Top-K 列表，而是把知识图谱推荐过程拆成可观察、可微调、可回溯的工作台。当前实现基于 `Vite + React + TypeScript`，但仍保持原有 `/api/*` 后端契约不变。

## 页面结构

- 左栏：输入与节点确认
  - 案例画廊、自然语言输入、结构化信号、目标岗位选择
- 中栏：传播图与节点详情
  - 按 `evidence -> ability -> composite -> direction -> role` 分层布局
  - 支持回放激活路径和查看节点来源/聚合信息
- 右栏：结果与规划面板
  - `results` 标签展示 strong match、near miss、bridge recommendation
  - `target` 标签展示目标岗位差距、成长路径和推荐行动
  - `simulation` 标签展示单行动或双行动方案的收益对比

## 页面主流程

1. 案例载入 / 输入与解析
   - 用户可先从案例画廊一键载入 benchmark persona
   - 也可以直接输入自然语言描述
   - 还可补充结构化信号
2. 节点确认
   - 后端返回 `normalized_inputs`
   - 用户可调整分值、删除节点、补充节点
3. 目标岗位分析
   - 用户选择任意目标岗位
   - 前端调用 `/api/role-gap`
   - 展示当前差距、优先补齐建议、成长路径、推荐行动模板和 what-if 模拟
4. 行动模拟 / 方案对比
   - 用户可以单独模拟某个推荐行动
   - 也可以把最多 2 个动作加入方案篮子
   - 前端调用 `/api/action-simulate`
   - 展示目标岗位分数变化、注入证据节点、被带动节点、重复覆盖提示和模拟前后岗位排序
5. 方案采纳
   - 用户可采纳当前模拟方案
   - 前端把 `simulation.injected_boosts` 合并到 `confirmedSignals`
   - 再调用 `/api/recommend` 重算推荐，形成新的确认画像
6. 二次重算
   - 前端仍可继续手动微调确认节点并再次调用 `/api/recommend`
   - 避免用户每次微调都重新依赖自然语言解析
7. 推荐与解释
   - 展示职业排序、分数、限制项
   - 点击某个职业查看关键路径
8. 传播图查看
   - 按 `evidence -> ability -> composite -> direction -> role` 分层布局
   - 点击节点可查看聚合器和诊断信息

## 案例画廊

- `GET /api/catalog` 现在除 evidence/role 目录外，还会返回 `demo_cases`
- 每个案例包含：
  - `id`
  - `title`
  - `summary`
  - `preview`
  - `text`
  - `signals`
  - `target_role_id`
  - `target_role_name`
- 前端支持两种动作：
  - `载入案例`
    - 只填充输入区和目标岗位，并重置下游状态
  - `一键回放`
    - 填充输入后自动执行 `/api/recommend`
    - 再自动执行 `/api/role-gap`
    - 方便课程演示时快速切换 persona

## 使用的接口

- `GET /api/catalog`
  - 返回 evidence 节点目录、role 节点目录、示例请求和 demo cases
- `POST /api/recommend`
  - 返回标准化输入、推荐结果、bridge fallback 和传播快照
- `POST /api/role-gap`
  - 返回目标岗位分析、优先补齐建议、多步成长路径、行动模板和 what-if 模拟结果
- `POST /api/action-simulate`
  - 返回某个行动模板对应的图谱注入模拟结果

## 交互设计取舍

- 使用组件化的 `React + TypeScript`，把原来的前端巨石拆成输入、图谱、结果三个职责清晰的区域
- 保持单屏工作台，不回到纵向长页面；需要滚动时只在面板内部滚动
- 不展示全量边，而是只展示已激活节点和高贡献边，提高可读性
- 节点确认与推荐结果分开，强化“用户可控”而不是“一次性黑盒”
- 当输入稀疏时优先展示 bridge recommendation，而不是直接给空结果
