# Momo TMS 项目进度说明

> 更新时间：以当前仓库代码、`pytest` 与 Playwright E2E 通过结果为准。

## 1. 当前阶段
- 阶段定位：**三线生命周期 MVP 已可运行，并已有验证工作台与自动化测试**。
- 当前重点：补齐文档口径，让“目标能力 / 当前实现 / API 缺口”一致。

## 2. 已完成

### 2.1 三线生命周期能力
- 已完成 `dev` 批量写回与 `dev_last` 形成。
- 已完成 `release` 的 active / passive hotfix。
- 已完成 `promote preview` 与 `promote execute`。
- 已完成 `archive release -> master`。
- 已完成 `delete keys`。
- 已完成 `fill` 与 `qa` 验证动作。

### 2.2 数据与编排能力
- 已落地核心表：`entries / translations / snapshots / snapshot_items / imports / import_rows`。
- 已落地三线状态管理：`branch_heads`。
- 已落地任务与报告管理：`jobs`。
- 已落地 demo/sample fixture，用于可重复 reset 和 E2E。

### 2.3 前端与验证
- 已完成单页 workbench，覆盖：
  - 样例 / reset
  - 三线状态
  - import / update dev
  - hotfix
  - promote preview / execute
  - archive / delete
  - fill / qa
  - jobs / reports
- 已完成后端自动化测试。
- 已完成前端 Playwright E2E。

## 3. 当前进行中
- 文档重构：统一为“目标产品能力 + 当前实现现状 + 明确缺口”口径。
- 对齐三线生命周期描述、能力矩阵、系统设计、页面设计与项目进度。

## 4. 真实待办

### 4.1 能力缺口
- 未实现 untranslated report。
- 未实现 diff / delta report。
- 未实现 conflict report。
- 未实现 package validation。
- 未实现 delete preview。

### 4.2 API 与工程化
- 基础 API 与 workbench API 仍是双轨，尚未统一。
- 缺少正式 branch heads 公共查询接口。
- 缺少统一错误码、trace id、操作主体审计字段。
- 缺少 migration 与环境分层配置。

### 4.3 产品化能力
- 当前 workbench 仍是验证页，不是最终产品 IA。
- 缺少正式上传体验与更完整的批次管理。
- 缺少权限模型与角色控制。

## 5. 当前结论
- 从“代码可运行”角度看，三线生命周期主链路已打通。
- 从“产品定义清晰”角度看，当前最重要的工作不是继续加功能，而是先把文档和 API 对齐。
- 下一阶段建议先完成文档对齐，再决定：
  - 是继续补生命周期周边报告能力
  - 还是把单页 workbench 拆向正式产品信息架构
