# 当前设计评审

## 总结

- 当前 repo 最强的部分是 runtime model 清晰，最弱的部分不是“没有设计”，而是“设计资产缺层”。
- `docs/` 已经较完整地描述了产品边界、核心模型、契约和 workflow，但“怎么设计一个变化”“为什么这样取舍”“哪些横切设计还没补”还没有独立工作台。
- 建议先把设计过程和设计盘点固化，再继续推进前端状态架构、read model 边界、契约归属和 ADR 机制。

## 已经做得比较成熟的设计

### 1. 产品边界与兼容策略

证据：

- [../AGENTS.md](../AGENTS.md)
- [../docs/system.md](../docs/system.md)
- [../docs/contracts.md](../docs/contracts.md)
- [../app/routers/pages.py](../app/routers/pages.py)

评价：

- `/app` 是唯一操作界面，旧工作台路由保持 `410 Gone`，public API 一律 project-scoped。
- 这让产品边界、兼容边界、重构边界都比较清楚，不容易在演进中把旧设计偷偷带回来。

### 2. 领域模型与 invariants

证据：

- [../docs/system.md](../docs/system.md)
- [../docs/user-guide.md](../docs/user-guide.md)
- [../app/services/branch/models.py](../app/services/branch/models.py)
- [../app/services/variant/__init__.py](../app/services/variant/__init__.py)
- [../app/services/variant/lifecycle.py](../app/services/variant/lifecycle.py)

评价：

- `Project / Schema / Entry / Variant / Scope Binding` 的拆分是清楚的。
- `business_key`、`source`、canonical same-source variant、`orphan`/`trashed` 生命周期这些规则已经形成稳定心智模型。
- `BranchRef` 和 `BranchKind` 说明 branch 语义已经不再完全依赖裸字符串。

### 3. Workflow 设计

证据：

- [../docs/workflows.md](../docs/workflows.md)
- [../app/services/branch/mutations.py](../app/services/branch/mutations.py)
- [../app/services/branch/replace.py](../app/services/branch/replace.py)
- [../app/services/workflows/application.py](../app/services/workflows/application.py)

评价：

- import、mutation、replace、trash、restore、fill、QA 的语义已经足够清楚，能够直接落到服务和测试上。
- transaction 边界、job/report 形态、project-scoped 约束也比较一致。

### 4. 文档与验证闭环

证据：

- [../AGENTS.md](../AGENTS.md)
- [../docs/runtime.md](../docs/runtime.md)
- [../code_review.md](../code_review.md)
- [../tests/](../tests/)

评价：

- owner doc 路由、验证命令、docs validator、review checklist 都已经建立起来。
- 这对持续演进很重要，因为它让“改代码”不再脱离“改事实文档”和“跑对应验证”。

### 5. 历史问题已经有部分修复

证据：

- [../archive/reviews/design-pattern-and-abstraction-review.md](../archive/reviews/design-pattern-and-abstraction-review.md)
- [../archive/2026-03-maintainability-repair-plan.md](../archive/2026-03-maintainability-repair-plan.md)
- [../frontend/src/product-app/](../frontend/src/product-app/)

评价：

- 历史上提到的 branch value object、前端拆分等问题，已经有明显进展。
- 说明 repo 不是“设计完全失控”，而是处在“核心模型已经清晰，但细化设计资产还没跟上”的阶段。

## 当前主要设计风险

### 1. 设计过程没有显式化

现状：

- 运行时事实写在 `docs/`，历史思考散落在 `archive/`，剩下的设计理由大量隐含在代码里。

风险：

- 团队很容易从“有想法”直接跳到“写实现”，导致 tradeoff、non-goal、验证范围都不够显式。

### 2. 前端状态架构仍然过于集中

证据：

- [../frontend/src/App.tsx](../frontend/src/App.tsx) 当前约 1156 行
- 同文件有 24 个 `useState`
- 同文件有 11 个 `useEffect`

风险：

- `App.tsx` 同时承担 route shell、共享状态、数据加载、workflow action、错误提示和页面编排。
- 这会让前端设计讨论很难落到稳定边界上，也让测试和重构成本持续升高。

### 3. repository 和 read model 边界仍需继续沉淀

证据：

- [../app/services/variant/store.py](../app/services/variant/store.py)
- [../app/services/variant/bindings.py](../app/services/variant/bindings.py)
- [../app/services/read_models/_support.py](../app/services/read_models/_support.py)
- [../app/services/branch/mutations.py](../app/services/branch/mutations.py) 当前约 567 行

风险：

- monolith 已拆开，但 query ownership、hydration 策略和性能预算的长期设计仍分散在多个模块里。
- 当我们要继续优化性能、补索引或调整 read model 形态时，仍需要更明确的 strategy note 承接取舍。

### 4. 契约归属存在双份维护

证据：

- [../app/schemas.py](../app/schemas.py)
- [../frontend/src/product-app/types.ts](../frontend/src/product-app/types.ts)

风险：

- 后端 Pydantic 和前端 TypeScript 目前主要靠人工同步。
- 一旦 API 字段调整，容易出现“后端改了，前端类型没跟上”或“前端假设比后端更宽/更窄”的漂移。

### 5. 非功能设计和 decision log 仍然偏弱

证据：

- [../archive/2026-03-maintainability-repair-plan.md](../archive/2026-03-maintainability-repair-plan.md) 中的 phase 3 仍是 planned
- active `docs/` 里还没有面向长期决策的 ADR 工作流

风险：

- read model 的性能预算、数据规模、可观测性、并发假设、长期 tradeoff 还没有固定下来。
- 一些关键决定会继续依赖团队记忆，而不是依赖可追溯文档。

## 建议的设计优先级

1. 先固化设计工作台。
2. 再补前端状态架构设计。
3. 再补 read model 和 repository boundary 设计。
4. 再补 contract ownership 策略。
5. 最后重启 ADR 机制，承接跨切面决策。

## 建议坚持的设计原则

- 先写 invariants，再写 workflow，再写 API，再写代码放置位置。
- 明确区分 write model 和 read model，不要让同一个服务同时变更状态又承担页面拼装。
- 继续保持 `/app` 和 project-scoped API 的高约束，不为旧路由和旧数据引入长期兼容层。
- 任何跨切面设计取舍都要留下文档，不要只留在实现里。
