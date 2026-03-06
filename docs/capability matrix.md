符号：
- `✅`：目标上允许，且当前已有可用实现
- `⚠️`：目标上允许，但当前有限制、仅验证层可用，或能力未完整公开
- `🟥`：目标上需要，但当前未实现
- `❌`：目标上不允许

---

# 三线能力矩阵：目标态 vs 当前实现

## 1. 三线定位

| 线 | 目标定位 | 当前实现现状 |
| --- | --- | --- |
| `dev` | 内容接收入库、批量写回、形成 `dev_last` | 已通过 `branch_heads.dev` 管理当前 head；支持 import + update dev |
| `release` | 发布线，承接 promote，允许受控 hotfix | 已支持 active/passive hotfix、promote preview/execute、delete、archive 源 |
| `master` | 归档沉淀线，作为 fill 兜底基线 | 已支持 archive 落地、delete、fill 兜底 |

---

## 2. Pre-process / Validation 能力

| 能力 | 目标态 Dev | 目标态 Release | 目标态 Master | 当前实现状态 | 当前入口 / 备注 |
| --- | --- | --- | --- | --- | --- |
| Fill from base | ✅ | ⚠️ | ⚠️ | ✅ | `/fill`、`/api/workbench/fill`；当前更偏样例驱动 |
| QA report | ✅ | ✅ | ✅ | ✅ | `/api/workbench/qa`；基础 API 尚未暴露 |
| Untranslated report | ✅ | ✅ | ✅ | 🟥 | 目标能力明确，当前未实现 |
| Diff / Delta report | ✅ | ✅ | ✅ | 🟥 | 当前未实现 |
| Conflict report | ✅ | ✅ | ✅ | 🟥 | 当前未实现，只有 promote/archive 内部冲突规则 |
| Package validation | ✅ | ✅ | ✅ | 🟥 | 当前未实现 |
| Delete preview | ✅ | ✅ | ⚠️ | 🟥 | 当前未实现 |

---

## 3. Content Management

### 3.1 文件 -> 系统

| 能力 | 目标态 Dev | 目标态 Release | 目标态 Master | 当前实现状态 | 当前入口 / 备注 |
| --- | --- | --- | --- | --- | --- |
| Import files | ✅ | ❌ | ❌ | ✅ | `/import`、`/api/workbench/import`；只形成 import batch |
| Update from files | ✅ | ⚠️ | ❌ | ⚠️ | Dev 已实现；Release 批量写回未开放，当前以单条 hotfix 为主 |

### 3.2 单条更新

| 能力 | 目标态 Dev | 目标态 Release | 目标态 Master | 当前实现状态 | 当前入口 / 备注 |
| --- | --- | --- | --- | --- | --- |
| Active single update | ⚠️ | ✅ | ❌ | ✅ | `/update/release/active_single`、`/api/workbench/hotfix/active` |
| Passive single update | ❌ | ✅ | ❌ | ✅ | `/update/release/passive_single`、`/api/workbench/hotfix/passive` |

---

## 4. 线间流转（核心生命周期）

### 4.1 高亮区块
以下能力已经不是“未来态”：
- `promote preview` 与 `promote execute` 已拆分
- `archive release -> master` 已实现
- `delete keys` 已实现
- `jobs / branch heads / report` 已存在于系统中

### 4.2 生命周期矩阵

| 能力 | 目标态 Dev | 目标态 Release | 目标态 Master | 当前实现状态 | 当前入口 / 备注 |
| --- | --- | --- | --- | --- | --- |
| Promote preview | ⚠️ | ✅ | ❌ | ✅ | `/api/workbench/promote/preview` |
| Promote execute | ⚠️ | ✅ | ❌ | ✅ | `/promote`、`/api/workbench/promote/execute` |
| Archive old release -> master | ❌ | ⚠️ | ✅ | ✅ | `/api/workbench/archive` |
| Delete keys | ✅ | ✅ | ⚠️ | ✅ | `/api/workbench/delete` |

---

## 5. 当前能力与 API 对齐情况

| 目标动作 | 当前 API 是否对上 | 说明 |
| --- | --- | --- |
| `dev_last` 状态管理 | ✅ | 当前通过 `branch_heads` + `/api/workbench/state` 提供 |
| Promote 先预览再执行 | ✅ | workbench API 已对上；基础 `/promote` 仍是单步接口 |
| Release hotfix 受控更新 | ✅ | active/passive 都已实现 |
| Release -> Master 归档 | ✅ | 已实现 archive job |
| Delete keys 走受控流程 | ✅ | 已产出 snapshot/report/job |
| Fill 作为基线导出动作 | ✅ | 当前已可运行 |
| QA 作为验证动作 | ✅ | 当前已可运行 |
| Untranslated / Diff / Conflict / Package Validation / Delete Preview | ❌ | 目标有定义，当前代码/API 还没对上 |

---

## 6. Project Schema 与 System Metadata

| 能力 | 目标态 | 当前实现现状 |
| --- | --- | --- |
| 固定业务列 | `文件名 + key + source` | 当前在文档中已明确，代码尚未正式 schema 化 |
| 翻译语言列 | project 创建时可配置，也可套模板 | 当前实现仍偏固定列假设 |
| 备注列 | project 创建时可配置，也可套模板 | 当前实现仍偏样例驱动 |
| 版本号 | 标准可选列，由 project schema 决定是否启用 | 当前代码保留 `version_tag` 语义，但未形成 project 配置 |
| 上传时间 / 最近修改时间 / 当前所属线 | 属于系统字段，不进入 Excel 业务列 | 当前概念上分散在 import / snapshot / jobs / branch_heads 中 |
| Project / Schema / Template 管理 | 应有正式数据模型与 API | 当前未实现 |

---

## 7. 统一约束

以下规则在目标态和当前实现中都应保持一致：
1. Content Management 动作必须可追溯，至少产出 `snapshot_id + report + job`
2. Fill 只能写 `target` 列，不能改文件结构
3. 冲突定义统一为：同 `文件名 + key` 且 `source` 不一致
4. Delete 只能手动触发，不能隐式自动删
5. 任何基线计算都必须显式使用 snapshot，不能依赖“猜当前版本”

---

## 8. 当前真实缺口

当前最需要在文档和产品规划中明确，而不是误写为“已完成”的项：
- 缺少正式公共层的 branch heads API
- 基础 API 与 workbench API 存在双轨，尚未统一
- 未实现 project/schema/template 持久化
- 未实现 pre-process/report 类扩展能力
- 缺少权限、审计主体、错误码、trace id 等工程化能力
