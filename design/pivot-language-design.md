# Pivot Language System Design

## Summary

- `pivot` 需要拆成两层来设计：
  - `pivot topology`：语言之间的依赖方向，属于 project schema，例如 `fr -> en`
  - `pivot drift`：同一 `variant` 内部 child 语言相对 parent 语言的同步状态
- V1 的目标不是改变 Fill 的 `(business_key, source)` 命中规则，而是在保持现有命中语义的前提下，让 branch-scoped Fill 能读取“目标语言是否相对 pivot parent 失同步”的 runtime 信号。
- V1 的第一个消费者是 branch-scoped Fill，而不是固定读取 `rel/current` 的旧 Fill 行为。
- 这份设计支持 many-to-one：多个 child 可以共享同一个 pivot parent，例如 8 种语言都依赖 `en`。
- 这份设计不支持 multi-parent 或链式依赖：每个 child 最多一个 pivot parent，任何被别人指向的 parent 自己不能再配置 pivot。

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

当前 live runtime 里的 Fill 仍然是 release-scoped：

- [`FillRequest`](../app/schemas.py) 还没有 `branch_ref`
- [`/api/projects/{project_id}/fill`](../app/routers/workflows.py) 也没有 branch 参数
- [`FillService`](../app/services/workflows/fill.py) 当前硬编码读取 `rel/current`

所以这份设计稿不是在描述“现状已经如此”，而是在定义 pivot V1 要求 runtime 升级到什么目标形态：

- Fill 需要变成 branch-scoped workflow
- `branch_ref` 需要成为必填 contract
- pivot drift 需要从 branch 选中的 active variant 上读取，而不是永远从 `rel/current` 读取

如果这一步不做，下面的 pivot 设计即使落到存储层，也无法被当前 Fill 正确消费。

## Goals

- 在 project schema 中表达稳定的 `child -> parent` pivot 方向
- 在同一 `variant` 上表达 child 语言相对 pivot parent 的同步或失同步状态
- 保持现有 `Entry / Variant / Scope Binding` 身份与 canonical same-source 规则不变
- 保持 Fill 仍按 `(business_key, source)` 命中 candidate variant
- 让 Fill 从 branch 选中的 active binding 消费 pivot drift
- 支持 many-to-one pivot fan-out，例如多个目标语言共同依赖 `en`
- 为将来的 queue、compare、QA 复用这套 runtime 信号预留清晰边界

## Non-Goals

- 不把 `pivot` 放进 `variant` 身份或 canonical-source 去重规则
- 不让 `pivot` 参与 branch authority、replace、trash/restore、scope binding 逻辑
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

实现落地时，project create/bootstrap 最终都需要把 `translation_pivots` 和 `translation_columns` 一起暴露出来；这份设计稿先定义语义边界。

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

## Why Current Translation Writes Are Not Enough

当前 [`app/services/variant/store.py`](../app/services/variant/store.py) 的 `overwrite_translations()` 会删除并重写整个 translation map。

这意味着：

- 即使只改了 `en`
- `fr`、`de`、`ja` 这些没有语义变化的语言行也会一起被重写
- per-language `updated_at` 不能直接作为 “谁真的变了” 的可靠依据

所以实现时必须先做一个语义层的 changed-set：

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

因此 V1 Fill 的语义应该是：

1. `branch_ref` 是必填 contract
2. Fill 仍然按 `(business_key, source)` 命中 candidate variant
3. candidate variant 来自 `branch_ref` 选中的 active binding，而不是固定来自 `rel/current`
4. 目标语言回填逻辑保持不变
5. 如果本次 `lang` 配置了 `pivot_lang`
6. 则额外读取 candidate variant 上该 child 语言的 sync checkpoint
7. 根据 checkpoint 与当前 parent fingerprint 的比较结果，输出 runtime pivot 状态

建议的 Fill 请求与上传语义：

- `FillRequest` 需要 `branch_ref`
- upload-folder Fill 也需要 `branch_ref`

建议的 Fill 报告字段：

- `pivot_lang`
- `pivot_sync_status`
- `pivot_branch_text`

其中：

- `pivot_sync_status` 只表达 child 相对 parent 的 runtime 状态，如 `PIVOT_IN_SYNC` / `PIVOT_OUT_OF_SYNC` / `MISSING_CHILD` / `MISSING_PARENT`
- 主 `status` 仍然维持 `FILLED` / `MISSING_KEY_IN_BASE` / `SRC_MISMATCH` / `SKIPPED_*`

### Example: `dev/2.4.2` -> `dev/2.4.3`

假设：

- `fr -> en`
- `dev/2.4.2` 里已有 10 条旧条目，且 `fr` 和 `en` 都存在
- `dev/2.4.3` 先导入 `en`
- 旧条目 10 条里，`(key, source)` 都不变，但其中 5 条的 `en` 文本变了
- 同时 `dev/2.4.3` 新增 5 条只有 `en` 的新条目
- 当前执行的是 `branch_ref = dev/2.4.3` 上的 `fr` Fill

那么在 `dev/2.4.3` 上执行 `fr` Fill 时：

- 旧 10 条里，`en` 没变的 5 条：
  - exact match
  - `fr` 可以正常 fill
  - `pivot_sync_status = PIVOT_IN_SYNC`
- 旧 10 条里，`en` 已变但 `fr` 未同步的 5 条：
  - 仍然是 exact match，因为 `(key, source)` 没变
  - `fr` 仍然可以被 fill
  - 但 fill 出来的是 stale `fr`
  - `pivot_sync_status = PIVOT_OUT_OF_SYNC`
- 新增的 5 条：
  - 如果 `en` 已存在而 `fr` 为空
  - 则 child 是缺失状态
  - `pivot_sync_status = MISSING_CHILD`

这个例子说明：

- `PIVOT_IN_SYNC / PIVOT_OUT_OF_SYNC / MISSING_CHILD / MISSING_PARENT` 不是 parent 的状态
- 它们始终是 child 语言相对 parent 的状态
- 同一个 parent 变化，可以同时影响多个 child，但状态仍分别记在各个 child 上
- Fill 读取的是目标 branch 的 active binding，而不是历史 branch 或固定 release branch

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
- 不应把它写死在 `FillService` 里
- Fill 只是第一个消费者，不应该成为唯一事实来源

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

- `docs/contracts.md`：Fill contract、bootstrap schema 字段
- `docs/workflows.md`：branch-scoped Fill 语义、pivot 报告字段
- 可能还有 `docs/system.md`：schema 与 variant runtime 状态的系统级不变量

## Design Summary

这套 pivot 系统要兜住的不是“某个 Fill 文件里 en 有没有变”，而是：

- project schema 上，谁依赖谁
- variant runtime 上，谁已经相对谁失同步
- branch-scoped Fill 如何消费这套 runtime drift

因此，最小正确设计应当包含：

- schema 级 `translation_pivots`
- variant 级 sync checkpoint
- 基于真实 changed-set 的状态迁移规则
- child-owned 的 `PIVOT_IN_SYNC / PIVOT_OUT_OF_SYNC / MISSING_CHILD / MISSING_PARENT` 状态模型
- branch-scoped Fill 对 runtime drift 的消费，而不是临时推断

如果后续实现严格遵守这些点，就能稳妥覆盖：

- `fr -> en`
- 8 种语言都依赖 `en`
- 同一 variant 下 parent 静默变化而多个 child 未同步
- parent 缺失与 child 缺失分开的状态语义
- `dev/2.4.3` 这类目标 branch 上的 Fill 消费场景
