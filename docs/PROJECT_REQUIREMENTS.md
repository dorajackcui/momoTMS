# Momo TMS 项目需求说明（MVP）

## 1. 项目背景与目标
Momo TMS 是一个面向 **Windows Excel 本地化流程** 的翻译管理系统原型，目标是用最小可行方案（MVP）打通从导入、版本演进到回填与质检的核心链路。

核心目标：
- 降低 Excel 多语言项目的人肉比对和回填成本。
- 对翻译数据建立可追溯的快照版本机制。
- 在 dev / release / master 分支语义下稳定推进版本。

## 2. 业务范围（In Scope）
当前 MVP 覆盖如下能力：
- 批量导入：扫描目录中的 `.xlsx` 文件并记录问题行。
- 快照管理：支持 `dev` / `release` / `master` 分支快照创建与继承。
- Dev 更新：从目录导入最新内容并更新 dev 快照。
- Release 单条更新：
  - active_single：仅改 target 文案。
  - passive_single：可更新 src 与多语言 target。
- Promote：从 `dev_last` 生成新 release，且 src 冲突时保留旧 release。
- Fill：将 release（可回退 master）翻译写回 Excel，仅写 target 列。
- QA 基础规则：占位符 `{}`、分隔符 `|`、标签 `<tag>` 结构校验。

## 3. 非目标（Out of Scope）
当前版本暂不覆盖：
- Web 前端与可视化报表。
- 复杂权限模型与审计工作流。
- 在线协作、任务分发、翻译供应商协同。
- 大规模并行处理和性能调优。

## 4. 功能性需求

### 4.1 导入与报表
- 系统应支持按目录递归扫描 `.xlsx` 文件（忽略临时文件 `~$` 前缀）。
- 每行以 `key`（第1列）与 `src`（第2列）作为基础结构校验。
- 对 `missing_key` 与 `missing_src` 问题进行记录。
- 可按 `import_batch_id` 查询导入异常报告。

### 4.2 快照与分支
- 快照应支持分支标识、父快照指针、动作类型、元数据。
- 新快照可复制父快照内容并增量修改。
- 快照项应保存 `key -> entry_id + src_hash` 映射。

### 4.3 更新策略
- dev 更新采用目录导入 + 快照增量覆盖（LWW 语义）。
- release active_single 仅更新指定 key 的指定语言 target。
- release passive_single 支持替换 key 的 src 与多语言译文。

### 4.4 Promote 规则
- 目标 key 空间固定为 `Keys(dev_last)`。
- 若同 key 在 dev 与 release 的 `src_hash` 不同，判定冲突并保留旧 release 条目。
- 统计新增、冲突、沿用、废弃 key 数量。

### 4.5 Fill 规则
- 候选翻译优先级：`release > master`。
- 必须满足 `key` 命中且 `src_hash` 一致才可回填。
- 仅允许写入 target 列，不改表结构、不增删行。
- 输出填充结果统计与 CSV 报告，并打包导出 zip。

### 4.6 QA 规则
- `PLACEHOLDER_COUNT`：源文与译文 `{}` 数量一致。
- `PIPE_COUNT`：源文与译文 `|` 数量一致。
- `TAG_WELL_FORMED`：译文标签需成对且闭合顺序正确。

## 5. 非功能需求
- 数据持久化采用 SQLite，本地可运行。
- API 使用 FastAPI 提供，便于后续对接前端与自动化脚本。
- 数据模型需可追踪（snapshot 链路、导入日志、回填报告）。

## 6. 验收建议（MVP）
- 可通过 API 独立完成一条端到端流程：
  `import -> snapshot/update -> promote -> fill`。
- QA 规则具备基础自动化单测，promote 关键冲突策略具备单测。
- 输出结果可由业务同学在 Excel 中复核。
