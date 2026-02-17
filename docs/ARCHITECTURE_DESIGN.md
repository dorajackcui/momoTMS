# Momo TMS 设计说明

## 1. 总体架构
项目采用轻量后端分层：
- **API 层**：`app/main.py` 暴露 FastAPI 路由。
- **服务层**：`app/services/*` 封装导入、快照、更新、promote、fill、QA 规则。
- **数据层**：`app/db.py` 管理 SQLite 初始化与连接。

数据流核心：Excel 文件 -> 结构化 entry/translation -> snapshot 映射 -> 回填导出。

## 2. 数据模型设计

### 2.1 核心实体
- `entries`：源文语义实体（key/src/src_hash/version_tag）。
- `translations`：按 `(entry_id, lang)` 存储目标文。
- `snapshots`：版本快照节点（支持 parent 指针）。
- `snapshot_items`：快照中的 key 映射到具体 entry。
- `imports` / `import_rows`：导入批次与行级问题追踪。

### 2.2 关键约束
- `translations` 以 `(entry_id, lang)` 为主键，保证每语言唯一。
- `snapshot_items` 以 `(snapshot_id, key)` 为主键，保证快照内 key 唯一映射。
- `entries` 上有 `(key, src_hash)` 索引，加速去重与查询。

## 3. 核心流程设计

### 3.1 Import
1. 扫描目录下 `.xlsx` 文件。
2. 逐行检查 key/src。
3. 将问题行写入 `import_rows`。
4. 返回批次统计结果。

### 3.2 Snapshot + Update
- 创建新快照并可复制父快照 item。
- 读取 Excel 行并执行：
  - `_upsert_entry(key, src, version_tag)`
  - `_upsert_translation(entry_id, lang, tgt)`
  - `set_item(snapshot_id, key, entry_id, src_hash)`

### 3.3 Promote
- 输入：`dev_last` 与当前 `release`。
- 逐 key 按规则合并：
  - src 冲突：保留旧 release。
  - 无冲突：使用 dev 条目。
- 输出：新 release 快照 + 统计报告。

### 3.4 Fill
- 预构建 `release_map` 与 `master_map`。
- 遍历 Excel：按 `release > master` 找候选。
- 命中后仅在 `src_hash` 一致时写 target 列。
- 产出：回填后的 Excel、CSV 报告、zip 包。

### 3.5 QA
- 规则函数对 src/tgt 对进行结构完整性检查。
- 当前输出为规则结果列表（rule + ok）。

## 4. API 设计概览
- `POST /import`
- `GET /import/{id}/report`
- `POST /snapshot`
- `POST /update/dev`
- `POST /update/release/active_single`
- `POST /update/release/passive_single`
- `POST /promote`
- `POST /fill`

## 5. 当前设计取舍
- **优先可落地**：SQLite + 本地文件系统，开发门槛低。
- **优先规则可解释**：promote/fill 规则显式编码，便于审计。
- **优先稳定性**：对 key/src_hash 建立一致性约束，降低误回填概率。

## 6. 后续演进建议
- 增加 API 层的请求参数统一建模（特别是 `/update/dev`）。
- 引入 migration 工具（如 Alembic）管理 DB 版本。
- 增补 fill 与 update 流程单测，覆盖更多异常场景。
- 增加可视化界面与操作审计日志。
