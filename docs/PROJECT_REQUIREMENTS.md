# Momo TMS 产品需求说明

> 当前文档口径：同时描述“目标产品能力”和“当前实现现状”，用于对齐 `dev / release / master` 三线生命周期、Excel 业务表结构与 API 能力。

## 1. 产品目标

Momo TMS 面向 Windows Excel 本地化流程。当前阶段的核心目标不是做通用 SaaS TMS，而是把 Excel 导入、三线流转、受控更新、回填导出和质检报告串成可追溯的版本链路。

当前文档重点回答三个问题：
- 三线分别承担什么职责，允许什么动作，如何流转。
- 项目的 `master` 业务表到底长什么样，哪些列是业务列，哪些字段应由系统维护。
- 我们期望拥有的能力，与当前 API / 实现是否对得上，缺口在哪里。

## 2. 三线模型

| 线 | 产品职责 | 当前有效状态 | 允许的核心动作 | 不允许或默认不开 |
| --- | --- | --- | --- | --- |
| `dev` | 接收入库、批量更新、形成 `dev_last` | 由 `branch_heads.dev` 指向当前快照 | import、update from files、fill、qa、report | 直接归档到 master、直接面向发布 |
| `release` | 面向发布版本，承接 promote，允许受控 hotfix | 由 `branch_heads.release` 指向当前快照 | active hotfix、passive hotfix、promote execute、archive 源、delete keys、fill、qa | 批量自由写回、自动删除 |
| `master` | 历史沉淀与归档线，用于回填兜底 | 由 `branch_heads.master` 指向当前快照 | archive 落地、fill、qa、受控 delete | hotfix、promote 目标线 |

补充约束：
- `snapshot` 是版本节点，不等于“当前线头”。
- `branch_heads` 才定义当前 `dev / release / master` 的有效状态。
- 所有变更型动作都应产出 `snapshot + report + job`，并更新对应 branch head。

## 3. Project 级表结构契约

### 3.1 Business Sheet Contract

`master` 表结构应理解为 `project-level sheet contract`，而不是全局固定列模板。

固定业务列：

| 列名 | 是否必填 | 说明 |
| --- | --- | --- |
| `文件名` | 是 | 业务来源文件名；用于定位条目所属文件与回填目标。 |
| `key` | 是 | 业务 key。 |
| `source` | 是 | 源文，当前默认是中文。 |

标准可选列：

| 列名 | 默认状态 | 说明 |
| --- | --- | --- |
| `版本号` | 默认启用 | 是否启用、是否必填由 project schema 决定。 |

可配置列：
- `翻译语言列`：在创建 project 时定义，列数量、顺序、列名可变。
- `备注列`：在创建 project 时定义，列数量、顺序、字段名可变。

创建 project 的两种方式：
- `从模板创建`：使用固定语言列和备注列模板。
- `自定义创建`：自行定义语言列、备注列及顺序。

推荐业务主键与冲突语义：
- 推荐业务主键：`文件名 + key`
- `source` 不属于主键，但参与语义冲突判断。
- 对同一 `文件名 + key`，若 `source` 不同，则视为语义冲突。

### 3.2 System Metadata Contract

以下字段必须由系统定义，但不应作为业务同学维护的 Excel 列：

| 字段 | 含义 |
| --- | --- |
| `project_id` | 所属项目 |
| `schema_id` | 所属 schema 版本 |
| `import_batch_id` | 导入批次 |
| `snapshot_id` | 当前条目所在快照 |
| `branch` | 当前快照所属线：`dev/release/master` |
| `uploaded_at` | 首次导入时间 |
| `updated_at` | 最近一次系统修改时间 |
| `source_file_path` | 原始文件路径 |
| `sheet_name` | 原始 sheet 名 |
| `row_index` | 原始行号 |
| `job_id` | 最近一次变更 job |

关键原则：
- `当前所属 dev/release/master` 必须被系统管理，但它是 snapshot 上下文，不是 Excel 业务列。
- `上传时间` 和 `最近修改时间` 应在数据库/API 中维护，不要求业务同学回填 Excel。
- 业务字段和系统字段必须严格分层。

详细定义见 [PROJECT_SCHEMA_CONTRACT.md](./PROJECT_SCHEMA_CONTRACT.md)。

## 4. 生命周期主链路

当前推荐主链路：

`import -> update dev -> promote preview -> promote execute -> release hotfix -> archive -> fill/export -> qa`

### 4.1 生命周期动作定义

| 动作 | 输入 | 作用线 | 是否改变系统内容 | 是否产出 `snapshot / report / job` | 关键规则 |
| --- | --- | --- | --- | --- | --- |
| Import files | Excel 文件集合、语言、target 列 | `dev` 前置动作 | 否，仅记录导入批次 | `import batch`，无 snapshot/job | 负责解析与定位，不直接写入三线 |
| Update Dev from files | 导入文件集合、语言、版本号、父快照 | `dev` | 是 | 是 | LWW 语义，生成新的 dev snapshot 并更新 `dev_last` |
| Promote Preview | `dev_last` + current release | `release` 评估 | 否 | report，当前不单独落 job | 统计 added / conflict / carried / deprecated |
| Promote Execute | `dev_last` + current release + release version | `release` | 是 | 是 | 目标 key 集合固定为 `Keys(dev_last)`；同 key 但 `source` 不同则保留旧 release |
| Release Active Hotfix | `key + lang + new target` | `release` | 是 | 是 | 仅改 target，`source` 不变 |
| Release Passive Hotfix | `key + new source + all language targets` | `release` | 是 | 是 | 允许新增 key；`source` 变化触发整条语义更新 |
| Archive Release -> Master | current release + current master | `master` | 是 | 是 | 以 master 为底叠加 release；同 key 冲突时以 release 归档版本覆盖 |
| Delete Keys | key 清单 + 目标线 | `dev / release / master` | 是 | 是 | 仅手动触发；未命中 key 进入 report，不静默吞掉 |
| Fill from base | 文件集合 + release/master snapshot + 语言 | 导出动作 | 否 | report + artifact；当前走 job | `release > master`；`key + src_hash` 都命中才回填 |
| QA report | 文件集合 + 语言 | 验证动作 | 否 | report；当前走 job | 校验 `{}`、`|`、`<tag>` 等结构 |

## 5. 产品能力与当前实现对照

### 5.1 三线管理与生命周期

| 目标能力 | 当前实现 / API 状态 | 缺口 / 备注 |
| --- | --- | --- |
| 三线都有明确 current head | 已实现 `branch_heads` 持久化；`GET /api/workbench/state` 返回三线状态 | 基础 API 还没有单独的 branch heads 查询接口 |
| Promote 拆分 preview / execute | 已实现 `/api/workbench/promote/preview` 与 `/api/workbench/promote/execute` | 旧基础 API 仍保留单步 `/promote` |
| Release 归档到 Master | 已实现 `/api/workbench/archive` | 未暴露为基础 API |
| Delete keys 作为受控生命周期动作 | 已实现 `/api/workbench/delete` | 未实现 delete preview；master 权限控制仍是文档约束，不是权限系统 |
| 所有变更动作都有审计 / 结果追踪 | 已实现 `jobs`、report、artifact 路径、snapshot_id 记录 | 仍缺角色权限、操作人、trace id 等完整审计字段 |

### 5.2 Content Management

| 目标能力 | 当前实现 / API 状态 | 缺口 / 备注 |
| --- | --- | --- |
| Dev 批量写回形成 `dev_last` | 已实现 `/update/dev` 与 `/api/workbench/update-dev` | 基础 `/update/dev` 仍是 query 参数风格，不够统一 |
| Release active single hotfix | 已实现 `/update/release/active_single` 与 `/api/workbench/hotfix/active` | 基础 API 只返回 `snapshot_id`，report 在 workbench API |
| Release passive single hotfix | 已实现 `/update/release/passive_single` 与 `/api/workbench/hotfix/passive` | 同上 |
| Master 仅允许 archive 与受控 delete | 当前实现符合这个边界 | 约束主要体现在 API 暴露层，还没有权限系统硬限制 |

### 5.3 验证、导出与报告

| 目标能力 | 当前实现 / API 状态 | 缺口 / 备注 |
| --- | --- | --- |
| Fill 导出保持原结构，仅写 target 列 | 已实现 `/fill` 与 `/api/workbench/fill` | 当前更偏样例驱动验证，不是通用上传流程 |
| QA 报告定位到 file/sheet/row/key/lang | 已实现 workbench QA job | 基础 API 尚未暴露 QA endpoint |
| Jobs & Reports 统一查看 | 已实现 `/api/jobs/*` 与单页 workbench | 仍是验证层体验，不是最终产品信息架构 |

### 5.4 Project Schema 与表结构契约

| 目标能力 | 当前实现 / API 状态 | 缺口 / 备注 |
| --- | --- | --- |
| 每个 project 拥有独立的 sheet schema | 当前仅在文档中明确，代码层尚未持久化 `project/schema/template` | 需要正式引入 project schema 数据模型 |
| 翻译语言列可在建项时自定义 | 当前样例与实现仍偏固定列假设 | 需要导入、fill、qa 统一改为按 schema 解析 |
| 备注列可在建项时自定义 | 当前仅支持样例场景中的固定列集合 | 需要 schema 驱动的列定义和回填规则 |
| 模板创建与自定义创建并存 | 当前未实现 | 需要模板配置与 project 创建流程 |
| Excel 业务列与系统字段分离 | 当前概念上已分离，`jobs/import/snapshot` 已承担部分系统字段 | 仍需正式文档和 API 模型收口 |

### 5.5 尚未实现或未正式开放

以下能力仍属于目标能力，不应在文档里误写成“已完成”：
- untranslated report
- diff / delta report
- conflict report
- package validation
- delete preview
- 通用文件上传流程与权限模型
- project / schema / template 持久化能力

## 6. 非目标

当前阶段不承诺以下内容：
- 复杂 RBAC、审批流、操作人体系
- 在线协作与任务分发
- 大规模性能优化
- 通用 SaaS 化项目 / 语言 / 供应商模型

## 7. 当前验收标准

### 7.1 已验证链路
- 后端自动化测试已覆盖 promote preview / execute、archive、delete、QA 基础规则、workbench 核心链路。
- 前端 E2E 已覆盖：
  - workbench 首屏加载
  - import + update dev
  - active / passive hotfix
  - promote preview / execute
  - archive + delete
  - fill + qa

### 7.2 文档更新后的校验要求
- 三线职责在 `PROJECT_REQUIREMENTS`、`capability matrix`、`ARCHITECTURE_DESIGN` 三份文档中表述一致。
- 生命周期动作名称、输入、输出、约束保持一致。
- `master` 表结构必须被表述为 `project-level sheet contract`，不能再写成全局固定列。
- `当前所属线`、`上传时间`、`最近修改时间` 等系统字段必须明确存在，但不能误写成 Excel 业务列。
- “目标能力”与“当前实现”必须显式区分，不能混写。
