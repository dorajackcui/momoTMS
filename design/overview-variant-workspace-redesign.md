# Overview Variant Workspace Redesign

## Summary

- remove the standalone `Variants` page from the primary `/app` navigation
- merge variant inspection, orphan browsing, and restore entrypoints into `Overview`
- redesign `Overview` from a branch-first sheet into a project-wide variant workspace
- make the main surface feel like one very large Excel table, but keep the design honest about current API limits
- the backend gap for project-scoped variant rows is now partially closed by `GET /api/projects/{project_id}/variants`, with V1 coverage limited to `active + orphan`

## Why This Direction Is Good

你的方向是对的，核心收益很明确：

- 把“看数据”和“查 variant 历史”放回同一个主工作台，减少页面跳转
- operator 打开产品后先看到的就是数据平面，而不是工具入口
- orphan inspection 不再是一个单独的“偏调试型页面”，而是主工作流的一部分
- restore、history、branch context 都可以围绕同一张表展开，认知成本更低

如果目标是“先跑流程、再持续收敛 UI”，这会比现在六页结构更接近真实操作习惯。

## Hard Constraints From Current APIs

这版想法里，真正需要先讲清楚的是“想要的交互”和“当前 API 能不能支撑”之间的差距。

### 1. 现在已经有 project-scoped variants query，但它仍是 V1

现有公开接口里已经新增：

- `GET /api/projects/{project_id}/variants`

但它目前只解决了第一步：

- 支持 project-scoped 的 variants workspace rows
- 支持 `active`、`orphan`、`all(active + orphan)` 状态
- 支持 branch filter、`business_key` / `source` 搜索、分页

它还没有解决的部分是：

- `trashed` variants 的主表发现能力
- translation / remark 全列服务端搜索
- 把 fill 的 full-history 语义统一进同一个公开 query

其它公开接口仍然是：

- `GET /api/projects/{project_id}/branches/dev/{version}` 只能拿到某一条 `dev/*` branch 的 active entries
- `GET /api/projects/{project_id}/orphan-variants` 只能拿到 orphan variants
- `GET /api/projects/{project_id}/entries/{business_key}/variants` 只能在已知 `business_key` 后查看单条 entry 的完整 history

当前仍然没有：

- 一个同时覆盖 `active + orphan + trashed` 的统一查询
- 一个支持 translation / remark 全列搜索的服务端 variants grid API

所以 backend 缺口已经不再是“完全没有 project-wide query”，而是“V1 query 还不够覆盖所有 lifecycle 和所有列搜索”。

### 2. `branch` 不是天然单值字段

从当前数据结构看，一个 variant 可以有多个 bindings。[branches/types.ts](../frontend/src/domains/branches/types.ts)

这意味着第二列如果叫“所属 branch”，真实语义更接近：

- `bindings`
- `active branches`
- `branch refs`

而不是一个单值 `branch`。

如果仍然显示成单值列，会误导 operator 认为一个 variant 只会属于一个 branch。

### 3. `trashed` variants 仍然无法做成全局收件箱

当前已经有 project-wide variants query，但它在 V1 里仍然明确排除了 `trashed`；同时仍然只有 restore write API，没有全局 trashed variants list API。[variants/api.ts](../frontend/src/domains/variants/api.ts)

这意味着：

- 可以在某个 entry 的 history 里 restore
- 也可以按 `variant_id` restore
- 但不能在主表里直接列出全项目 trashed variants，除非补 backend query

## Recommendation

建议保留你的大方向，但把方案拆成两层：

### Layer A: 产品 IA 决策

- 删除 `Variants` 顶层页面
- `Overview` 成为唯一的 variant 浏览入口
- orphan、history、restore 都并入 `Overview`

这个方向可以直接成立。

### Layer B: 数据实现决策

如果我们真的要“当前项目全部 variant 的超级 Excel 表”，推荐显式新增 backend variants workspace API，而不是在前端用现有接口硬拼。

这个方向也应该直接成立。

## Proposed UX

## Navigation

新的顶层导航改成五个入口：

- `Overview`
- `Intake`
- `Branch Ops`
- `Runs`
- `Project`

`Variants` 从顶层导航删除。

## Overview Positioning

新的 `Overview` 不再是“某个 branch 的表格视图”，而是：

- the main variant workspace for one project
- one row per variant
- one grid that can switch between active work and orphan inspection

默认落点仍然是 `/app/overview`。

## Primary Grid Model

每一行代表一个 `variant`，而不是一个 `entry`。

推荐列顺序：

1. `state`
2. `branches`
3. `file_name`
4. `business_key`
5. `source`
6. translation columns from project schema
7. remark columns from project schema

可选辅助列：

- `variant_id`
- `updated_at`
- `created_at`

其中：

- `state` 至少支持 `active` 和 `orphan`
- `branches` 显示为 badge list 或逗号拼接，不应假装是单值
- translation / remark 列继续动态跟随 schema

## Filtering And Search

你提的表头思路整体合理，我建议细化成下面这套交互：

### Global filters

- `state`: `all / active / orphan`
- `branch`: 多选 filter，按 `branch_ref` 过滤
- `lang preset`: 决定显示哪些 translation columns

### Column filters

对下面这些列提供单列搜索：

- `file_name`
- `business_key`
- `source`
- each translation column
- each remark column

### Search semantics

- state 和 branch 应该走服务端过滤
- 文本列搜索如果数据量大，也应该走服务端过滤
- 前端只保留轻量本地筛选，不承担“把全项目几万条 variant 拉下来再筛”的职责

## Row Actions

点击任意行后，右侧 drawer 打开。

drawer 承担三类任务：

- show current variant details
- show all variants under the same `business_key`
- expose restore actions when history里存在 trashed variant

也就是说，旧 `Variants` 页里的 timeline 能力迁移到 `Overview` drawer，而不是消失。

## Orphan Experience

orphan 不再需要单独页面。

推荐交互：

- 默认进入 `state = active`
- operator 切到 `state = orphan` 时，表格就切成 orphan 工作视图
- orphan rows 仍然使用相同列结构
- branch 列对 orphan rows 显示为空或 `-`

这样 operator 不需要理解“为什么 orphan 要去另一个页面看”。

## Restore Experience

restore 不建议直接挂在主表一级按钮上，推荐放在 drawer 里的 history 区：

- 主表负责发现问题
- drawer 负责判断 variant timeline
- restore 仍然从具体 `variant_id` 触发

这样既不丢功能，也不会把主表变成大量危险操作按钮的集散地。

## API Design Needed For The Target UX

## New Read Endpoint

推荐新增一个 project-wide variants workspace query，例如：

`GET /api/projects/{project_id}/variants`

建议查询参数：

- `state=active|orphan|trashed`
- `branch_ref=...`，可重复
- `search_file_name=...`
- `search_business_key=...`
- `search_source=...`
- `search_translation_<lang>=...`
- `search_remark_<key>=...`
- `page`
- `page_size`
- `sort`

建议返回结构：

- `rows`
- `total_rows`
- `page`
- `page_size`
- `available_branches`

每行至少包含：

- `variant_id`
- `business_key`
- `file_name`
- `source`
- `translations`
- `remarks`
- `bindings`
- `state`
- `created_at`
- `updated_at`

## Existing APIs To Keep Using

即使新增主表 query，下面这些接口仍然有价值：

- `GET /api/projects/{project_id}/state`
  - shell 和 schema
- `GET /api/projects/{project_id}/entries/{business_key}/variants`
  - drawer timeline
- `POST /api/projects/{project_id}/variants/trash/restore`
  - restore action

## Why Frontend-Only Composition Is Not Enough

不推荐下面这条路：

- 用 `dev branch detail` 当 active rows
- 再把 `orphan-variants` 贴进去
- 假装这就是“全项目全部 variant”

问题在于：

- 它只覆盖一条 branch 的 active rows
- 不能表达一个 variant 绑定了多条 branch
- 不能做真正的 branch filter
- 不能覆盖 trashed
- 数据量上也会很快撞到前端拼装上限

这条路最多只能作为短期 demo，不适合当正式 redesign 目标。

## Recommended Delivery Plan

## Phase 0: Confirm The Data Model

先定三件事：

1. `Overview` 的行模型是否明确改成 `one row per variant`
2. 第二列是否改名为 `branches` 而不是 `branch`
3. 主表是否只先覆盖 `active + orphan`，把 `trashed` 留在 drawer history

这是最先要拍板的范围边界。

## Phase 1: Backend Workspace Query

新增 project-wide variants query，并补齐：

- state filter
- branch filter
- paginated rows
- schema-driven text fields

同时补 backend tests，确认：

- project scope 不泄漏
- active/orphan state 判定正确
- branch filter 对 multi-binding rows 行为清晰
- 分页和搜索结果稳定

## Phase 2: Frontend Overview Rewrite

改造 `Overview`：

- 从 branch sheet 改成 project-wide variants grid
- 删掉当前 branch-first summary mode
- 增加 state filter、branch filter、列搜索
- 把 variant timeline drawer 做成默认 inspection 面板

这一阶段完成后，`Variants` 页面仍可先保留但从导航隐藏，作为过渡 fallback。

## Phase 3: Remove Standalone Variants Page

当下面能力都已经迁入 `Overview` 后：

- orphan browsing
- business key inspection
- history timeline
- restore from history

就可以删除：

- `/app/variants` route
- variants nav item
- variants page tests

同时把所有“跳去 Variants”的入口改成“在 Overview 打开对应 row / drawer”。

## Phase 4: Branch Ops And Queue Link Updates

调整其它页面跳转：

- `Queue` 行点击优先跳 `Overview` 并定位该 row
- `Lookup` 行点击优先打开 `Overview` drawer
- 任何 restore 相关成功反馈统一跳 `Runs`

## Phase 5: Docs And E2E

实现落地时同步更新：

- `docs/contracts.md`
- `docs/user-guide.md`
- 必要时 `docs/workflows.md`

并重写 E2E：

- Overview covers active + orphan browsing
- no top-level `Variants` route in normal nav
- restore path starts from `Overview`

## Proposed Scope For The First Implementation

如果我们想先尽快跑一轮，而不是一次做满，我建议第一版范围如下：

- 删除顶层 `Variants` 导航
- `Overview` 合并 orphan browsing 和 history drawer
- 先支持 `active + orphan`
- trashed 仍然只在 drawer history 里出现
- branch 列显示 `bindings`
- 列搜索先做 `file_name / business_key / source`
- translation / remark 单列搜索放到第二版

这是一个更稳的第一跳，因为它先把信息架构改对，再决定要不要继续把更重的列搜索和全量服务端筛选一次做完。

## Open Questions

- `trashed` 要不要成为主表一级 `state`
- branch filter 是单选还是多选
- 列搜索是否必须首版就覆盖所有 translation / remark 列
- 主表默认排序按 `updated_at`、`business_key`，还是按 state + branch
- 是否需要 URL state 保存列过滤条件，便于分享链接

## Final Recommendation

建议采纳这个方向，但不要把它定义成“纯前端重排”。

更准确的结论是：

- IA 上，`Variants` 合并进 `Overview` 是对的
- 交互上，主工作台应该变成 variant 级超级表格也是对的
- 实现上，需要一个新的 project-wide variants workspace API 才能把这件事做扎实

如果不补这层 query，最终做出来的会是“看起来像全项目大表，实际上只是某个 branch 视图加 orphan 拼接”，后面很容易返工。
