# Momo TMS 能力与 API 对齐总表

> 用途：作为三线生命周期、project schema、当前 API、实现状态与缺口的单点索引。
> 口径：`目标能力 -> 当前 endpoint -> 当前状态 -> 差距/备注`

状态说明：
- `已对齐`：目标能力与当前 API/实现基本一致
- `部分对齐`：已有能力，但接口层次、返回形态或开放方式还不完整
- `未对齐`：目标能力已定义，但当前没有可用 API/实现
- `验证层`：当前可用，但主要通过 workbench API 提供，不等于正式公共 API

## 1. 三线状态与生命周期总览

| 能力 | 目标说明 | 当前 endpoint | 当前状态 | 差距 / 备注 |
| --- | --- | --- | --- | --- |
| 查看当前 `dev / release / master` 线头 | 获取三线当前有效状态，而不是仅看某个 snapshot | `GET /api/workbench/state` | 已对齐（验证层） | 当前缺少正式公共 branch heads API |
| 重置演示环境 | 恢复固定样例与三线初始状态 | `POST /api/demo/reset` | 已对齐（验证层） | 只服务当前 workbench 验证，不属于正式产品 API |
| 查看 jobs 列表与详情 | 统一查看生命周期动作 summary/report/artifact | `GET /api/jobs` `GET /api/jobs/{job_id}` `GET /api/jobs/{job_id}/report` `GET /api/jobs/{job_id}/artifact/{name}` | 已对齐（验证层） | 审计字段仍不完整，缺操作人、trace id |

## 2. Project Schema 与表结构

| 能力 | 目标说明 | 当前 endpoint | 当前状态 | 差距 / 备注 |
| --- | --- | --- | --- | --- |
| 定义 project 级 sheet schema | 每个 project 拥有自己的固定列、语言列、备注列与版本列配置 | 无 | 未对齐 | 当前只有文档契约，无数据模型/API |
| 模板创建 project | 通过预置模板生成 schema | 无 | 未对齐 | 当前未实现 |
| 自定义语言列 | 建项时自定义翻译语言列数量、顺序、列名 | 无 | 未对齐 | 当前实现仍偏固定列假设 |
| 自定义备注列 | 建项时自定义备注列数量、顺序、字段名 | 无 | 未对齐 | 当前实现仍偏样例驱动 |
| 业务列与系统字段分层 | `文件名/key/source` 属于业务列；`uploaded_at/branch/snapshot_id` 属于系统字段 | 无统一 endpoint | 部分对齐 | 当前概念上已分层，但没有正式 project schema / metadata API |

## 3. Dev 线能力

| 能力 | 目标说明 | 当前 endpoint | 当前状态 | 差距 / 备注 |
| --- | --- | --- | --- | --- |
| Import files | 接收 Excel 文件集合并形成 import batch | `POST /import` `POST /api/workbench/import` | 部分对齐 | 基础 API 只做导入；workbench 版本是样例驱动 |
| 查询导入异常报告 | 查看 `missing_key` / `missing_source` 等问题 | `GET /import/{import_batch_id}/report` | 已对齐 | 当前是基础问题定位接口 |
| Update Dev from files | 将导入内容写回 dev，形成新的 `dev_last` | `POST /update/dev` `POST /api/workbench/update-dev` | 部分对齐 | workbench 已有 job/report；基础 API 仍是轻量接口 |
| Dev 直接单条编辑 | 可选能力，不是当前主线 | 无 | 未对齐 | 当前未实现，也未纳入本轮主链路 |

## 4. Release 线能力

| 能力 | 目标说明 | 当前 endpoint | 当前状态 | 差距 / 备注 |
| --- | --- | --- | --- | --- |
| Active hotfix | `source` 不变，仅更新指定语言 target | `POST /update/release/active_single` `POST /api/workbench/hotfix/active` | 部分对齐 | workbench 已满足验证；基础 API 无 report/job |
| Passive hotfix | 更新 `source` 与多语言 target，可新增 key | `POST /update/release/passive_single` `POST /api/workbench/hotfix/passive` | 部分对齐 | 同上 |
| Promote preview | 在不修改 release 的前提下计算 added/conflict/carried/deprecated | `POST /api/workbench/promote/preview` | 已对齐（验证层） | 基础 API 未提供 preview |
| Promote execute | 从 `dev_last` 生成新的 release | `POST /promote` `POST /api/workbench/promote/execute` | 部分对齐 | 基础 `/promote` 仍是单步接口；workbench 才是 preview+execute 闭环 |

## 5. Master 线能力

| 能力 | 目标说明 | 当前 endpoint | 当前状态 | 差距 / 备注 |
| --- | --- | --- | --- | --- |
| Archive release -> master | 将当前 release 沉淀为新的 master 快照 | `POST /api/workbench/archive` | 已对齐（验证层） | 当前未暴露基础公共 API |
| Delete keys on master | 允许受控删除 | `POST /api/workbench/delete` | 部分对齐 | 目前通过统一 delete endpoint 支持；权限控制仍是文档约束 |
| Master 作为 fill fallback 基线 | 在 release 不命中时作为兜底 | `POST /fill` `POST /api/workbench/fill` | 已对齐 | 当前 fill 行为已按 `release > master` 执行 |

## 6. 跨线动作与受控变更

| 能力 | 目标说明 | 当前 endpoint | 当前状态 | 差距 / 备注 |
| --- | --- | --- | --- | --- |
| Delete keys | 手动提供 key 清单，从目标线删除并产出报告 | `POST /api/workbench/delete` | 已对齐（验证层） | 当前无 delete preview；正式权限模型未落地 |
| Snapshot 底层创建 | 提供快照创建基础能力 | `POST /snapshot` | 已对齐（底层能力） | 偏底层接口，不是业务动作入口 |
| 统一 job/report 产物 | 所有关键变更动作可回查 | `GET /api/jobs*` + workbench 变更动作 | 已对齐（验证层） | 基础 API 层尚未完全统一到 job 模型 |
| 系统元数据回查 | 可查看 `snapshot_id/branch/uploaded_at/updated_at` 等上下文 | 无统一 endpoint | 部分对齐 | 当前只有 jobs/import/snapshot 分散承载，未形成统一 contract API |

## 7. 导出与验证能力

| 能力 | 目标说明 | 当前 endpoint | 当前状态 | 差距 / 备注 |
| --- | --- | --- | --- | --- |
| Fill from base | 使用 `release > master` 回填译文并导出 zip | `POST /fill` `POST /api/workbench/fill` | 部分对齐 | workbench 当前是样例驱动；正式上传流程未做 |
| QA report | 校验 `{}`、`|`、`<tag>` 等结构规则 | `POST /api/workbench/qa` | 已对齐（验证层） | 基础 API 未暴露 QA endpoint |
| 下载导出 artifact | 获取 fill 导出包等结果 | `GET /api/jobs/{job_id}/artifact/{name}` | 已对齐（验证层） | 依赖 jobs 体系 |

## 8. 目标能力但当前未对齐

| 能力 | 目标说明 | 当前 endpoint | 当前状态 | 差距 / 备注 |
| --- | --- | --- | --- | --- |
| Untranslated report | 统计未翻译项并定位到文件/行 | 无 | 未对齐 | 目标已定义，尚未实现 |
| Diff / Delta report | 比较 snapshot 或 batch 差异 | 无 | 未对齐 | 尚未实现 |
| Conflict report | 独立输出 `same key + different source` 冲突清单 | 无 | 未对齐 | 当前只有 promote/archive 内部冲突规则 |
| Package validation | 检查列缺失、target 列不可写、表头异常 | 无 | 未对齐 | 尚未实现 |
| Delete preview | 删除前先做影响预览 | 无 | 未对齐 | 尚未实现 |
| Project / Schema / Template API | 项目、schema、模板的正式管理接口 | 无 | 未对齐 | 目前只有文档契约 |

## 9. 当前对齐结论

### 9.1 已基本打通的主链路
当前代码与 API 已支持以下闭环：

`import -> update dev -> promote preview -> promote execute -> release hotfix -> archive -> delete -> fill -> qa -> jobs/report`

### 9.2 仍需继续收敛的点
- 正式公共 API 与 workbench API 仍是双轨
- branch heads 仍缺单独公共查询接口
- project schema / system metadata 还没有持久化模型和 API
- 预处理 / 报告类扩展能力还没有实现
- 权限、审计主体、错误码、trace id 仍缺失

### 9.3 建议用法
- 讨论产品边界时，看 `PROJECT_REQUIREMENTS.md`
- 讨论数据模型和系统分层时，看 `PROJECT_SCHEMA_CONTRACT.md` 与 `ARCHITECTURE_DESIGN.md`
- 快速检查能力是否已经对上 API，就看本表
