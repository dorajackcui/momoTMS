# PRD 0001: Canonical Source Variant Model (Archived)

Archived on March 14, 2026 during the documentation system refactor. This PRD is implemented and preserved for rationale, migration assumptions, and acceptance context. Active runtime guidance now lives in `docs/architecture/` and `docs/reference/`.

## Status

Implemented.

## Purpose

这份文档最初是实现准则文档；当前保留为已落地模型的规则、迁移约束和验收口径参考。

目标是让新一轮 agent 在修改时只遵守一套清晰规则：

- `entry` 仍是 `project_id + business_key`
- `variant` 改为 `project_id + business_key + source`
- `translations + remarks + file_name` 是 variant content，但不是 identity
- scope 只表达“当前哪个分支指向哪个 source variant”

## Current Runtime Facts

当前代码已经按本 PRD 落地，现状是：

- variant 复用按 `business_key + source`
- branch 写接口已经收敛为 `scope mutation` + `scope sync`
- `dev/*` 和 `rel/current` 的差异通过 policy 表达，不再通过不同方法名表达
- fill / compare / queue / sync 仍然围绕 active bindings 运转

现有相关实现集中在：

- `app/services/branch/service.py`
- `app/services/variant/`

## Target Model

### 1. Entry

- identity: `(project_id, business_key)`
- entry 是稳定槽位，不直接决定 source/content

### 2. Variant

- identity: `(project_id, business_key, source)`
- 同一 entry 下，同一 `source` 只允许一个 canonical variant
- `translations + remarks + file_name` 跟随该 canonical variant 存储

### 3. Scope Binding

- scope 仍是 `rel/current` 或 `dev/<version>`
- 同一 scope 内，同一 `business_key` 只能绑定一个 active variant
- 不同 scopes 可以共享同一个 variant

### 4. Lifecycle

- `active`: 当前被至少一个 scope 绑定
- `orphan`: 当前无 scope，但可被后续同 source 复用
- `trashed`: 被显式删除，不参与自动命中

`retained` 在新模型中并入 `orphan`，实现上已完全删除，不再作为独立长期语义。

## Hard Rules

### Identity

- lookup 永远先按 `business_key + source`
- 不允许再按 `translations + remarks` 判断 variant identity
- fill 的成立前提是 `same source => same translation`

### Content Authority

内容优先级固定为：

- `rel` 最高
- `dev` 次之
- `orphan` 最低

authority 只决定命中已有 same-source variant 时，是否允许覆盖 canonical content。

### Lookup Scope

- same-source lookup 必须覆盖所有 `non-trashed` variants
- 包括 `active` 和 `orphan`
- `trashed` 必须显式 restore 后才能再次参与命中

## Decision Matrix

| Scope mutation policy | Hit target | Binding | Content |
| --- | --- | --- | --- |
| `dev/*` mutation hit rel-bound active variant | rel-bound active variant | bind/rebind dev | keep existing canonical content |
| `dev/*` mutation hit non-rel active variant | non-rel active variant | bind/rebind dev | update canonical `translations/remarks` |
| `dev/*` mutation hit orphan variant | orphan variant | bind dev and clear orphan | update canonical `translations/remarks` |
| `dev/*` mutation miss | miss | create variant and bind dev | write incoming content |
| `rel/current` direct mutation with source change | hit same-source non-trashed variant | rebind rel | update canonical content with rel payload |
| `rel/current` direct mutation with source change | miss | create variant and bind rel | write mutation content |
| `rel/current` direct mutation without source change | current rel variant | keep rel binding | update canonical content in place |

补充规则：

- `dev/*` import-batch mutation 不做逐行 content conflict 检查
- `dev/*` mutation 不会覆盖 rel-bound canonical content
- `dev/*` mutation 可以覆盖 orphan 或纯 dev-shared canonical content
- 本轮不区分 `dev/2.4` 与 `dev/2.5` 的 authority，后写入的 dev 可覆盖未被 rel 占用的 content

## Workflow Rules

### Scope Mutation

统一 mutation 输入：

- `direct`: 显式 `changes[]`
- `import_batch`: 通过 `import_batch_id` 解析出 `changes`

核心规则：

1. `business_key` 不存在且目标 policy 允许：
   - 创建 entry
   - 创建 variant
   - bind 到目标 scope
2. `business_key` 存在，且 `source` 未变化：
   - 更新当前 scope 已绑定 variant
3. `business_key + source` 已存在：
   - hit rel-bound active: 只 bind
   - hit non-rel active: bind 并按 policy 更新 `translations/remarks`
   - hit orphan: bind、清除 orphan，并按 policy 更新 `translations/remarks`
   - 不创建重复 same-source variant

建议 report statuses：

- `UPDATED_BOUND_VARIANT`
- `BOUND_EXISTING_VARIANT`
- `UPDATED_AND_BOUND_EXISTING_VARIANT`
- `CREATED_AND_BOUND_VARIANT`
- `NOOP`

### Scope Sync

- sync 仍然只是 rebinding
- `dev/<version> -> rel/current` 是当前唯一支持的 policy 实例
- sync preview 比较 source/target active bindings
- sync execute 不复制 content，不创建 variant
- `dev/<version> -> rel/current` execute 后会清理同 version line 的 dev bindings

### Trash / Restore

- trash / restore 继续围绕 variant 和 binding 运转
- orphan 与 trashed 不能混用
- restore 不自动重建 scope binding

## Migration Rules

默认采用一次性切换，不做双模型长期共存。

迁移目标：

- 每个 entry 收敛成唯一的 `source -> canonical variant`
- 去除同一 entry 下重复 same-source variants
- 重算 active / orphan / trashed
- 让 fill / compare / queue / scope sync 在新模型下不回归

同 source 多 variant 时，canonical 选择顺序固定为：

1. rel-bound active
2. active
3. orphan
4. `updated_at` 最新

非 canonical 的 same-source variants：

- 不再保留为平行候选
- 在迁移中删除或并入迁移日志

## API / Compatibility Impact

这些语义会变：

- variant identity
- branch mutation report statuses
- direct rel mutation behavior
- inspection response semantics
- old variant rows 的迁移 contract

要求：

- `/api/projects/{project_id}/entries/{business_key}/variants` 必须返回 canonical variants、bindings、orphan state
- compare / queue / master / fill / QA 继续只读 active bindings
- branch 写 API 固定为 `/branches/mutations` 和 `/branches/sync/*`
- `/variants/trash/*` 保持 variant lifecycle 边界
- 不做新旧两套 branch workflow 路由长期共存

## Acceptance

实现完成后，至少要满足：

- 同 source 的 `dev/*` import-batch mutation 不创建新 variant
- dev hit rel-owned variant 时只 bind，不改 content
- dev hit orphan 或 non-rel active variant 时会更新 canonical content
- `rel/current` direct source mutation 会把 rel 从 `abc` 切到 `abd`，原 `abc` 上其他 dev bindings 不受影响
- `rel/current` direct translation mutation 会同步影响所有共享该 variant 的 scopes
- repeated direct source mutation `abc -> abd -> abe -> abf` 后：
  - `abf` 是 rel active
  - 中间失去全部 scope 的 variants 进入 orphan
  - 仍被 dev 使用的老 source 保持 active
- sync 只 rebind，不复制 content
- fill 只从 canonical active variant 取内容
- inspection 能展示 active/orphan canonical variants 及其 bindings
- 迁移后不存在同一 entry 下重复 `source` variants

## Minimum Test Set

- branch mutation:
  - new key + new source
  - existing key + same source hit rel-owned variant
  - existing key + same source hit non-rel active variant
  - existing key + same source hit orphan
  - existing key + new source
- rel/current direct mutation:
  - source change while rel/dev share one variant
  - translation-only change while rel/dev share one variant
  - repeated source changes `abc -> abd -> abe -> abf`
- scope sync:
  - dev to rel rebind
  - version-line cleanup after sync execute
- migration:
  - duplicate same-source variants collapse correctly
  - rel-bound active precedence beats orphan precedence
  - fill / compare outputs remain correct after migration

## Assumptions

- 不新增 product hotfix UI。
- 不做 per-row content conflict 检查。
- orphan TTL / 自动清理后续另立文档。
- remarks 跟随 canonical variant 一起存储，但不是 identity。
