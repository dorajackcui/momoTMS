# Pivot Language System Design

## Summary

- `pivot` 需要拆成两层来设计：
  - `pivot topology`：语言之间的依赖方向，属于 project schema，例如 `fr -> en`
  - `pivot drift`：同一 `variant` 内部 child 语言相对 parent 语言的同步状态
- `pivot` 系统本身是 variant-level 设计，与 branch 正交；它关心的是同一 `variant` 内部不同语言之间的同步关系，而不是哪些 branch 指向这个 `variant`
- V1 的目标不是改变 Fill 的 `(business_key, source)` 命中规则，而是在保持现有命中语义的前提下，让 Fill 能读取“命中的 target 译文是否相对 pivot parent 失同步”的 runtime 信号
- V1 的第一个消费者可以是 Fill，但 Fill 只是消费者，不是 `pivot` 状态的定义者
- 这份设计支持 many-to-one：多个 child 可以共享同一个 pivot parent，例如 8 种语言都依赖 `en`。
- 这份设计不支持 multi-parent 或链式依赖：每个 child 最多一个 pivot parent，任何被别人指向的 parent 自己不能再配置 pivot。

## Agent Start Here

这份文档是给实现 agent 的开工说明，不是现状描述稿。实现时优先按下面这个顺序理解：

1. `pivot topology` 是 project schema
2. `pivot drift` 是 variant-level runtime state
3. Fill/QA/queue/compare 都只是未来可能的消费者
4. branch 只在某个 workflow 明确要“读取某条 branch 当前 active variant”时才需要参与；它不是 `pivot` 模型本身的一部分

## Why This Needs A Dedicated Design

当前讨论里最容易被混在一起的是三个不同问题：

1. schema 上，谁依赖谁
2. runtime 里，谁已经相对谁失同步
3. 某次 Fill 输入文件本身是不是已经落后于目标 branch

前两个问题是 `pivot` 系统本身，第三个问题只是某个 workflow 的输入新鲜度。

如果只在 Fill 时比较“工作簿里的 pivot 文本”和“branch 里的 pivot 文本”，只能回答输入文件新不新，回答不了更关键的问题：

- 同一个 `(business_key, source)` 下，pivot parent 已经变过
- dependent target 还没有同步更新
- 即使 workbook 恰好是最新的，这条 target 仍然应该被视为 `PIVOT_OUT_OF_SYNC`

因此，`pivot` 系统必须先有 runtime 里的持久化同步状态，Fill 只是消费这个状态。

## Current Runtime Mismatch

当前 live runtime 里还没有 `pivot` 系统，但这个缺口主要不在 branch，而在 “variant-level drift 还没有被建模并持久化”。

- [`FillRequest`](../app/schemas.py) 还没有 `branch_ref`
- [`/api/projects/{project_id}/fill`](../app/routers/workflows.py) 和 upload-folder Fill 也都只有目录或上传文件、`lang`、`output_name`
- 当前入口是 [`WorkflowApplicationService`](../app/services/workflows/application.py) -> [`FillService`](../app/services/workflows/fill.py) -> [`FillQueryService`](../app/services/workflows/fill_queries.py)
- 当前查询是 project-scoped：`FillQueryService.list_fill_candidates(project_id, lang)` 直接扫描项目下所有 recorded variants
- 当前匹配仍然按 `(business_key, source)` 建索引，并优先 live variant，只有没有 live same-source 候选时才回退到 trashed history
- 当前 runtime 里没有 `translation_pivots`
- 当前 runtime 里也没有 variant-level 的 pivot sync checkpoint 或 drift state

所以这份设计稿不是在描述“现状已经如此”，而是在定义 pivot V1 要求 runtime 升级到什么目标形态：

- project schema 需要表达稳定的 `child -> parent` 依赖关系
- variant write path 需要维护 child 相对 parent 的 sync checkpoint
- Fill 之类的 workflow 需要能读取命中 variant 上的 pivot drift

如果这一步不做，下面的 pivot 设计即使落到存储层，也无法被当前 Fill 正确消费。

## Current Contract Vs Planned Contract

当前 contract：

- Fill 请求里没有 `branch_ref`
- project schema / bootstrap 里没有 `translation_pivots`
- Fill report 里只有 `match_variant_id` 和 `match_variant_state`，没有 pivot 专属字段

计划中的 contract：

- project create / bootstrap 需要暴露 `translation_pivots`
- variant runtime 需要持久化 pivot sync checkpoint
- Fill report 至少可以增加 `pivot_lang`、`pivot_sync_status`
- `branch_ref` 不是 pivot 模型本身的必要字段；只有当某个 workflow 明确要求“按 branch 当前 active variant 消费”时，才需要额外进入 contract

## Goals

- 在 project schema 中表达稳定的 `child -> parent` pivot 方向
- 在同一 `variant` 上表达 child 语言相对 pivot parent 的同步或失同步状态
- 保持现有 `Entry / Variant / Scope Binding` 身份与 canonical same-source 规则不变
- 保持 Fill 仍按 `(business_key, source)` 命中 candidate variant
- 让 Fill 能消费命中 variant 上的 pivot drift
- 支持 many-to-one pivot fan-out，例如多个目标语言共同依赖 `en`
- 为将来的 queue、compare、QA 复用这套 runtime 信号预留清晰边界

## Non-Goals

- 不把 `pivot` 放进 `variant` 身份或 canonical-source 去重规则
- 不让 `pivot` 参与 branch authority、replace、trash/restore、scope binding 逻辑
- 不要求 V1 为 `pivot` 引入 branch-scoped 语义
- 不支持 multi-parent
- 不支持链式依赖
- 不支持 schema edit after create
- 不为旧本地库或旧 project 增加兼容迁移层
- 不在 V1 定义 “acknowledge pivot review” 的正式写接口

## Core Model

### 1. Pivot Topology

`pivot topology` 是 project schema 上的固定配置：

- `translation_pivots: Record<lang, pivot_lang | null>`
- key 是 child 语言
- value 是这个 child 依赖的直接 parent 语言

约束：

- child 必须是 project 的 translation language
- parent 必须是另一个 translation language
- 不允许 `lang -> lang`
- 每个 child 最多一个 parent
- 允许多个 child 指向同一个 parent
- 任何被 child 指向的 parent 自己不能再配置 parent
- 不允许链式依赖或 multi-parent
- schema 在 project create 时固定；后续不提供 schema edit

示例：

```json
{
  "fr": "en",
  "de": "en",
  "ja": "en",
  "ko": "en",
  "es": "en",
  "it": "en",
  "pt": "en",
  "ru": "en",
  "en": null
}
```

上面这个例子是合法的，因为：

- 每个 child 只有一个 parent
- `en` 可以被多个 child 依赖
- `en` 自己没有 pivot

### 2. Pivot Drift

`pivot drift` 不是 schema 配置，而是 variant 级 runtime 状态。

它回答的问题是：

- 当前这个 `variant` 上，child 语言是否仍然对应于它上一次确认时所依据的 pivot parent

这里要特别明确，状态主体始终是 child：

- `PIVOT_IN_SYNC`
- `PIVOT_OUT_OF_SYNC`
- `MISSING_CHILD`
- `MISSING_PARENT`

这些状态都绑定在 child 语言上，不绑定在 parent 语言上。

也就是说，状态主体始终是：

- “这个 child 相对于它的 pivot parent 处于什么状态”

而不是：

- “这个 parent 当前是什么状态”

例如在 `fr -> en` 的配置下：

- 如果 `en` 变了但 `fr` 没变，变化的是 `fr` 的状态，`fr` 变成 `PIVOT_OUT_OF_SYNC`
- 如果 `en` 已存在但 `fr` 没内容，缺失的是 `fr`，所以 `fr` 的状态是 `MISSING_CHILD`
- 如果 `en` 没内容，则 `fr` 的状态是 `MISSING_PARENT`
- 如果 `en` 和 `fr` 已重新对齐，那么 `fr` 的状态是 `PIVOT_IN_SYNC`

因此它必须是：

- variant 级，而不是 branch 级
- 针对 `variant_id + child_lang` 存储
- 由内容更新事件驱动，而不是由 Fill 临时推断

`MISSING_PARENT` 是单独状态，而不是 `MISSING_CHILD` 的文案变体。否则 parent 缺失和 child 缺失会被混成一种状态，后续 Fill、queue、QA 都无法可靠区分。

## Persistence Design

### Project Schema

project schema 新增：

- `translation_pivots_json`

现有 `translation_columns_json` 继续负责语言顺序，不需要被替换成更复杂的结构。

按当前服务边界，`translation_pivots` 的落点应该跟 project schema 一起进入 [`ProjectService`](../app/services/project/service.py) 的 schema 读写，再由 [`ProjectBootstrapService`](../app/services/project/bootstrap.py) 负责向 `/api/projects/{project_id}/state` 暴露；它不应该先塞进 workflow 层。

### Variant Sync Checkpoint

建议新增一张专用表，例如：

`variant_translation_sync_state`

字段：

- `variant_id`
- `lang`
- `pivot_lang`
- `pivot_fingerprint_at_sync`
- `pivot_synced_at`
- `created_at`
- `updated_at`

含义：

- 每条记录表示：这个 `variant` 上，这个 child 语言上一次被认为“已经对齐当前 pivot parent”时，对应的是哪个 pivot 内容版本

这里的 `pivot_fingerprint_at_sync` 建议基于规范化后的 parent 文本生成，而不是只靠 `updated_at`。原因是：

- 当前实现里的 translation 写入是整包重写
- 仅靠时间戳很容易把“哪些语言真的变了”与“哪些语言只是被重写了”混淆

按当前 `app/services` 分层，这张表虽然应该靠近 variant-domain persistence，但状态迁移计算不应该塞进最底层的 [`_VariantStore`](../app/services/variant/store.py) 里。更合理的边界是：

- 原始持久化仍归 `variant` 包的 repository / store 边界
- checkpoint 刷新与 drift 迁移规则运行在高于 raw store 的协调层
- 当前写入口仍然主要经过 [`DirectMutationApplier`](../app/services/branch/direct_mutation.py) 和 [`ImportBatchMutationApplier`](../app/services/branch/import_batch_mutation.py) 这类 branch mutation applier，但它们只是现有写路径入口，不应反过来把 `pivot` 定义成 branch-level 模型

## Why Current Translation Writes Are Not Enough

当前真实写路径是：

- [`VariantCatalogService.create_variant()`](../app/services/variant/catalog.py) / [`VariantCatalogService.update_variant()`](../app/services/variant/catalog.py)
- -> [`VariantCommandRepository`](../app/services/variant/repositories.py)
- -> [`_VariantStore.overwrite_translations()`](../app/services/variant/store.py)

而 [`_VariantStore.overwrite_translations()`](../app/services/variant/store.py) 会删除并重写整个 translation map。

这意味着：

- 即使只改了 `en`
- `fr`、`de`、`ja` 这些没有语义变化的语言行也会一起被重写
- per-language `updated_at` 不能直接作为 “谁真的变了” 的可靠依据

所以实现时必须先做一个语义层的 changed-set，而且这个 changed-set 必须发生在 catalog / repository 写边界之前或之中，而不能在 raw store 重写完成之后再倒推：

- 先把 old translations 和 new translations 逐语言做规范化比较
- 得到“真正变化的语言集合”
- 再基于这个 changed-set 计算 pivot drift 的状态迁移

是否继续保留整包写入实现，是实现细节问题；但设计上不能把“所有语言都被写过”误当成“所有语言都被同步过”。

## State Transition Rules

下面的规则都发生在“同一 `variant` 被更新”的前提下；如果 `source` 变了，那是新 variant，下面的状态不继承。

### On Variant Create

- 为所有配置了 pivot 的 child 语言初始化 checkpoint
- 如果 parent 和 child 在同一次 create/import 写入里都有内容：
  - `pivot_fingerprint_at_sync` 设为当前 parent 文本的 fingerprint
  - 初始状态视为 `PIVOT_IN_SYNC`
- 如果 parent 有内容，但 child 没内容：
  - 仍初始化 checkpoint 行
  - child 状态视为 `MISSING_CHILD`
- 如果 parent 没内容：
  - 仍初始化 checkpoint 行
  - child 状态视为 `MISSING_PARENT`

这个初始化规则是 V1 的默认假设：同一次 create/import 写入里，如果 parent 和 child 都有内容，先视为它们是一起进入当前 variant 的，因此初始化为 `PIVOT_IN_SYNC`。这不等于未来不能再引入更保守的 bootstrap 策略，但 V1 不新增 `UNKNOWN` 类状态。

### On Same-Variant Update

先基于 old/new normalized translations 算出真实 changed-set，再套下面规则：

- parent 没内容：
  - child checkpoint 不表示“已对齐”
  - child 统一视为 `MISSING_PARENT`
- child 变了，parent 没变，且 parent 当前有内容：
  - child checkpoint 刷新到当前 parent fingerprint
  - child 视为 `PIVOT_IN_SYNC`
- parent 变了，child 没变：
  - child checkpoint 保持不动
  - 如果 parent 变更后为空，则 child 变成 `MISSING_PARENT`
  - 如果 parent 变更后仍有内容且 child 有内容，则 child 变成 `PIVOT_OUT_OF_SYNC`
  - 如果 parent 变更后仍有内容但 child 没内容，则 child 保持 `MISSING_CHILD`
- parent 和 child 同时变了：
  - 如果 parent 变更后为空，则 child 视为 `MISSING_PARENT`
  - 如果 parent 变更后有内容且 child 变更后有内容：
    - child checkpoint 刷新到新的 parent fingerprint
    - child 视为 `PIVOT_IN_SYNC`
  - 如果 parent 变更后有内容但 child 变更后仍为空：
    - child 视为 `MISSING_CHILD`
- parent 没变，child 没变：
  - checkpoint 不动
  - 状态不变

### On Source Change

- `source` 变化意味着 canonical same-source 语义已经切换
- 应创建新 variant
- 新 variant 的所有 pivot checkpoint 重新初始化
- 不继承旧 variant 的 sync state

### Many-To-One Fan-Out

如果同一个 parent 被多个 child 依赖，例如多个语言都依赖 `en`：

- 当 `en` 变了
- 所有依赖 `en` 的 child 都要各自独立迁移状态
- 当前已有内容的 child 会按规则变成 `PIVOT_OUT_OF_SYNC`
- 当前没有内容的 child 继续保持 `MISSING_CHILD`
- 如果 `en` 变更后为空，则所有依赖它的 child 都转成 `MISSING_PARENT`
- 之后如果只更新 `fr`
- 只有 `fr` 的 checkpoint 被刷新；`fr` 回到 `PIVOT_IN_SYNC`
- 其它 child 继续保持各自的 `PIVOT_OUT_OF_SYNC`、`MISSING_CHILD` 或 `MISSING_PARENT`

## Fill Consumption Model

Fill 不负责推导 pivot drift，它只负责消费。

这里要先明确一个原则：

- `pivot drift` 是 variant-level 信号
- Fill 只是读取“这次命中的 variant”的 pivot 状态
- 是否再叠加 branch-scoped 选择，是独立的 workflow 设计问题，不是 `pivot` 核心模型的一部分

按当前服务拆分，Fill 侧的未来落点应该明确成：

- [`FillService`](../app/services/workflows/fill.py) 继续保留 workbook 遍历、报告生成、artifact 输出
- Fill 专属读查询仍由 [`FillQueryService`](../app/services/workflows/fill_queries.py) 承担
- pivot 相关读取发生在“Fill 已经命中 candidate variant”之后，而不是让 Fill 重新定义 variant identity

因此 V1 Fill 的语义应该是：

1. Fill 仍然按 `(business_key, source)` 命中 candidate variant
2. 目标语言回填逻辑保持不变
3. 如果本次 `lang` 配置了 `pivot_lang`
4. 则额外读取 candidate variant 上该 child 语言的 sync checkpoint
5. 根据 checkpoint 与当前 parent fingerprint 的比较结果，输出 runtime pivot 状态

建议的 Fill 请求与上传语义：

- `FillRequest` 可以保持现有最小 contract，不必为了 `pivot` 强制引入 `branch_ref`
- upload-folder Fill 同理
- 如果未来产品明确要做 “按某条 branch 当前 active variant 执行 Fill”，那应作为单独 workflow contract 再设计，而不是混入 `pivot` 基础模型

建议的 Fill 报告字段：

- `pivot_lang`
- `pivot_sync_status`

其中：

- `pivot_sync_status` 只表达 child 相对 parent 的 runtime 状态，如 `PIVOT_IN_SYNC` / `PIVOT_OUT_OF_SYNC` / `MISSING_CHILD` / `MISSING_PARENT`
- 主 `status` 仍然维持 `FILLED` / `MISSING_KEY_IN_PROJECT` / `SRC_MISMATCH` / `SKIPPED_*`

### Example: Same Variant, No Branch Semantics Required

假设：

- `fr -> en`
- 某个 `variant` 上 `source = Hello`
- 初始时：
  - `en = Hello`
  - `fr = Bonjour`
  - 所以 `fr` 相对 `en` 是 `PIVOT_IN_SYNC`
- 之后同一个 `variant` 被更新：
  - `en` 改成 `Hello there`
  - `fr` 仍然是 `Bonjour`

那么此时：

- 这个 `variant` 上 `fr` 的状态变成 `PIVOT_OUT_OF_SYNC`
- 这个判断只依赖同一 `variant` 里的 `fr` 与 `en`
- 无论当前有 0 条、1 条还是 3 条 branch 指向这个 `variant`，这个状态都不变

如果之后同一个 `variant` 再被更新为：

- `en = Hello there`
- `fr = Bonjour a tous`

那么：

- child 与 parent 再次对齐
- `fr` 回到 `PIVOT_IN_SYNC`

这个例子说明：

- `PIVOT_IN_SYNC / PIVOT_OUT_OF_SYNC / MISSING_CHILD / MISSING_PARENT` 不是 parent 的状态
- 它们始终是 child 语言相对 parent 的状态
- 同一个 parent 变化，可以同时影响多个 child，但状态仍分别记在各个 child 上
- branch 是否指向这个 `variant`，不会改变这个 `variant` 自己的 pivot drift

## Keep Runtime Drift Separate From Workbook Freshness

这套设计里，必须显式区分下面两个信号：

### A. Runtime Drift

- 当前 variant 上，child 是否已经相对 parent 失同步
- 这是 pivot 系统的核心信号
- 需要持久化

### B. Workbook Freshness

- 某次 Fill 输入文件中的 pivot 文本是否已经落后于目标 branch
- 这是 Fill 的输入对比信号
- 不属于 pivot 系统的核心状态
- 可以后续作为附加报表字段补充，但不应取代 runtime drift

如果未来确实需要，Fill 可以同时报告：

- `pivot_sync_status`
- `pivot_workbook_status`

但这两个东西不能混成一个状态名。

## Implications For Other Workflows

V1 不要求 queue、compare、QA 立刻消费 pivot drift，但设计上应该允许未来这样做。

这意味着：

- pivot drift 的持久化位置应该靠近 variant write model
- 不应把它写死在 `FillService` 或 `FillQueryService` 里
- Fill 只是第一个消费者，不应该成为唯一事实来源
- 如果未来 queue、compare、QA 需要按 branch 展示 pivot 信息，那是“在已有 variant-level drift 之上增加 branch 选择视角”，不是把 drift 本体改造成 branch-level

## Risks And Deferred Decisions

### 1. “同文案同译文，但人工确认过” 的情况

当前设计里，child 要重新变成 `PIVOT_IN_SYNC`，默认依赖 child 自身文本发生了变化。

如果未来需要支持这样的场景：

- parent 变了
- child 最终仍然保持同样的文本
- 但人工已经确认它对当前 parent 仍然成立

那就需要单独的 “acknowledge pivot review” 行为，而不是继续复用普通 translation write。

V1 当前不定义这个接口，也不假装现有写路径已经隐式支持它。这是刻意保留的设计缺口，后续如果产品需要，应该单独设计正式行为。

### 2. Fan-Out 成本

many-to-one 合法以后，parent 一次变化会导致多个 child 状态失效。

这要求实现时：

- 能快速从 schema 得到 `parent -> [children]` 的反向映射
- 变更时只更新受影响的 child checkpoint

### 3. Runtime Reset Strategy

由于这套设计会引入新的 schema 字段和新的 variant 级状态表，默认仍采用 repo 当前策略：

- bump schema version
- reset/reseed
- 不给旧库加兼容迁移分支

### 4. Active Docs Follow-Through

这份设计稿定义的是目标设计，不是当前 active runtime contract。

一旦开始实现，至少还需要同步更新：

- [`docs/contracts.md`](../docs/contracts.md)：Fill contract、bootstrap schema 字段
- [`docs/workflows.md`](../docs/workflows.md)：Fill 消费 pivot drift 的语义、pivot 报告字段
- 可能还有 [`docs/system.md`](../docs/system.md)：schema 与 variant runtime 状态的系统级不变量

更新这些 active docs 时，应继续把当前 runtime 事实锚定在现有实现和 guardrail tests 上，例如：

- [`tests/test_services_architecture.py`](../tests/test_services_architecture.py)：保证当前 package 边界和 Fill 查询归属不回退
- [`tests/test_io_flows.py`](../tests/test_io_flows.py)：保证当前 Fill 的 project-history 候选读取和 live/trashed 选择语义

## Design Summary

这套 pivot 系统要兜住的不是“某个 Fill 文件里 en 有没有变”，而是：

- project schema 上，谁依赖谁
- variant runtime 上，谁已经相对谁失同步
- Fill 等 workflow 如何消费这套 runtime drift

因此，最小正确设计应当包含：

- schema 级 `translation_pivots`
- variant 级 sync checkpoint
- 基于真实 changed-set 的状态迁移规则
- child-owned 的 `PIVOT_IN_SYNC / PIVOT_OUT_OF_SYNC / MISSING_CHILD / MISSING_PARENT` 状态模型
- workflow 对 runtime drift 的消费，而不是临时推断

如果后续实现严格遵守这些点，就能稳妥覆盖：

- `fr -> en`
- 8 种语言都依赖 `en`
- 同一 variant 下 parent 静默变化而多个 child 未同步
- parent 缺失与 child 缺失分开的状态语义
- Fill 报告 matched variant 的 pivot 状态
