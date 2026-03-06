# Momo TMS 当前系统设计说明

> 当前文档口径：描述代码已经落地的设计，同时用“目标动作 -> 当前 API -> 差距”方式对齐产品需求。

## 1. 总体架构

项目采用轻量 FastAPI + SQLite + 本地文件系统架构，围绕三线生命周期构建：

- API 层：`app/main.py`
  - 基础 API：保留原始后端能力
  - workbench API：面向当前验证工作台的编排层接口
- 服务层：`app/services/*`
  - 基础服务：import、snapshot、update、promote、fill、qa
  - 生命周期编排：workbench、archive、delete、branch、job、demo fixture
- 数据层：`app/db.py`
  - SQLite 初始化、连接与核心表结构
- 静态前端：`app/static/*`
  - 单页 workbench，用于验证生命周期主链路

核心数据流：

`Excel -> import rows -> entries/translations -> snapshot -> branch head -> report/job/artifact`

## 2. 核心数据模型

### 2.1 基础业务实体

| 实体 | 作用 |
| --- | --- |
| `entries` | 源文语义实体，记录 `key / src / src_hash / version_tag` |
| `translations` | 每个 `entry_id + lang` 的译文 |
| `snapshots` | 快照节点，记录 `branch`、`parent`、`action_type`、`meta` |
| `snapshot_items` | 快照内部 `key -> entry_id + src_hash` 映射 |
| `imports` / `import_rows` | 导入批次与行级问题定位 |

### 2.2 状态与审计实体

| 实体 | 作用 |
| --- | --- |
| `branch_heads` | 定义 `dev / release / master` 当前有效线头 |
| `jobs` | 记录生命周期动作的输入摘要、summary、report、artifact、snapshot、状态 |

### 2.3 目标中的 project schema 实体

以下能力已经在需求文档中确定，但当前代码尚未落地：

| 目标实体 | 作用 | 当前状态 |
| --- | --- | --- |
| `projects` | 项目实体 | 未实现 |
| `project_schemas` | 记录固定列、语言列、备注列、版本列开关 | 未实现 |
| `schema_templates` | 预置模板 | 未实现 |

建议最小模型：

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

### 2.4 关键设计含义
- `snapshot` 是版本节点，不等于当前线状态。
- `branch_heads` 决定当前 `dev_last / current_release / current_master`。
- 变更型动作通过 job 编排执行，并在成功后更新对应 head。
- 业务 Excel 列与系统元数据字段必须分层建模。

## 3. Business Sheet 与 System Metadata

### 3.1 Business Sheet Contract

根据当前需求，`master` 表应理解为 project 级业务表契约：

| 类型 | 字段 |
| --- | --- |
| 固定业务列 | `文件名`、`key`、`source` |
| 标准可选列 | `版本号` |
| 可配置翻译语言列 | `translation_columns[]` |
| 可配置备注列 | `metadata_columns[]` |

架构含义：
- import、fill、qa 后续都不应依赖固定列号。
- 解析器应基于 project schema 读取 Excel。
- `文件名 + key` 推荐作为业务主键；`source` 用于冲突判断。

### 3.2 System Metadata Contract

以下字段需要在系统中有清晰归属，但默认不属于 Excel 业务列：

| 字段 | 建议归属 |
| --- | --- |
| `project_id` / `schema_id` | project context |
| `import_batch_id` | import |
| `snapshot_id` | snapshot context |
| `branch` | branch head context |
| `uploaded_at` / `updated_at` | row/job audit |
| `source_file_path` / `sheet_name` / `row_index` | import row metadata |
| `job_id` | job audit |

关键说明：
- `当前所属 dev/release/master` 应由 `snapshot_id + branch_heads` 推导，不应设计成 Excel 常驻列。
- `上传时间` 与 `最近修改时间` 应由数据库/API 管理。

详细契约见 [PROJECT_SCHEMA_CONTRACT.md](./PROJECT_SCHEMA_CONTRACT.md)。

## 4. 三线状态管理

### 4.1 三线状态的真实来源
- `dev` 当前状态：`branch_heads.dev`
- `release` 当前状态：`branch_heads.release`
- `master` 当前状态：`branch_heads.master`

当前 workbench `GET /api/workbench/state` 返回：
- 各 branch 当前 `snapshot_id`
- `action_type`
- `created_at`
- `parent_snapshot_id`
- `key_count`
- `meta`

### 4.2 生命周期动作的统一编排方式

以下动作当前都通过 `WorkbenchService` 统一包装为同步 job：
- `update dev`
- `active hotfix`
- `passive hotfix`
- `promote execute`
- `archive`
- `delete keys`
- `fill`
- `qa`

统一行为：
- 生成 job 记录
- 执行业务服务
- 成功后写入 report / artifact / snapshot_id
- 更新对应 `branch_heads`

## 5. 生命周期动作与服务映射

| 产品动作 | 当前服务 | 当前 endpoint | 当前输出 |
| --- | --- | --- | --- |
| Import files | `ImportService` | `POST /import`、`POST /api/workbench/import` | import batch、导入问题列表 |
| Update Dev from files | `UpdateService.update_dev_from_directory` | `POST /update/dev`、`POST /api/workbench/update-dev` | 新 snapshot；workbench 额外返回 job/report |
| Active hotfix | `UpdateService.update_release_active_single` | `POST /update/release/active_single`、`POST /api/workbench/hotfix/active` | 新 release snapshot；workbench 额外返回 job/report |
| Passive hotfix | `UpdateService.update_release_passive_single` | `POST /update/release/passive_single`、`POST /api/workbench/hotfix/passive` | 新 release snapshot；workbench 额外返回 job/report |
| Promote preview | `PromoteService.preview` | `POST /api/workbench/promote/preview` | preview summary + report rows |
| Promote execute | `PromoteService.promote` | `POST /promote`、`POST /api/workbench/promote/execute` | 新 release snapshot；workbench 额外返回 job/report |
| Archive release -> master | `ArchiveService.archive` | `POST /api/workbench/archive` | 新 master snapshot + archive report |
| Delete keys | `DeleteService.delete_keys` | `POST /api/workbench/delete` | 新 snapshot + delete report |
| Fill from base | `FillService.fill_and_export` | `POST /fill`、`POST /api/workbench/fill` | fill report + zip artifact |
| QA report | `QaScanService.scan_directory` | `POST /api/workbench/qa` | qa report |

## 6. API 对齐表

### 6.1 基础 API

| 目标动作 | 当前 endpoint | 当前 response 形态 | 是否满足产品预期 | 备注 |
| --- | --- | --- | --- | --- |
| 导入批次 | `POST /import` | `import_batch_id/files_scanned/rows_scanned/issues` | 部分满足 | 缺少统一 job/audit 包装 |
| 导入异常报告 | `GET /import/{id}/report` | 行级异常列表 | 满足 | 用于基础问题定位 |
| 创建快照 | `POST /snapshot` | `snapshot_id/branch/action_type` | 满足底层能力 | 偏底层，不是业务动作 API |
| Dev 批量写回 | `POST /update/dev` | `{snapshot_id}` | 部分满足 | 参数仍是 query 风格，report 不统一 |
| Release active hotfix | `POST /update/release/active_single` | `{snapshot_id}` | 部分满足 | 缺少 report/job |
| Release passive hotfix | `POST /update/release/passive_single` | `{snapshot_id}` | 部分满足 | 缺少 report/job |
| Promote execute | `POST /promote` | promote summary + `snapshot_id` | 部分满足 | 没有 preview 分离 |
| Fill/export | `POST /fill` | fill summary + report path | 部分满足 | 更像底层执行接口 |

### 6.2 Workbench API

| 目标动作 | 当前 endpoint | 当前 response 形态 | 是否满足产品预期 | 备注 |
| --- | --- | --- | --- | --- |
| 查看三线状态 | `GET /api/workbench/state` | branches + samples + imports + jobs | 满足当前验证需求 | 主要服务单页 workbench |
| Reset demo | `POST /api/demo/reset` | 完整 workbench state | 满足验证需求 | 不是正式产品 API |
| Import sample | `POST /api/workbench/import` | import summary + issues | 满足验证需求 | 当前基于样例目录 |
| Update dev | `POST /api/workbench/update-dev` | `JobDetail` | 基本满足 | 已有 snapshot/report/job |
| Active hotfix | `POST /api/workbench/hotfix/active` | `JobDetail` | 基本满足 | 已更新 branch head |
| Passive hotfix | `POST /api/workbench/hotfix/passive` | `JobDetail` | 基本满足 | 已更新 branch head |
| Promote preview | `POST /api/workbench/promote/preview` | `PromotePreview` | 满足 | 已与 execute 拆分 |
| Promote execute | `POST /api/workbench/promote/execute` | `JobDetail` | 满足 | 已更新 release head |
| Archive | `POST /api/workbench/archive` | `JobDetail` | 满足 | 已更新 master head |
| Delete keys | `POST /api/workbench/delete` | `JobDetail` | 满足 | 当前无 delete preview |
| Fill | `POST /api/workbench/fill` | `JobDetail` | 满足验证需求 | 产物通过 jobs artifact 下载 |
| QA | `POST /api/workbench/qa` | `JobDetail` | 满足验证需求 | 当前为目录扫描模式 |
| Jobs 列表/详情 | `GET /api/jobs*` | `JobSummary / JobDetail / ReportPayload` | 满足 | 已形成统一查看入口 |

## 7. 两层 API 的边界

### 7.1 基础 API 的角色
基础 API 更接近底层后端能力，特点是：
- 简单直接
- 返回结构轻量
- 适合脚本或后续二次封装
- 不保证每个动作都有完整 report/job 体验

### 7.2 Workbench API 的角色
workbench API 更接近当前产品验证层，特点是：
- 面向单页验证工作台
- 强调 `snapshot + report + job`
- 包含样例 reset、branch heads、jobs、artifact 下载
- 当前可用，但不等于最终正式公共 API 设计

## 8. demo / sample fixture 设计

当前 workbench 通过 `DemoService` 动态生成样例 Excel 和初始数据，覆盖以下典型场景：
- `promote added`
- `promote conflict_keep_release`
- `promote deprecated`
- `fill missing`
- `fill src mismatch`
- `qa error`
- `delete hit`
- `delete miss`

这样做的目的：
- 保证 E2E 可重复
- 降低手工准备样例成本
- 固定生命周期验证路径

## 9. 当前实现与目标能力的差距

以下产品动作在能力矩阵里是目标项，但当前尚未落地为可用 API：
- untranslated report
- diff / delta report
- conflict report
- package validation
- delete preview

以下能力当前只存在于验证层，不宜误写成“已形成正式产品 API”：
- sample-based import/update/fill/qa
- demo reset
- 单页 workbench orchestration

以下能力已经在需求层明确，但代码尚未实现：
- `project / schema / template` 持久化能力
- 按 project schema 解析 Excel，而不是依赖固定列结构
- 把 `uploaded_at / updated_at / branch` 等系统字段纳入正式 API 模型

## 10. 当前设计取舍

- **优先三线生命周期清晰**：先明确 branch head 和版本流转，而不是先做复杂前端。
- **优先规则可解释**：promote、archive、delete、fill 规则都显式编码，方便审计和写测试。
- **优先验证闭环**：单页 workbench + demo fixture + E2E 比先做完整产品 IA 更适合现阶段。
- **接受两层 API 共存**：基础 API 与 workbench API 并存，是当前阶段有意设计，不是 accidental duplication。
- **暂不提前实现 project schema 持久化**：先用文档把契约定义清楚，再决定数据模型和迁移方案。
