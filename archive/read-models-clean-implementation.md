# Read Models Clean Implementation

## Goal

- 这份设计文档定义 `app/services/read_models` 的终态 clean implementation，而不是对当前结构继续补丁式整理。
- 终态 `read_models` 必须围绕稳定读数据集组织，而不是围绕旧 endpoint、旧页面或旧 service 名称拆分。
- 所有 preview、summary、inspection、workflow 读依赖都必须建立在统一基础读模型上，不能各自复制查询规则和 row assembly。
- branch-first 遗留核心结构需要被删除替换，避免双读侧、重复 hydration、以及 selector 与 service 混层。
- `master` 只是一种 scope selector，不再作为独立 read service 存在。

## Problem Restatement

当前 scope-first read side 真正要回答的问题，可以稳定收敛为 5 类读需求。

### 1. Scope Membership

回答的问题：

- 某个 scope 当前绑定了哪些 live variants
- 某个 `business_key` 或 `source` 在指定 scope 下当前解析到什么

是否是基础数据集：

- 是

当前大致对应：

- `/scopes/{scope_ref}/rows`
- `/scopes/{scope_ref}/lookup`
- `master` alias 路由背后的读逻辑

为什么不能继续按旧 service 名字拆：

- 它的稳定核心不是 “catalog” 或 “master”，而是 “scope -> live members”
- `master` 只是同一查询族的一个 selector，不该拥有独立 service

### 2. Project Live Variants

回答的问题：

- 项目里所有非 trashed variants 的工作台视图是什么
- 哪些 variants 当前是 `active` 或 `orphan`
- 按 branch binding、pivot 状态、关键字过滤后还剩什么

是否是基础数据集：

- 是

当前大致对应：

- `/variants` workspace

为什么不能继续按旧 service 名字拆：

- 这个能力面向的是 “项目级 live variant workspace”，不是某个 inspection 页面
- 终态需要作为多个派生视图和 workflow preview 的基础数据集

### 3. Project History

回答的问题：

- 项目历史里有哪些 variant 候选
- 同一个 `business_key + source` 在历史中有哪些 reusable variants
- fill、pivot preview、历史候选查找应该基于什么全集

是否是基础数据集：

- 是

当前大致对应：

- `/history/same-source-candidates`
- fill candidate lookup

为什么不能继续按旧 service 名字拆：

- 它的核心不是 “same-source endpoint”，而是 “project-wide history access”
- fill preview、pivot preview 不能继续各自重定义候选读取逻辑

### 4. Entry Timeline

回答的问题：

- 单个 `business_key` 下所有 variants 的全量状态是什么
- 当前有哪些 active / orphan / trashed variants
- 每个 variant 的 bindings、lifecycle、pivot 信息是什么

是否是基础数据集：

- 是

当前大致对应：

- `/entries/{business_key}/variants`
- `entry_variants inspection`

为什么不能继续按旧 service 名字拆：

- 它是稳定的 entry-level 历史对象集合，不是单纯 inspection 专用页面数据
- 后续任何 timeline、debugging、或 entry-level preview 都应该复用这套基础数据集

### 5. Derived Views

回答的问题：

- 如何从基础读模型推导出 branch summary、replace preview、fill preview、pivot preview

是否是基础数据集：

- 否

当前大致对应：

- `/branches`
- `/branches/replace/preview`
- 未来 fill preview
- 未来 pivot change preview
- 旧 compare / queue 一类面向业务视图的读能力

为什么不能继续按旧 service 名字拆：

- 它们不是 read side 的地基，而是建立在基础数据集之上的派生视图
- 如果继续把 compare / queue 当核心 service，会把 branch-first 结构重新带回来

## Current-State Diagnosis

当前结构的方向是对的，但还停留在“按旧接口拆文件”的阶段，而没有沉到稳定读数据集层。

### 基础查询形状少于模块数

- 当前真正稳定的查询形状，明显少于 `read_models` 下现有模块数
- `summary.py`、`compare.py`、`queue.py` 很大程度只是旧 `_support.py` 的 wrapper
- `master.py` 本质是 `scope membership + master selector` 的 alias，不是独立读模型

这说明当前模块名多于问题域里的稳定数据集，拆分轴不够干净。

### 重复 hydration 与 row assembly

当前至少以下几处都在重复做同一类工作：

- 读取 raw rows
- hydrate variant content
- 查询 bindings
- 计算 lifecycle state
- 归一化 pivot metadata
- 拼装 API row

重复点主要出现在：

- `scope_catalog / history / variants / inspection`

结果是：

- 字段定义和状态判定容易漂移
- 增加 preview 时会继续长出第四套、第五套 row assembly
- 任一公共字段变化都需要多点同步修改

### `_support.py` 混合多层职责

`_support.py` 当前同时承担：

- projection loading
- branch compare
- translation queue
- filtering
- pagination
- compare row shaping
- summary derivation

这不是 support，而是一个旧时代的“读侧总线”。  
终态不应保留这种混合模块。

### `master.py` 把 selector 误建成独立 service

- `master` 是 scope selector，不是独立数据集
- `master.py` 会误导后续实现继续围绕 route alias 建 service
- 兼容 master 路由可以保留在 router 层，但 read model 层不再保留独立 `master` service

### branch package 与 read_models 重叠

- branch package 里旧的 scope read query 责任仍与 read side 重叠
- 这会形成双读侧：一套在 `branch/`，一套在 `read_models/`
- 终态要求 operator-facing read side 统一收敛到 `read_models`

### variant package 混入 read-model 类型

- `variant.records` 里目前包含 `ScopeEntryRecord`、`EntryVariantView` 等 read-side typed dict
- 这些类型并不属于 variant domain，而属于 operator-facing read models
- 继续把它们放在 variant package 会模糊 domain 与 read side 边界

### 需要被删除替换的旧结构

终态设计要求以下旧结构不再作为长期核心存在：

- 旧 `master.py`
- 旧 `_support.py`
- 旧 `compare.py`
- 旧 `queue.py`
- `branch/queries.py` 中与 read side 重复的 scope read query 责任

## Target Architecture

终态目录结构固定为：

```text
app/services/read_models/
  selectors.py
  types.py
  repository.py
  hydrate.py
  datasets/
    scope_members.py
    live_variants.py
    history.py
    entry_timeline.py
  derived/
    branch_summary.py
    replace_preview.py
    fill_preview.py
    pivot_preview.py
```

### `selectors.py`

唯一职责：

- 定义输入选择条件和语义归一

必须包含：

- `ScopeSelector`
- `VariantFilter`
- `HistorySelector`

明确不负责：

- 执行查询
- hydrate content
- 组装 API response

### `types.py`

唯一职责：

- 持有 read side 类型定义

至少定义：

- `VariantSnapshot`
- `BindingInfo`
- `ScopeMember`
- `LiveVariantRow`
- `HistoryCandidate`
- `EntryTimelineItem`

明确要求：

- read-model 类型全部集中在这里
- variant package 不再持有这些 operator-facing 类型

### `repository.py`

唯一职责：

- 返回基础 raw rows 和 projection rows

明确要求：

- 不拼 API response
- 不计算业务状态
- 不处理 endpoint alias
- 不承载 master/compare/queue 命名语义

终态 repository 只关心：

- scope membership raw rows
- live variants raw rows
- history raw rows
- entry timeline raw rows
- projection rows for derived views

### `hydrate.py`

唯一职责：

- 作为唯一共享组装出口

必须负责：

- variant content hydration
- binding hydration
- lifecycle state resolve
- pivot metadata normalization

明确要求：

- 今天散落在 `scope_catalog/history/variants/inspection` 里的手写 row assembly，终态全部统一收口到这里
- dataset 层只声明“要什么数据”，由 hydrator 输出统一 read row shape

### `datasets/scope_members.py`

唯一职责：

- scope membership 数据集

负责：

- 列出某个 scope 下当前 live members
- 按 `business_key` 或 `source` 做 scope-aware lookup

明确不负责：

- master alias 兼容语义
- derived summary 或 preview

### `datasets/live_variants.py`

唯一职责：

- project live variants 数据集

负责：

- 项目级非 trashed variants workspace
- `active / orphan` state
- branch / search / pivot 等过滤

明确不负责：

- timeline
- same-source history
- branch summary

### `datasets/history.py`

唯一职责：

- project history 数据集

负责：

- same-source candidates
- fill candidates
- 未来 pivot preview 所需历史候选

明确不负责：

- scope membership
- variants workspace
- entry timeline

### `datasets/entry_timeline.py`

唯一职责：

- 单个 entry 的 timeline 数据集

负责：

- 某个 `business_key` 下全部 variants 的完整状态视图

明确不负责：

- 项目级 variants workspace
- scope-wide 查询
- preview 专用筛选逻辑

### `derived/*`

唯一职责：

- 派生业务视图

必须遵守：

- 明确是 derived views，不是基础读模型
- 只能消费 datasets
- 不得重新定义基础查询规则

终态含义：

- `branch_summary.py` 只负责 branch summary view
- `replace_preview.py` 只负责 replace preview view
- `fill_preview.py` 只负责 fill preview view
- `pivot_preview.py` 只负责 pivot change preview view

## Canonical Interfaces

下面接口草图定义的是终态 contract，不是分阶段迁移步骤。

### `ScopeMembershipDataset`

```python
class ScopeMembershipDataset:
    def list(self, scope_selector, filters, page): ...
    def lookup(self, scope_selector, *, business_key=None, source=None): ...
```

语义要求：

- `scope_selector` 决定读哪个 scope
- `filters` 只表达基础筛选，不嵌入 preview 语义
- `lookup()` 只接受二选一：`business_key` 或 `source`

### `ProjectLiveVariantsDataset`

```python
class ProjectLiveVariantsDataset:
    def list(self, filters, page): ...
```

语义要求：

- 只面向项目级 live variant workspace
- 默认不返回 trashed
- 统一输出 live variants row shape

### `ProjectHistoryDataset`

```python
class ProjectHistoryDataset:
    def same_source_candidates(self, business_key, source): ...
    def fill_candidates(self, lang): ...
    def pivot_candidates(self, ...): ...
```

语义要求：

- `same_source_candidates()` 是 today route 的稳定接口
- `fill_candidates(lang)` 提供 fill preview / fill workflow 共用的历史候选入口
- `pivot_candidates(...)` 只保留为扩展位，不在本设计里细化更多 wire shape

### `EntryTimelineDataset`

```python
class EntryTimelineDataset:
    def get(self, business_key): ...
```

语义要求：

- 返回单个 `business_key` 下所有 variants 的完整状态集合
- 含 bindings、lifecycle、pivot metadata

### `Derived Views`

```python
class BranchSummaryView:
    def build(self, ...): ...

class ReplacePreviewView:
    def build(self, ...): ...

class FillPreviewView:
    def build(self, ...): ...

class PivotPreviewView:
    def build(self, ...): ...
```

语义要求：

- derived views 只组合 datasets
- 不再把 compare / queue 当作核心 read service

### 关于 `master`

终态要求：

- `master` 通过 `ScopeSelector.master()` 表达
- legacy master routes 只在 router 层保留兼容
- read model 层不再保留独立 `master.py`

### 关于 `compare` 与 `queue`

终态要求：

- `compare` 与 `queue` 不再是 read_models 基础设施
- 如果产品仍需要类似能力，只能作为 `derived/` 视图重建
- 不再保留 `_support.py + compare.py + queue.py` 这一套核心结构

## Boundary Rules

以下规则是实施约束，不是建议。

- `read_models` 是唯一 operator-facing read side
- branch package 不再维护独立的 scope read query service
- variant package 不再持有 read-model 类型
- dataset 层只定义稳定读数据集
- derived 层不得绕过 datasets 直接手写重复查询规则，除非设计文档里特别允许且说明原因
- response row shape 必须由单一 hydrator/assembler 输出，不允许每个 dataset 再手拼一份
- `master` 只能作为 selector 存在，不能重新长成独立 read service
- preview、summary、inspection 都不能各自复制 hydration 与 lifecycle 判定逻辑

## Route / API Mapping

终态下，各现有 API 的落点如下。

| Route / Capability | Target dataset / derived view |
| --- | --- |
| `/scopes/{scope_ref}/rows` | `datasets/scope_members` |
| `/scopes/{scope_ref}/lookup` | `datasets/scope_members` |
| `/variants` | `datasets/live_variants` |
| `/history/same-source-candidates` | `datasets/history` |
| `/entries/{business_key}/variants` | `datasets/entry_timeline` |
| `/branches` | `derived/branch_summary` |
| `/branches/replace/preview` | `derived/replace_preview` |
| `fill preview` | `derived/fill_preview` |
| `pivot change preview` | `derived/pivot_preview` |

终态下的删除映射：

- `master.py` 不再存在
- `compare.py` 不再作为核心路由后端
- `queue.py` 不再作为核心路由后端
- `_support.py` 不再存在

## Implementation Consequences

终态实施后，结构上必须满足以下落点。

### 统一 row assembly

- 现有重复 row assembly 全部统一收口到 `hydrate.py`
- `scope_catalog / history / variants / inspection` 不再各自维护一套手写拼装逻辑

### inspection 并入 datasets

- `inspection.py` 的能力并入 datasets 体系
- 不再长期保留一套“半独立 read side”

### Branch detail 复用 scope dataset

- `BranchDetailService.list_branch_entries()` 改为复用 `ScopeMembershipDataset`
- branch detail 不再单独维护另一条 scope read query 通路

### read-model 类型迁移

- `variant.records` 里的 read-side typed dict 迁到 `read_models/types.py`
- variant package 只保留 domain 与 persistence 相关类型

### 双读侧终止

- `branch/queries.py` 中与 operator-facing read side 重复的 scope read query 责任被删除
- 所有 operator-facing read flows 统一走 `read_models`

### 旧结构删除替换

- `master.py`
- `_support.py`
- `compare.py`
- `queue.py`

这些模块在终态不再保留为核心结构，也不作为长期兼容层存在。

## Validation Checklist

完成该设计的实现时，实施 agent 需要至少检查以下事项：

- 设计与 `docs/system.md` 中 “read_models 是唯一 operator-facing read side” 的边界不冲突
- 没有把 `master` 重新表述成 writable branch
- 没有保留 `_support.py`、`master.py`、`compare.py`、`queue.py` 为长期核心结构
- `design/README.md` 中的 file map 与实际设计文件一致

## Non-Goals

- 这份文档不提供 phased migration plan
- 这份文档不定义短期 patch strategy
- 这份文档不把 `design/` 变成 runtime source of truth
- 这份文档不为 `pivot_candidates(...)` 发明更多当前未被需求锁定的 wire shape 细节

## Assumptions

- 文档语言使用中文，代码标识与路径保留英文
- 这次产出只是一份 design note，不实现代码
- 设计文档强调终态 clean architecture，不提供 phased migration plan
- legacy `compare / queue / master / _support` 采用立即删除替换的目标立场，而不是并存策略
