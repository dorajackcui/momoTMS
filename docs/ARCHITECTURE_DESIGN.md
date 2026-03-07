# Momo TMS 架构设计

> 本文档描述当前系统如何实现 `canonical strings + memberships + trash` 模型。

## 1. 运行架构

当前系统由四层组成：
- SQLite 数据层
- FastAPI API 层
- 服务层
- 单页 workbench 验证层

核心数据流：

`Excel directory -> import batch -> dev import / rel hotfix / promote / trash -> jobs & reports -> fill / qa`

## 2. 数据模型

### 2.1 核心表

| 表 | 作用 |
| --- | --- |
| `projects` | project 基础信息 |
| `project_schemas` | fixed columns、translation columns、remark columns |
| `strings` | canonical string 主表 |
| `string_translations` | 各语言译文 |
| `string_remarks` | 备注列内容 |
| `dev_versions` | 开发版本与版本线 |
| `string_memberships` | `rel` / `dev` memberships |
| `imports` | 导入批次 |
| `import_rows` | 导入行级解析结果 |
| `jobs` | 异步动作的执行记录、报告和 artifact 索引 |

### 2.2 `strings`

当前核心字段：
- `string_id`
- `project_id`
- `business_key`
- `file_name`
- `source`
- `deleted_at`
- `trash_until`
- `restored_at`
- `created_at`
- `updated_at`

约束：
- `(project_id, business_key)` 唯一
- `master` 不单独落库；`deleted_at IS NULL` 的 strings 即属于隐式全集

### 2.3 `string_memberships`

当前字段：
- `string_id`
- `membership_type`
- `membership_value`
- `created_at`

当前约定：
- `rel/current`
- `dev/<version>`

### 2.4 `dev_versions`

当前字段：
- `project_id`
- `version`
- `version_line`
- `is_candidate_release`
- `created_at`
- `promoted_at`

实现含义：
- `version_line` 用来做 promote 后的整线清理
- `promoted_at IS NULL` 的版本视为运行时活跃 dev versions

## 3. 服务层

### 3.1 `ProjectService`

职责：
- 读取默认 project
- 读取 schema
- 按 schema 解析 Excel 表头
- 校验语言列是否受支持

### 3.2 `StringService`

职责：
- 查询 strings
- 创建和更新 canonical string
- 维护 translations 和 remarks
- 维护 memberships
- 执行 soft delete / restore
- 统计 trash 数量

### 3.3 `ImportService`

职责：
- 扫描本地目录中的 `.xlsx`
- 按 schema 解析 sheet 和行
- 写入 `imports` / `import_rows`
- 生成 parse report

### 3.4 `DevVersionService`

职责：
- 创建或更新 `dev_version`
- 执行 dev import 规则
- 标记 candidate release
- 查询 dev version 列表和成员

### 3.5 `RelService`

职责：
- 汇总当前 `rel`
- 执行 active hotfix
- 执行 passive hotfix

### 3.6 `PromoteService`

职责：
- 预览 `dev_version -> rel` 的集合变化
- 清空旧 `rel` memberships
- 将目标 `dev_version` 集合打成新的 `rel`
- 清理同一 `version_line` 下的 `dev` memberships
- 将同一版本线标记为 `promoted`

### 3.7 `TrashService`

职责：
- 将 canonical string 送入垃圾桶
- 从垃圾桶恢复 string
- 生成删除与恢复报告

### 3.8 `FillService` / `QaScanService`

`FillService`：
- 按 schema 读取输入 Excel
- 回填指定语言列
- 对 `source` 不一致行生成 `SRC_MISMATCH`
- 输出 zip artifact

`QaScanService`：
- 按 schema 读取目标语言列
- 使用 `qa_service` 做规则校验
- 输出问题报告

### 3.9 `WorkbenchService`

职责：
- 统一编排 import、dev import、hotfix、promote、trash、fill、qa
- 将每个动作包装成 `job`
- 为 workbench 提供统一状态摘要

## 4. API 形态

当前系统只有一套 `/api/*` 接口。

状态与查询：
- `GET /api/state`
- `GET /api/strings`
- `GET /api/strings/{business_key}`
- `GET /api/imports`
- `GET /api/imports/{import_batch_id}/report`
- `GET /api/dev-versions`
- `GET /api/dev-versions/{version}`
- `GET /api/jobs`
- `GET /api/jobs/{job_id}`
- `GET /api/jobs/{job_id}/report`
- `GET /api/jobs/{job_id}/artifact/{name}`

动作：
- `POST /api/demo/reset`
- `POST /api/imports/directory`
- `POST /api/dev-versions/import`
- `POST /api/rel/hotfix/active`
- `POST /api/rel/hotfix/passive`
- `POST /api/promote/preview`
- `POST /api/promote/execute`
- `POST /api/trash/delete`
- `POST /api/trash/restore`
- `POST /api/fill`
- `POST /api/qa`

## 5. 当前实现约束

- 单默认 project，尚未扩展到多 project runtime
- schema 持久化已存在，但暂无 schema 编辑接口
- import 基于本地目录，不支持上传流
- `rel` 只有摘要接口，没有独立列表接口
- 没有自动 purge 调度
- workbench 用于验证主流程，不承担完整产品管理 UI

## 6. 兼容性说明

当前代码已经移除旧 `snapshot / branch_heads / archive / delete-by-branch` 主链。

这意味着：
- 不做旧数据库迁移兼容
- 不保留旧 API 兼容层
- 历史残留只在重建 schema 时被清理，不再参与运行时逻辑
