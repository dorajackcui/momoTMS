# 页面设计

> 本文档描述当前 workbench 的信息架构，以及后续如果拆分正式页面时的建议边界。

## 1. 当前页面形态

当前实现是一个单页 workbench：`/workbench`

它承担四类职责：
- 查看 project 状态和 strings
- 执行 import / dev import
- 执行 rel hotfix / promote / trash
- 查看 jobs、reports、fill、qa

当前 workbench 是正式可用的验收入口，不再是旧 branch/snapshot 验证页。

## 2. 当前单页 IA

### 2.1 Project Summary

展示：
- 默认 project
- schema 摘要
- 当前 rel 数量
- candidate dev version
- trash 数量

### 2.2 Project Strings

能力：
- 查看 canonical strings 列表
- 按 `business_key` / `source` / `file_name` 搜索
- 查看 memberships
- 切换是否包含垃圾桶
- 执行 delete / restore

### 2.3 Dev Versions

能力：
- 导入 sample Excel
- 查看 import batches
- 选择 import batch 执行 dev import
- 设置 `dev_version`
- 标记 candidate release
- 查看当前活跃 dev versions

### 2.4 Rel Operations

能力：
- 查看当前 rel 摘要
- active hotfix
- passive hotfix
- promote preview
- promote execute

### 2.5 Jobs & Reports

能力：
- 查看 jobs 列表
- 查看 job 详情、report rows、artifact 下载
- 运行 fill
- 运行 qa

## 3. 当前页面原则

- 页面围绕 `canonical strings + memberships + workflow` 组织
- 不再使用 branch cards、archive 区块、delete-by-branch 交互
- strings 查询和流程动作放在同一页，方便验收和演示
- jobs 作为统一反馈层，不为每类能力单独设计报告页

## 4. 后续拆页建议

如果后续演进为正式产品，建议从当前单页拆成四页：

1. `Project Strings`
2. `Dev Versions`
3. `Rel Operations`
4. `Jobs & Reports`

建议拆分边界：
- `Project Strings`：列表、详情、trash
- `Dev Versions`：import、dev import、candidate release
- `Rel Operations`：rel 集合、hotfix、promote
- `Jobs & Reports`：历史记录、报告、artifact

## 5. 当前未覆盖的页面能力

当前 workbench 还没有单独页面承载以下内容：
- project 创建和切换
- schema 编辑
- 上传式导入
- 权限与审计
- 垃圾桶长期治理和 purge 管理
