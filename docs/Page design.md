# 页面设计：理想 IA 与当前验证工作台

> 当前文档同时描述两件事：
> 1. 理想产品信息架构
> 2. 当前已经落地的单页 workbench 验证形态

## 1. 设计口径
- **理想 IA**：面向最终产品体验，仍然按 4 页分工组织。
- **当前实现**：单页 workbench，用于验证三线生命周期与关键能力，不等于最终产品 IA。

这两个视图必须并存，否则容易出现两种误解：
- 把当前单页验证页误认为最终产品设计
- 把理想 4 页 IA 误认为当前已经实现

## 2. 理想产品信息架构（4 页）

### Page 1：Branch Dashboard
目的：
- 看当前 `dev / release / master` 的线头状态
- 承载高风险生命周期动作

理想内容：
- current dev / release / master 状态
- promote preview / execute
- release hotfix
- archive release -> master
- delete keys
- 最近 jobs 与报告摘要

当前实现映射：
- 已由单页 workbench 中的“三线状态 + hotfix + promote + archive/delete + jobs”覆盖验证

### Page 2：Import Batches
目的：
- 管理导入批次和文件集合
- 作为 `update dev` 及后续报告动作入口

理想内容：
- batch 列表
- 语言、文件数、行数、异常数
- 跳转到 batch detail

当前实现映射：
- 单页 workbench 中已提供样例 import 与 import batch 列表
- 仍缺正式上传流程和多批次深度管理

### Page 3：Import Batch Detail
目的：
- 围绕一批文件做 fill / qa / report / update dev

理想内容：
- 文件树与过滤器
- release / master 基线选择
- fill / untranslated / conflict / package validation / update dev

当前实现映射：
- 单页 workbench 中已验证：
  - update dev
  - fill
  - qa
- 以下仍未实现：
  - untranslated
  - conflict report
  - package validation

### Page 4：Jobs & Reports
目的：
- 统一查看所有动作的执行结果、报告和下载产物

理想内容：
- job 列表
- report 详情
- artifact 下载

当前实现映射：
- 单页 workbench 已有 jobs 列表、job detail、report rows、artifact 下载
- 体验上仍是验证页，不是最终完整报告中心

## 3. 当前实现：单页 Workbench

当前 workbench 入口：`/workbench`

### 3.1 这个页面的角色
- 不是最终产品 IA
- 是当前验证核心能力的统一入口
- 优先验证三线生命周期、状态流转和报告产出

### 3.2 已覆盖的 8 个功能区块

| 区块 | 当前作用 | 对应生命周期环节 |
| --- | --- | --- |
| 样例 / 重置 | 生成 demo fixture，恢复初始状态 | demo reset |
| 三线状态 | 查看 current `dev / release / master` | branch heads |
| Import / Update Dev | 导入样例并写回 dev | import -> update dev |
| Release Hotfix | active / passive hotfix | release content management |
| Promote Preview / Execute | 查看 promote 统计并正式执行 | release lifecycle |
| Archive / Delete | 归档 release 到 master，执行 delete keys | archive / delete |
| Fill / QA | 运行导出与质检验证 | fill / qa |
| Jobs / Reports | 查看 summary、明细和 artifact | job/report |

### 3.3 当前 workbench 对产品目标的价值
- 可以完整验证三线状态是否变化正确
- 可以验证每个变更动作是否产生 `snapshot + report + job`
- 可以验证关键生命周期规则：
  - promote preview / execute
  - archive
  - delete
  - fill / qa

## 4. 页面与能力映射

| 能力 | 理想 IA 页面 | 当前是否已由 workbench 覆盖 |
| --- | --- | --- |
| 三线状态查看 | Page 1 | ✅ |
| Update Dev | Page 3 | ✅ |
| Active / Passive Hotfix | Page 1 | ✅ |
| Promote Preview / Execute | Page 1 | ✅ |
| Archive | Page 1 | ✅ |
| Delete Keys | Page 1 | ✅ |
| Fill | Page 3 | ✅ |
| QA | Page 3 | ✅ |
| Jobs / Reports | Page 4 | ✅ |
| Untranslated | Page 3 | ❌ |
| Conflict Report | Page 3 | ❌ |
| Package Validation | Page 3 | ❌ |
| Delete Preview | Page 1 或 Page 3 | ❌ |

## 5. 交互规则
以下规则适用于理想 IA 和当前 workbench：

1. 所有 Content Management 动作必须生成 `snapshot + report + job`
2. Promote 必须允许先 preview，再 execute
3. Delete 必须显式手动触发，不允许自动推断
4. Fill 必须只写 target 列，不改原文件结构
5. 三线当前状态必须基于 branch head，而不是“最后一个某分支 snapshot”

## 6. 当前页面设计结论
- 理想产品仍建议保留 4 页结构，因为职责清晰。
- 当前实现选择单页 workbench 是正确的，因为它更适合验证生命周期闭环。
- 后续如果从验证形态演进到正式产品，优先拆分的顺序仍建议是：
  1. Import Batches / Batch Detail
  2. Branch Dashboard
  3. Jobs & Reports
