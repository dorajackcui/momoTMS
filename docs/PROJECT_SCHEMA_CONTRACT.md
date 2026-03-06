# Momo TMS Project Schema Contract

> 用途：定义项目级 Excel 业务表结构，以及不进入 Excel 业务列的系统元数据字段。
> 口径：先区分“业务字段”和“系统字段”，再讨论三线流转、导入、回填、QA 和 API。

## 1. 设计原则

### 1.1 分层原则
- Excel `master` 表只承载业务字段。
- 上传时间、最近修改时间、当前所属线等系统字段必须定义，但不作为业务同学维护的 Excel 列。
- 三线 `dev / release / master` 是 snapshot 上下文，不是业务表中的常驻列。

### 1.2 Project 级 Schema
- 每个 `project` 都有自己的 `sheet schema contract`。
- `翻译语言列` 和 `备注列` 在创建 project 时可自定义。
- 系统提供两种创建方式：
  - `template-based`：使用固定模板快速创建。
  - `custom`：手动定义语言列、备注列、顺序和是否启用版本列。

### 1.3 模板不是另一套逻辑
- 模板只是 `project schema` 的预设。
- 无论模板还是自定义，导入、回填、QA、promote、archive 的解析逻辑都应基于同一份 schema。

## 2. Business Sheet Contract

### 2.1 固定业务列
以下列在所有 project 中都存在，且语义固定：

| 列名 | 是否必填 | 说明 |
| --- | --- | --- |
| `文件名` | 是 | 业务来源文件名；用于定位条目所属文件与回填目标。 |
| `key` | 是 | 业务 key。 |
| `source` | 是 | 源文，当前默认是中文。 |

### 2.2 标准可选列
以下列建议作为标准列，但允许按 project schema 配置：

| 列名 | 是否默认启用 | 说明 |
| --- | --- | --- |
| `版本号` | 是 | 业务版本标记；用于识别条目版本归属。是否必填由 project schema 决定。 |

### 2.3 可配置翻译语言列
- `translation_columns[]` 由 project 创建时定义。
- 列数量可变，顺序可变，列名也由 project schema 决定。
- 推荐使用稳定语言代码，例如 `en`, `ja`, `ko`, `fr`，但展示名可配置。

示例：

| 列顺序 | 业务列名 |
| --- | --- |
| 4 | `en` |
| 5 | `ja` |
| 6 | `ko` |
| 7 | `fr` |

### 2.4 可配置备注列
- `metadata_columns[]` 由 project 创建时定义。
- 备注列数量可变，顺序可变。
- 备注列可以是标准模板字段，也可以是项目自定义字段。

常见示例：
- `speaker`
- `tips`
- `context`
- `scene`
- `ui_location`

### 2.5 业务主键与冲突语义
- 推荐业务主键：`文件名 + key`
- `source` 不是主键的一部分，但参与冲突判断。
- 对同一 `文件名 + key`：
  - 若 `source` 相同：视为同一语义条目，可更新译文或备注信息。
  - 若 `source` 不同：视为语义冲突，后续由 promote/archive/hotfix 规则决定如何处理。

### 2.6 逻辑示例

```text
文件名 | key | source | en | ja | ko | 版本号 | speaker | tips
story_01.xlsx | hero.greet | 你好 | Hello | こんにちは | 안녕 | v1 | Hero | 首次见面
```

## 3. System Metadata Contract

### 3.1 系统字段与业务字段分离
以下字段必须在系统中有清晰定义，但不要求出现在 Excel `master` 业务表里：

| 字段 | 含义 | 建议归属 |
| --- | --- | --- |
| `project_id` | 所属项目 | project / API context |
| `schema_id` | 所属 schema 版本 | project schema |
| `import_batch_id` | 导入批次 | import |
| `snapshot_id` | 当前条目所在快照 | snapshot context |
| `branch` | 当前快照所属线：`dev/release/master` | branch head context |
| `uploaded_at` | 首次导入时间 | import/job audit |
| `updated_at` | 最近一次系统修改时间 | row/job audit |
| `source_file_path` | 原始文件路径 | import row metadata |
| `sheet_name` | 原始 sheet 名 | import row metadata |
| `row_index` | 原始行号 | import row metadata |
| `job_id` | 最近一次变更 job | job audit |
| `created_by` / `updated_by` | 操作人 | future audit |

### 3.2 关于“当前所属线”
- `当前所属 dev/release/master` 需要规定，但不应设计成 Excel 业务列。
- 原因：同一个业务条目可以在多个 snapshot 中同时存在，线归属是版本上下文，不是静态业务属性。
- 系统应通过 `snapshot_id + branch_heads` 推导当前有效线头。

### 3.3 关于时间字段
- `上传时间`：建议定义为 import 批次或首次入库时间。
- `最近修改时间`：建议定义为最近一次改变该条目快照归属或内容的系统时间。
- 这两个字段应通过数据库/API 暴露，而不是要求业务同学回填 Excel。

## 4. Project Creation Contract

### 4.1 创建方式
- `从模板创建`
  - 选择预置语言列和备注列集合。
- `自定义创建`
  - 自定义语言列、备注列、显示名、顺序，以及是否启用版本列。

### 4.2 最小 project schema 建议

```text
project
  id
  name
  schema_id

project_schema
  id
  fixed_columns = [file_name, key, source]
  version_enabled = true/false
  translation_columns[]
  metadata_columns[]
  template_id(optional)
```

### 4.3 模板示例
- `8-language template`
- `4-language lightweight template`
- `narrative/game script template`

## 5. 对三线生命周期的影响

- `import / update dev` 不能再依赖固定列号，必须按 project schema 解析 Excel。
- `fill` 只能回填 project schema 中声明的翻译语言列，不能猜测列位置。
- `qa` 要能带着 `file_name / sheet_name / row_index / key / lang` 返回问题。
- `promote / archive / delete` 主要作用于 snapshot 和 branch head，不直接依赖 Excel 列顺序，但报告需要能回溯到 project schema 中的字段名。

## 6. 当前实现对齐结论

| 项目 | 当前状态 | 备注 |
| --- | --- | --- |
| 三线与 snapshot / branch head 的区分 | 已对齐 | 当前代码已通过 `branch_heads` 建模。 |
| 业务表结构固定为 project 级 schema | 未对齐 | 当前实现仍偏向固定列假设和样例驱动。 |
| 系统字段与 Excel 业务列分离 | 部分对齐 | 概念上已存在 `jobs/import/snapshot`，但尚未形成正式 project schema 模型。 |
| 模板创建 project | 未对齐 | 当前无 `project/schema/template` 持久化能力。 |

## 7. 后续文档和实现约束

1. 所有后续需求文档都应把 `master 表结构` 表述为 `project-level sheet contract`，而不是全局固定 12 列。
2. 所有系统字段都应落在 `System Metadata Contract`，不要再混写成 Excel 列。
3. `当前所属线`、`上传时间`、`最近修改时间` 等字段必须出现在 API / 数据模型设计里，但默认不出现在业务维护表中。
