# Momo TMS 产品需求说明

> 本文档定义当前产品范围和业务规则。
> 当前代码已经按 `canonical strings + memberships + trash` 模型运行，以下内容以现实现状为准。

## 1. 产品定位

Momo TMS 是一个面向 Excel 本地化流程的 strings management 系统。

当前版本解决的问题：
- 用 `business_key` 作为唯一键管理 project 内 strings
- 通过本地目录中的 Excel 批量导入 strings
- 用 `rel` 和 `dev_version` memberships 管理开发与发布集合
- 对上线内容提供受控 hotfix
- 提供 soft delete、trash、fill、qa、jobs 和报告

当前范围：
- 单默认 project
- 本地目录导入 `.xlsx`
- 单页 workbench 作为操作和验收入口
- 破坏式重构版本，不兼容旧 `snapshot / branch_heads` 模型

## 2. 核心实体

### 2.1 Project

`Project` 是 strings 的管理边界。

当前实现：
- 只有一个默认 project
- schema 已持久化
- project 级 schema 定义以下内容：
  - 固定列：`file_name`、`business_key`、`source`
  - 翻译列：`translation_columns[]`
  - 备注列：`remark_columns[]`

当前默认 schema：
- `translation_columns[] = [fr, en]`
- `remark_columns[] = [context]`

### 2.2 Canonical String

`String` 是系统中的最小业务对象，也是唯一的 canonical 实体。

当前字段契约：

| 字段 | 是否必填 | 说明 |
| --- | --- | --- |
| `file_name` | 否 | 来源文件名，可空 |
| `business_key` | 是 | project 内唯一标识 |
| `source` | 是 | 原文 |
| `translations[]` | 是 | 按 project schema 定义 |
| `remarks[]` | 是 | 按 project schema 定义 |

关键约束：
- 唯一键是 `business_key`
- `file_name` 不是身份字段
- 同一个 `business_key` 在 project 中只对应一个 canonical string
- 同一 string 在不同 memberships 中共享同一份 canonical 内容

### 2.3 Memberships

当前模型不是三条对称 branch，而是 canonical strings 加 memberships：

| 概念 | 当前语义 |
| --- | --- |
| `master` | 所有未删除 strings 的隐式全集 |
| `rel` | 当前上线集合 |
| `dev_version` | 开发候选集合，例如 `2.2.3` |

规则：
- `master` 不是显式 tag
- `rel` 通过 membership `rel/current` 表达
- `dev_version` 通过 membership `dev/<version>` 表达
- 一个 string 可以同时属于 `rel` 和某个 `dev_version`

## 3. Excel 契约

Excel 业务表当前按 schema 解析，不依赖固定列号。

### 3.1 固定列

- `file_name`
- `business_key`
- `source`

### 3.2 可配置列

- `translation_columns[]`
- `remark_columns[]`

### 3.3 当前导入约束

- 只读取本地目录中的 `.xlsx`
- 跳过临时文件 `~$*.xlsx`
- 缺失 `business_key` 的行标记为 `missing_business_key`
- 缺失 `source` 的行标记为 `missing_source`
- 缺失 schema 所需表头的 sheet 标记为 `sheet_error`

## 4. 业务规则

### 4.1 Dev Import

`dev import` 是当前批量工作流主入口。

按 `business_key` 执行以下规则：
- 新 key：创建 canonical string，并打上目标 `dev_version` tag
- 已存在且不在 `rel`：更新 canonical 内容，并打上目标 `dev_version` tag
- 已存在且已在 `rel`：只加 `dev_version` tag，不覆盖 canonical 内容

当前 report 状态：
- `CREATED`
- `UPDATED_CANONICAL`
- `TAGGED_ONLY`
- `PROTECTED_SKIPPED`

### 4.2 Rel Hotfix

`rel` 只允许受控修改。

当前支持两类操作：
- `active hotfix`：只改某个翻译列
- `passive hotfix`：改 `source`、翻译列和备注列

规则：
- hotfix 修改的是 canonical string
- 如果 string 同时属于 `rel` 和 `dev_version`，变更会被两边同时看到

### 4.3 Promote

当前发布语义固定为：

`rel = target dev_version`

执行结果：
- 目标 `dev_version` 集合切换为新的 `rel`
- 当前版本线的所有 `dev` tags 被清理，例如 `2.2.x`
- 被 promote 的版本线在运行时不再视为活跃 dev versions
- 历史追溯依赖 jobs 和 reports，而不是保留旧 dev tags

### 4.4 Delete / Trash

删除统一作用于 canonical string。

当前规则：
- 删除是 `master soft delete`
- 删除后从运行时 strings、rel、dev 查询中隐藏
- 删除后进入 30 天垃圾桶
- 恢复时恢复 canonical string 本身
- 现实现状下 memberships 不被物理删除，因此 restore 后原 memberships 仍然生效

### 4.5 Fill / QA

`fill`：
- 从 canonical strings 回填 Excel 目标语言列
- 命中优先级：当前 `rel` 集合优先；其他 key 仍可从 `master` 补齐
- `source` 不一致时标记 `SRC_MISMATCH`

`qa`：
- 按 schema 读取指定语言列
- 当前检查规则来自 `qa_service`
- 输出行级问题报告

## 5. 当前能力范围

| 能力 | 当前状态 |
| --- | --- |
| 默认 project 和 schema | 已实现 |
| canonical strings 查询 | 已实现 |
| import batch | 已实现 |
| dev import | 已实现 |
| candidate release | 已实现 |
| rel active hotfix | 已实现 |
| rel passive hotfix | 已实现 |
| promote preview / execute | 已实现 |
| soft delete / restore | 已实现 |
| fill | 已实现 |
| qa | 已实现 |
| jobs / reports / artifact | 已实现 |

## 6. 当前限制

以下属于当前版本的明确边界：
- 只有一个默认 project，没有 project CRUD
- 没有 schema 编辑 API，schema 由初始化数据提供
- 导入入口是本地目录，不是上传流
- 没有独立的 `GET /api/rel/strings` endpoint；当前通过 `GET /api/state` 看摘要，通过 `GET /api/strings` 看全量 memberships
- 没有垃圾桶自动 purge 调度和独立 purge API
- workbench 是单页验证台，不是正式多页面产品
