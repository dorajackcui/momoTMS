# User Guide

## Purpose

- own the user-facing introduction to the product, its core concepts, and the common operations users see in `/app`

## Read This When

- you need a simple explanation of what this project does for end users
- you need the user-facing meaning of `project`, `business_key`, `variant`, or `branch`
- you are writing onboarding, external-facing introductions, or operator guidance for `/app`

## Owns

- user-facing product overview
- user-facing glossary for branches and variants
- recommended day-to-day usage flow
- plain-language explanation of common product actions

## Does Not Own

- API routes or payload contracts
- backend invariants or database terminology
- detailed workflow rules for import, sync, fill, QA, trash, or restore
- local run commands or validation steps

## Update When

- the product's user-facing concepts, navigation, or common operation flow changes

## 产品定位

Momo TMS 是一个面向本地化协作的版本管理工作台。它服务的不是“单次翻译文件处理”，而是更常见也更麻烦的长期问题：同一批文案会在多个版本里持续演进，团队需要反复导入 Excel、比较差异、复用已有翻译、确认发布范围，并在出问题时能够回溯。

产品的重点不是让使用者理解底层数据结构，而是把一个复杂问题变简单：

- 同一条业务文案，在不同版本里到底应该采用哪一份内容
- 新版本来了以后，哪些内容可以复用，哪些必须重做
- 发布时如何把开发版本安全地提升为新的正式基线

日常操作都集中在 `/app`。你可以把它理解成一个“围绕版本、差异和发布决策展开”的产品界面。

## 它解决什么问题

如果团队直接靠 Excel 文件和人工约定推进版本，通常会遇到几类问题：

- 同一条文案在多个文件和多个版本中重复出现，难以确认哪份才是当前有效内容
- 新版本导入后，只能靠人工比对，容易漏掉真正发生变化的条目
- 已经确认过的翻译很难稳定复用，团队会重复处理同样的内容
- 发布时经常是整包替换，影响范围不透明，出了问题也难排查

Momo TMS 的设计就是围绕这些问题展开的：

- 把“稳定身份”和“具体内容”拆开管理
- 把“内容本身”和“哪个版本正在使用它”拆开管理
- 让比较、复用、发布、恢复都围绕同一套模型完成

这也是它为什么不是一个简单的 Excel 上传器，而是一个带有分支、版本和发布语义的产品。

## 先掌握三个核心概念

### `project`

`project` 是一个独立的业务空间。它定义了这个项目的列结构，包括：

- 固定字段：`business_key` 和 `source`
- 项目自己的翻译列和备注列

项目创建后，列结构保持固定。这么设计的原因是：导入、比对、回填和 QA 都必须基于同一套字段含义工作，否则同一个项目里的结果无法稳定比较。

### `business_key`

`business_key` 表示“一条业务文案的稳定身份”。

它回答的问题是：

- 我们讨论的是不是同一条文案

它不代表当前内容本身，也不代表某个版本。无论文案内容怎么改，只要业务上仍然是同一个槽位，就还是同一个 `business_key`。

### `variant`

`variant` 表示“这条文案在某个时刻的一份具体内容”。

它承载的是实际工作对象，例如：

- 当前源文
- 各语言翻译
- 备注
- 来自哪个文件

这样设计的好处是，系统可以同时保留同一条业务文案的多份内容版本，而不必把整个项目复制很多份。

### `branch`

`branch` 表示“某个版本视角下，系统当前选用了哪些 `variant`”。

它回答的问题是：

- 这个版本现在实际采用的是哪一份内容

分支不是项目副本，也不是把所有数据重新存一遍。它更像一组选择结果：对每个 `business_key`，当前这个分支绑定哪一个 `variant`。

当前最常见的分支有两类：

- `rel/current`：当前正式发布基线
- `dev/<version>`：某个开发版本或待发布版本

## 为什么要这样设计

这套设计的关键价值在于，系统把三个问题拆开了：

- `business_key` 负责“这是谁”
- `variant` 负责“它具体长什么样”
- `branch` 负责“现在谁在用哪一份”

拆开之后，很多高频场景就能更稳定地处理：

- 新版本导入时，不需要整包复制旧版本，只需要为变化的内容生成或切换 `variant`
- 做版本比较时，系统比较的是分支当前采用的内容，而不是两份松散文件
- 发布时，系统做的是“切换正式分支所采用的内容”，而不是再造一套新数据
- 出现误删、冲突或历史问题时，系统可以回看同一条文案的不同内容版本

从使用者角度说，可以把 Momo TMS 理解成：

- 它不是在管理很多份 Excel
- 它是在管理“文案内容”和“版本采用关系”

## 源文变化为什么重要

在这个产品里，`source` 不只是展示字段，它还是判断内容是否发生本质变化的重要依据。

可以这样理解：

- 如果 `business_key` 相同，且 `source` 也相同，系统更倾向于把它视为同一份源文语义下的内容，可以复用已有结果
- 如果 `business_key` 相同，但 `source` 变了，系统会把它当作新的内容阶段处理

这样设计的目的，是把“翻译沿用”和“源文变更”区分开。团队不会因为 key 没变，就错误地沿用一份已经不适用的翻译。

## 为什么分支之间会有 authority

不同分支并不是完全隔离的。当两个分支遇到同一个 `business_key` 下、同一份 `source` 的内容时，它们可能会指向同一个共享 `variant`。

这时系统必须回答一个问题：

- 谁可以改写这份共享内容，谁只能复用它

`branch authority` 就是这条规则。它存在的目的，是避免低优先级分支覆盖高优先级分支已经确认的同源内容，尤其是正式发布基线已经采用的内容。

从普通使用者角度，可以把它记成一句话：

- 高 authority 分支可以改写同源共享内容
- 低 authority 分支只能复用，不能覆盖

当前规则要点：

- `rel/current` 高于所有 `dev/*`
- 同一版本线里，patch 更高的 `dev` 分支 authority 更高
- 不同版本线之间按系统预设优先级判断，不能简单按版本号大小理解

这也是为什么“版本号更大”不一定意味着“能覆盖别人”。

## `variant` 的常见状态

### `active`

- 当前至少被一个分支使用
- 这是大部分日常页面真正关注的内容

### `orphan`

- 当前没有任何分支在使用
- 仍然保留在系统里，方便复用、核查或排障

### `trashed`

- 已被明确移出正常使用流程
- 不会参与正常业务流程，但仍可恢复

这个状态设计的目的，是把“暂时不用了”和“明确移除”区分开，减少误删带来的不可逆风险。

## 日常使用应该怎么理解页面

### `Imports & Jobs`

这里负责接收 Excel 内容，并把一次上传整理成可追踪的导入批次和任务记录。它解决的是“文件已经进来了，但还没真正进入某个版本”的阶段管理问题。

### `Branch Compare`

这里用来比较两个分支当前采用的内容差异。最常见的是比较 `dev/<version>` 和 `rel/current`，帮助你确认新版本到底改了什么，而不是只看文件层面的变动。

### `Translation Queue`

这里是工作队列。它不是简单列出所有文案，而是帮助你优先看到真正需要处理、确认或复核的项目。

### `Fill`

这里把当前分支已经确认的内容回填到输出文件。它解决的是“系统里已经确认过的内容，如何可靠地产出到文件里”。

### `QA`

这里对文件进行规则检查并生成报告。它解决的是“在发布或交付前，怎样用统一规则发现问题”。

### `Replace`

这里把一个 `dev/<version>` 当前采用的内容提升到 `rel/current`。它不是复制一份新数据，而是把正式基线切换到已经准备好的版本结果上。

### `Master Query` 与 `Inspection`

这两个页面主要用于解释和排查：

- 一条文案现在在哪些分支生效
- 同一个 `business_key` 曾经有哪些内容版本
- 某个历史版本为什么没有出现在当前结果里

### `Delete` 与 `Restore`

这两个操作用于清理和恢复。它们的存在说明系统不是“一删就没”，而是把移除动作做成可追踪、可恢复的流程。

## 推荐的日常使用路径

1. 创建项目并确认列结构。
2. 上传 Excel，生成 import batch。
3. 将 import batch 应用到目标 `dev/<version>`。
4. 使用 `Branch Compare` 对比它与 `rel/current` 的差异。
5. 在 `Translation Queue` 中处理待翻译、待确认和待复核内容。
6. 需要产出文件时运行 `Fill`，需要检查质量时运行 `QA`。
7. 确认无误后执行 `Replace`，把该开发版本提升为新的正式基线。
8. 只有在排查、清理或恢复时，再使用 `Master Query`、`Inspection`、`Delete` 和 `Restore`。

## 一句话总结这套产品思路

Momo TMS 的核心不是“存很多份文件”，而是用稳定的业务键、可追踪的内容版本和清晰的分支采用关系，把本地化团队最容易混乱的三件事拆开管理：

- 内容是什么
- 哪个版本在用它
- 什么时候把它发布为正式结果
