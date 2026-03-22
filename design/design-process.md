# 设计步骤

## 适合这个 repo 的设计顺序

对 Momo TMS 这类“领域模型明确、workflow 较多、前后端都在同一 repo”的项目，推荐按下面的顺序设计：

1. 先定义问题和边界。
2. 再定义领域对象和 invariants。
3. 再设计 workflow 与状态转换。
4. 再设计 contract 与页面数据依赖。
5. 再设计模块职责和依赖边界。
6. 再设计数据、查询和持久化细节。
7. 再设计验证、观测和交付方式。

这个顺序的核心原则是：先确定“什么必须成立”，再讨论“怎么实现”。

## 步骤矩阵

| 步骤 | 目标 | 必须设计的内容 | 推荐产出 |
| --- | --- | --- | --- |
| 1. 问题定义 | 先把变化说清楚 | 用户/操作者是谁；要解决什么痛点；受影响的是 `/app`、API、workflow 还是数据层；成功标准是什么；明确 non-goals | 一页 design brief |
| 2. 边界与约束 | 确认不能破坏什么 | `AGENTS.md` guardrails；owner doc；是否仍然 project-scoped；是否触碰 schema immutability；是否涉及 compatibility/migration | 约束清单 |
| 3. 领域模型 | 设计概念和身份 | 涉及哪些对象；对象身份是什么；`business_key`、`source`、`variant`、`binding` 的关系是否变化；允许状态和禁止状态是什么 | 领域对象表 + invariants 列表 |
| 4. Workflow 设计 | 设计行为路径 | happy path；异常路径；branch authority；transaction 边界；job/report 行为；是否影响 import、mutation、replace、trash、restore、fill、QA | sequence 或步骤说明 |
| 5. Contract 设计 | 明确输入输出 | 页面路由是否变；API route、request、response、error semantics 是否变；frontend bootstrap/data dependency 是否变 | contract 草案 |
| 6. 模块设计 | 决定代码该放哪 | router/service/repository/page/component 的职责；依赖方向；哪些模块可以知道 DB 细节；哪些模块只能消费 contract 或 assembled view | 模块职责图 |
| 7. 数据与查询设计 | 保证实现可落地 | 表结构、字段、索引、read model、write model、hydration 策略、分页策略、幂等性、reset/migration 策略 | schema/query note |
| 8. 验证与交付 | 保证变更可上线 | 该跑哪些 tests；该更新哪个 owner doc；是否需要 docs validator；手动验证场景；风险和 deferred items | validation plan + rollout note |

## 每一步要回答什么

### 1. 问题定义

至少回答下面这些问题：

- 这次设计解决的是“产品问题”“工程问题”还是“两者都有”？
- 影响的是哪个运行时表面：`/app`、project-scoped API、workflow、DB、jobs，还是文档与验证流程？
- 这次明确不做什么？

如果这一步不清楚，后面的实现很容易变成“顺手多改一点”。

### 2. 边界与约束

这个 repo 里要优先检查：

- 是否仍然保持 `/app` 为唯一 operator-facing surface
- 是否仍然保持 project-scoped API
- 是否会误把 `GET /workbench` 或 `GET /variant-workbench` 拉回来
- 是否会引入 schema-edit 行为
- 是否会为了旧数据库或旧语义增加长期兼容层

这一步的产出不是代码，而是“哪些东西绝不能被设计突破”。

### 3. 领域模型

这一步建议画出最少四类内容：

- 对象：`Project`、`Schema`、`Entry`、`Variant`、`Scope Binding`、`Job`
- 身份：每个对象靠什么字段识别
- 生命周期：active、orphan、trashed 等状态怎样转换
- 不变量：例如“同一 entry 下同 source 只能有一个 non-trashed canonical variant”

如果这里没有写清楚，后面的 API 和事务设计会不断反复。

### 4. Workflow 设计

这一步要把“用户动作”变成“系统步骤”：

- 谁发起动作
- 输入从哪里来
- 中间要不要开 job
- 哪一步写库
- 哪一步只做 projection
- 哪些错误是业务结果，哪些错误应该整体 rollback

对 Momo TMS 来说，workflow 设计比页面设计更关键，因为 branch mutation、replace、trash、restore 都会跨对象更新。

### 5. Contract 设计

这一步关注的是“边界协作”而不是“内部实现”：

- 页面 route 是否变化
- bootstrap 是否变化
- request/response 字段是否变化
- error semantics 是否变化
- 前端页面依赖哪些数据，哪些数据可以延迟加载

如果 contract 设计不先做，前端和后端很容易各自补字段，最后再靠临时修补对齐。

### 6. 模块设计

这一步建议直接回答“代码应该放在哪里，为什么”：

- router 只做 contract 和参数解析，还是也做业务组合
- service 是 orchestration 还是 domain policy
- repository 只做 persistence，还是也做复杂 hydration
- frontend `App.tsx` 负责哪些共享状态，哪些状态应该下沉到 page 或 hook

一旦这些边界不清楚，文件会持续变大，但团队仍然说不清应该怎么拆。

### 7. 数据与查询设计

这一步要把“能跑”推进到“能长期维护”：

- 是否需要新字段或新表
- read model 和 write model 是否应该分开
- 哪些查询会随着数据规模增长而变慢
- 哪些地方需要分页、索引、缓存或惰性 hydration
- 当前 change 是 reset 即可，还是必须设计 migration

这一步对当前 repo 特别重要，因为 read model 和 repository 已经是明显的后续重点。

### 8. 验证与交付

最后一步不能只写“跑一下测试”：

- 应跑哪组 tests
- 该更新哪个 owner doc
- 是否需要 `.venv/bin/python scripts/validate_docs.py`
- 用户如何手动验证
- 哪些内容明确延期，不在本次范围

好的设计不是“想清楚了”，而是“能被验证、能被交付、能被继续维护”。

## 适用于本 repo 的设计清单

在开始写实现前，建议至少勾完下面这些项：

- [ ] 已选定 owner doc，并确认这次变化属于 system、contracts、workflows、runtime 还是 user-guide
- [ ] 已写明问题、目标、non-goals
- [ ] 已写明会受影响的 invariants
- [ ] 已写明 workflow happy path 和 failure path
- [ ] 已写明 API / bootstrap / page dependency 是否变化
- [ ] 已决定代码放置位置和模块职责
- [ ] 已决定验证命令、手动验证场景和 docs follow-through
- [ ] 已把 deferred items 和 open questions 单独列出
