# TMS Terms and Model

这份文档给人看，不是给 agent 用的。

目标只有两个：

- 用最少的术语讲明白这套 TMS 在管理什么
- 区分“通用模型”和“我们项目当前的 in-house 约定”

## 一句话先说清

这套系统管理的不是“一个 key 对应一条翻译”，而是：

“一个 key 下面可以有多个原文版本，不同分支在同一时刻各自只选其中一个生效，而不同分支对内容还有不同修改权限。”

## 先讲通用模型

如果以后要开源，最值得保留的是下面这 4 层，而不是 `rel/dev` 这些具体名字。

### 1. Entry

也就是 `business_key`。

它表示一个稳定的文案槽位，只回答一件事：

"这是哪一条文案？"

它不直接保存译文，也不代表当前线上到底用哪版原文。

### 2. Variant

`variant` 表示这个槽位下的一版具体内容。

在当前项目里，它基本由 `business_key + source` 来识别。一个 variant 会携带：

- `source`：原文
- `translations`：译文
- `remarks`：备注
- `file_name`：来源文件信息

可以把它理解成：

"同一个 key 的某个具体原文版本，以及它配套的译文内容。"

### 3. Binding

`binding` 表示某个分支 / 环境 / 发布线当前指向哪个 variant。

它回答的是：

"谁现在在使用这版内容？"

### 4. Authority

`authority` 表示不同分支对已有 variant content 的修改权重。

它回答的是：

"当多个分支命中同一个 variant 时，谁有资格覆盖这条内容？"

这是当前系统里很关键的一层。很多行为差异，不是因为名字叫 `rel` 或 `dev`，而是因为它们 authority 不同。

## 当前项目里的 in-house 映射

上面的 4 层，在我们项目里被映射成下面这些术语。

### business_key

稳定槽位。

例如一个 UI 文案、一条错误提示、一个按钮标题，都应该有自己的 `business_key`。

### variant

同一个 `business_key` 下，不同 `source` 会形成不同的 variant。

所以：

- 一个 key 可以有多个 variant
- 但同一个 `source` 只应该对应一个 canonical variant

### scope

当前项目里的 `scope`，本质上就是 binding 所属的“分支名”。

目前主要有两类：

- `rel/current`
- `dev/<version>`

### orphan

`orphan` 不是 scope，不是分支。

它是 variant 的一种生命周期状态，表示：

"这条 variant 还存在，但当前没有任何 scope 在使用它。"

它通常是旧 source 被切走后留下来的历史版本，之后如果又遇到相同 source，可以复用。

## 最重要的 3 条规则

### 规则 1：一个 key 可以有多个 variant

因为原文会演化。

同一个 `business_key` 在不同时间可能出现多个 `source`，系统需要保留这些 source 版本，而不是简单覆盖历史。

### 规则 2：同一个 scope 下，一个 key 只能有一个 active variant

这是理解系统行为最关键的一句。

含义是：

- 在 `rel/current` 里，一个 key 只会有一个当前生效的 source
- 在某个 `dev/<version>` 里，一个 key 也只会有一个当前生效的 source

所以正常业务读取里，不会出现“同一个 scope 下同一个 key 同时命中两个 active source”。

### 规则 3：分支行为不同，根本原因是 authority 不同

当前 authority 大致可以理解为：

- `rel` 最高
- `dev` 次之
- `orphan` 最低

这意味着：

- `dev` 命中 rel 正在使用的 same-source variant 时，只能绑定，不能覆盖内容
- `dev` 命中 dev-owned 或 orphan 的 same-source variant 时，可以更新内容
- `rel` 命中 same-source variant 时，可以按 rel payload 覆盖 canonical content

所以“不同分支行为不同”本质上不是流程差异，而是 authority 差异。

## 用最直白的话解释 rel / dev / orphan

### rel/current

当前发布版本正在使用的内容。

它代表对外生效的版本，也拥有最高 authority。

### dev/<version>

某个开发版本正在准备、验证、补译、对齐的内容。

它可以编辑内容，但不能覆盖 rel 正在占用的 canonical content。

### orphan

旧版本内容还在，但已经没有任何 scope 使用。

它不是“删除”，而是“暂时无人引用”。之后遇到同样的 `source`，系统仍然可以复用它。

## 常见操作该怎么理解

### 1. Dev Import

当 dev 导入一行数据时，系统先看同一个 `business_key + source` 是否已经存在。

- 不存在：创建新 variant，然后绑定到这个 dev scope
- 存在且被 rel 使用：只绑定到 dev，不覆盖内容
- 存在且只被 dev 使用：更新内容，并绑定到当前 dev
- 存在但已经 orphan：复用它，更新内容，并重新绑定到 dev

### 2. Rel Hotfix

如果 rel 只是改译文，`source` 没变：

- 直接修改当前 rel 指向的 variant

如果 rel 连 `source` 都改了：

- rel 会去找新的 same-source variant
- 找到就切过去并更新内容
- 找不到就新建一个再切过去
- 旧 variant 如果没人用了，就变成 orphan

### 3. Promote

`promote` 不是复制一份内容到 rel。

它更像是：

"让 `rel/current` 改为指向某个 `dev/<version>` 当前正在使用的 variant。"

也就是说，promote 的核心动作是 rebinding，不是 content copy。

## 为什么这套设计适合 in-house

这套设计明显偏工程化，适合下面这种内部流程：

- 原文会持续变化，不是一次性定稿
- dev 和 rel 需要长期并存
- 发布后还会做 hotfix
- 同一个 key 的旧 source 不能直接丢掉
- 希望 promote 更像“切引用”而不是“复制数据”

对这种场景，这套设计是合理的，因为它把：

- 槽位
- 内容版本
- 分支选择
- 修改权限

拆开管理了。

## 如果以后想做得更通用

如果这个项目以后开源，更推荐把“概念层”写得更 general，把当前规则写成默认策略。

更通用的表达方式应该是：

- `Entry`
- `Variant`
- `Binding`
- `Lifecycle`
- `Authority Policy`

然后把当前项目的 `rel/current`、`dev/<version>`、`orphan` 解释成这套通用模型的一组默认映射。

这样外部团队就可以把它替换成自己的术语，例如：

- `prod / staging / draft`
- `main / release / feature`
- `approved / working / archived`

而不需要先接受我们团队内部的 `rel/dev` 命名。

## 给新人记住的最终版本

只要先记住下面 4 句，基本就不会迷路：

1. `business_key` 是稳定槽位，不是内容本身。
2. `variant` 是这个槽位下的一版原文和译文内容。
3. `scope` 决定哪个分支当前在用哪一个 variant。
4. `authority` 决定哪个分支有资格覆盖 variant 的内容。

再加一句最关键的运行规则：

"一个 key 可以有多个 variant，但在同一个 scope 下，同一时刻只会有一个 active variant。"
