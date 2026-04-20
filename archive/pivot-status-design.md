# Pivot Status Design

## Summary

- `pivot` 保持为 `variant` 级概念，不做 branch-scoped state。
- project schema 只定义单一 `pivot_language`；`branch` 只是筛选视角和 review 操作的 actor，不拥有独立 pivot 状态。
- 不再使用 fingerprint、`pivot_revision`、或 child 自动 in-sync 机制。
- pivot runtime state 只保留三态：
  - `init`
  - `changed`
  - `reviewed`
- 状态机固定为：
  - `init -> changed <-> reviewed`
- 只要某次有效 variant 修改真正改到了 `pivot_language`，variant 就进入 `changed`。
- `changed -> reviewed` 只能通过人工操作完成；系统不提供任何自动恢复 normal 的机制。

## Why This Design

当前业务真正关心的是：

- 对某个 variants 集合来说，哪些项的 pivot language 发生了变化
- 这些变化是否已经被人工确认处理
- 哪个 authority 对当前 outstanding change 负责

当前不需要解决的问题是：

- child 是否自动跟 parent in-sync
- child 是否按内容语义重新翻译
- pivot 内容具体变了多少次

因此 pivot 设计不应该围绕 child drift、fingerprint 或 per-child checkpoint 展开，而应该围绕：

- variant 上是否存在 outstanding pivot change
- 这个 outstanding change 是谁产生的
- 谁可以把它手动 review 掉

## Settled Decisions

- `pivot` 是 variant-level state，branch 不是状态主体。
- `branch_ref` 在 pivot 里只承担两种角色：
  - 作为 variants workspace 的筛选条件
  - 作为手动 review 操作的 actor branch
- `reviewed` 替代原先讨论中的 `in-sync`，语义是“当前 outstanding pivot change 已被人工确认处理”。
- 低 authority branch 不能 review 高 authority branch 产生的 `changed` 状态。
- 如果同一个 variant 先后被不同 authority 的 branch 修改了 `pivot_language`，当前 outstanding change 的 owner 以最近一次有效 pivot 修改为准。

## Core Model

### 1. Project Schema

project schema 继续只允许单一 `pivot_language`：

- `pivot_language: string | null`
- `pivoted_languages: string[]`

这组 schema 配置只负责说明：

- 哪个语言是 pivot source
- 哪些 child language 业务上依赖这个 pivot

但 V1 的 runtime pivot status 不再为 child 单独存状态，也不尝试自动推导 child 是否已经跟上。

### 2. Variant Pivot State

建议在 `variants` 表直接新增下列字段：

- `pivot_status TEXT NOT NULL`
  - allowed values: `init`, `changed`, `reviewed`
- `pivot_changed_by_scope_type TEXT`
- `pivot_changed_by_scope_value TEXT`
- `pivot_changed_at TEXT`
- `pivot_reviewed_at TEXT`
- `pivot_status_updated_at TEXT NOT NULL`

含义：

- `pivot_status`
  - 当前 variant 的 pivot runtime state
- `pivot_changed_by_scope_*`
  - 当前这轮 outstanding pivot change 是由哪个 branch actor 触发的
- `pivot_changed_at`
  - 当前这轮 pivot change 最近一次进入 `changed` 的时间
- `pivot_reviewed_at`
  - 最近一次从 `changed` 被人工 review 的时间
- `pivot_status_updated_at`
  - 最近一次 pivot status 发生变化的时间

这里不需要额外记录 child 语言的任何 checkpoint，也不需要保存 revision/fingerprint。

## State Machine

### On Variant Create

- 新建 variant 时一律初始化为 `init`
- 即使 create payload 里已经带有 `pivot_language` 内容，也不直接进入 `changed`
- create 不设置 `pivot_changed_by_scope_*`

原因：

- `init` 表示“这是这个 variant 的起始内容”
- `changed` 表示“起始内容之后又发生了新的 pivot 修改”

### On Effective Variant Update

先沿用当前写路径已有的语义层比较：

- merge payload
- 如果 `variant_matches == true`，则是 `NOOP`
- `NOOP` 不改变 pivot state

如果不是 `NOOP`，再看这次是否真正改到了 `pivot_language`：

- 未改到 `pivot_language`
  - pivot state 不变
- 改到了 `pivot_language`
  - `pivot_status = changed`
  - `pivot_changed_by_scope_type/value = 当前操作 branch`
  - `pivot_changed_at = now`
  - `pivot_status_updated_at = now`

如果当前状态已经是 `changed`，再次改到 `pivot_language` 时仍然保持 `changed`，但 owner 和 `pivot_changed_at` 要覆盖为最新一次有效 pivot 修改。

### On Manual Review

review 是单独的显式动作，不从普通 mutation 自动触发。

前置条件：

- variant 当前 `pivot_status == changed`
- actor branch 对该 variant 有可见性
- actor branch 的 authority 必须大于等于 `pivot_changed_by_scope_*`

成功后：

- `pivot_status = reviewed`
- `pivot_reviewed_at = now`
- `pivot_changed_by_scope_type/value = null`
- `pivot_status_updated_at = now`

不允许：

- `init -> reviewed`
- 非 `changed` 项执行 review
- 低 authority branch review 高 authority branch 产生的 `changed`

## Authority Rules

当前仓库已经有 canonical variant + branch authority 规则，pivot review 应直接复用这套顺序，而不是新造权限体系。

建议规则：

- 把 review 请求里的 `branch_ref` 当作 actor branch
- 读取当前 variant 上记录的 `pivot_changed_by_scope_*`
- 使用现有 authority comparison 规则判断：
  - actor authority `<` changed-owner authority：拒绝
  - actor authority `>=` changed-owner authority：允许

典型例子：

- variant A 同时被 `dev/2.4.3` 和 `rel/current` 绑定
- `rel/current` 修改了它的 `pivot_language`
- A 进入 `changed`
- owner 记录为 `rel/current`
- 此时不能从 `dev/2.4.3` 把它 review 回 `reviewed`
- 必须从 `rel/current` 执行 review

如果之后又由更低 authority 的 dev branch 修改了同一个 variant 的 pivot language，这种修改是否允许，本身仍由当前 canonical variant mutation policy 决定；pivot 模型不额外放宽这条边界。

## Read Model

建议复用现有 variants workspace，而不是单独设计 branch-scoped pivot state 表。

variants workspace 新增返回字段：

- `pivot_status`
- `pivot_changed_by_branch_ref`
- `pivot_changed_at`
- `pivot_reviewed_at`

建议新增过滤条件：

- `pivot_status`
- 可选 `pivot_changed_by_branch_ref`

继续复用现有 `branch_ref` 过滤：

- `branch_ref` 只筛选“当前哪些 variant 被该 branch 绑定”
- `pivot_status` 仍然来自 variant 本身

这能直接支持：

- 看 `dev/2.4.3` 当前绑定 variants 中哪些是 `changed`
- 看 `rel/current` 中哪些是 `changed`
- 看全项目哪些 outstanding change 由 `rel/current` 产生

## Manual Review API

建议新增专用动作接口，例如：

- `POST /api/projects/{project_id}/variants/pivot/review`

请求体：

- `branch_ref`
- `variant_ids[]`

处理方式：

- 按 variant 逐条校验
- 对通过校验的项执行 `changed -> reviewed`
- 返回逐条 report row

建议的逐条状态：

- `REVIEWED`
- `NOT_CHANGED`
- `NOT_VISIBLE_IN_SCOPE`
- `FORBIDDEN_BY_AUTHORITY`
- `MISSING`

这样前端可以先在 variants workspace 里筛选：

- `branch_ref=dev/2.4.3`
- `pivot_status=changed`

再批量提交 review。

## Important Implication

虽然 review 时带 `branch_ref`，但状态仍然是 variant-level。

这意味着：

- 如果某个 variant 同时被多个 branch 绑定
- 在其中一个 branch 视图里把它 review 成 `reviewed`
- 这个 variant 在其他 branch 视图里也会一起显示为 `reviewed`

这是有意设计，不是 bug。因为当前设计原则已经明确：

- pivot 是 variant-level fact
- branch 只是查看和操作该 fact 的视角

## Non-Goals

- 不做 per-child drift state
- 不做 fingerprint / content checksum
- 不做 `pivot_revision`
- 不做自动从 `changed` 恢复 `reviewed`
- 不根据 child 修改自动推导 pivot 已处理
- 不引入 branch-level 独立 pivot state

## Example Lifecycle

1. variant 创建
   - `pivot_status = init`

2. `dev/2.4.3` 修改了 `pivot_language`
   - `pivot_status = changed`
   - owner = `dev/2.4.3`

3. 下游确认完，从 `dev/2.4.3` 批量 review
   - `pivot_status = reviewed`

4. 后来 `rel/current` 又修改了这个 variant 的 `pivot_language`
   - `pivot_status = changed`
   - owner 切换为 `rel/current`

5. 此时不能从低 authority 的 `dev/2.4.3` 把它改回 `reviewed`
   - 只能从 `rel/current` review

## Implementation Notes

- 变更检测应继续复用当前 mutation 路径里的 `merged_variant_payload()` + `variant_matches()` 语义，避免把无效导入误判为 pivot change。
- “是否改到了 `pivot_language`” 必须基于 old/new normalized translation value 对比，而不是基于 import row 里是否出现了 pivot column。
- 如果后续要把这份设计固化成 runtime facts，需要同步更新：
  - `docs/system.md`
  - `docs/contracts.md`
  - `docs/workflows.md`

## Relationship To Older Design Notes

- 这份设计取代早期 `pivot = child drift + fingerprint checkpoint` 的方向。
- 老的讨论稿保留在 [`archive/pivot-language-design.md`](../archive/pivot-language-design.md) 作为历史记录，不再作为当前实现方案。
