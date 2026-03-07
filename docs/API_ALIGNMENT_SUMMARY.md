# Momo TMS 能力与 API 总表

> 本文档汇总当前已实现能力、对应 endpoint 和已知缺口。
> 口径：`能力 -> endpoint -> 当前状态 -> 备注`

状态说明：

- `已实现`：能力和接口都已可用
- `部分实现`：主能力可用，但仍缺少专门 endpoint 或管理能力
- `未实现`：当前代码中没有该能力

## 1. Project 与 Schema


| 能力                   | Endpoint         | 当前状态 | 备注                                  |
| -------------------- | ---------------- | ---- | ----------------------------------- |
| 默认 project 状态摘要      | `GET /api/state` | 已实现  | 返回默认 project 摘要                     |
| 读取 project schema 摘要 | `GET /api/state` | 已实现  | 返回 fixed/translation/remark columns |
| project CRUD         | 无                | 未实现  | 当前只有单默认 project                     |
| schema 编辑            | 无                | 未实现  | 当前 schema 由初始化数据提供                  |


## 2. Strings 与 Memberships


| 能力                     | Endpoint                          | 当前状态 | 备注                                     |
| ---------------------- | --------------------------------- | ---- | -------------------------------------- |
| 查询全部 canonical strings | `GET /api/strings`                | 已实现  | 支持搜索和 `include_deleted`                |
| 查询单条 string            | `GET /api/strings/{business_key}` | 已实现  | 返回 translations、remarks、memberships    |
| 查看 `rel` 摘要            | `GET /api/state`                  | 已实现  | 返回数量和 sample keys                      |
| 查看 `rel` 成员完整列表        | 无独立 endpoint                      | 部分实现 | 当前通过 `GET /api/strings` 查看 memberships |
| 查看 dev versions 列表     | `GET /api/dev-versions`           | 已实现  | 只返回活跃 dev versions                     |
| 查看某个 dev version 成员    | `GET /api/dev-versions/{version}` | 已实现  | 返回 members                             |


## 3. Import 与 Dev Workflow


| 能力                             | Endpoint                                    | 当前状态 | 备注                                            |
| ------------------------------ | ------------------------------------------- | ---- | --------------------------------------------- |
| 本地目录导入为 job                    | `POST /api/imports/directory`               | 已实现  | 输入目录路径，结果写入 jobs                              |
| 查看 import batches              | `GET /api/imports`                          | 已实现  | 返回批次摘要                                        |
| 查看 import report               | `GET /api/imports/{import_batch_id}/report` | 已实现  | 返回全量行级 report                                 |
| 执行 dev import                  | `POST /api/dev-versions/import`             | 已实现  | 支持 candidate release 标记                       |
| dev import 新增 string           | `POST /api/dev-versions/import`             | 已实现  | report 状态 `CREATED`                           |
| dev import 更新非 rel string      | `POST /api/dev-versions/import`             | 已实现  | report 状态 `UPDATED_CANONICAL`                 |
| dev import 对 rel string 只打 tag | `POST /api/dev-versions/import`             | 已实现  | report 状态 `TAGGED_ONLY` / `PROTECTED_SKIPPED` |


## 4. Rel 与 Promote


| 能力                   | Endpoint                       | 当前状态 | 备注                             |
| -------------------- | ------------------------------ | ---- | ------------------------------ |
| rel active hotfix    | `POST /api/rel/hotfix/active`  | 已实现  | 修改单个翻译列                        |
| rel passive hotfix   | `POST /api/rel/hotfix/passive` | 已实现  | 修改 source、translations、remarks |
| promote preview      | `POST /api/promote/preview`    | 已实现  | 返回 rel 集合变化和清理统计               |
| promote execute      | `POST /api/promote/execute`    | 已实现  | 切换 rel 并清理当前版本线 dev tags       |
| candidate release 摘要 | `GET /api/state`               | 已实现  | 返回当前 candidate dev version     |


## 5. Trash、Fill、QA、Jobs


| 能力                | Endpoint                                 | 当前状态 | 备注                                 |
| ----------------- | ---------------------------------------- | ---- | ---------------------------------- |
| soft delete 到垃圾桶  | `POST /api/trash/delete`                 | 已实现  | 作用于 canonical string               |
| 从垃圾桶恢复            | `POST /api/trash/restore`                | 已实现  | restore 后原 memberships 仍生效         |
| trash 数量摘要        | `GET /api/state`                         | 已实现  | 返回 `trash_count`                   |
| fill 并导出 artifact | `POST /api/fill`                         | 已实现  | 产出 zip artifact                    |
| qa 扫描             | `POST /api/qa`                           | 已实现  | 返回 rule counts 和行级报告               |
| jobs 列表           | `GET /api/jobs`                          | 已实现  | 统一查看 import、hotfix、promote、fill、qa |
| job 详情            | `GET /api/jobs/{job_id}`                 | 已实现  | 含 summary 和 report                 |
| job report        | `GET /api/jobs/{job_id}/report`          | 已实现  | report 单独读取                        |
| artifact 下载       | `GET /api/jobs/{job_id}/artifact/{name}` | 已实现  | 主要用于 fill 产物                       |


## 6. 当前缺口

- 没有多 project API
- 没有 schema 编辑和模板管理 API
- 没有文件上传型 import API，当前只支持目录路径
- 没有独立 `rel strings` 列表 endpoint
- 没有垃圾桶 purge API 或调度
- 没有正式的权限与审计模型

