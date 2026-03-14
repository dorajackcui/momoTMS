# Terminology

This page is for humans. It explains the current model in plain language, not as agent instructions.

## One-Line Model

这套系统管理的不是“一个 key 对应一条翻译”，而是：

一个 `business_key` 下面可以有多个原文版本，不同分支在同一时刻各自只选其中一个生效，而且不同分支对内容还有不同修改权限。

## Core Concepts

### Entry

`Entry` 也就是 `business_key`。

- 它是一个稳定的文案槽位
- 它回答的是“这是哪一条文案”
- 它不直接保存当前生效的译文

### Variant

`Variant` 表示同一个槽位下的一版具体内容。在当前项目里，它基本由 `business_key + source` 识别。

一个 variant 会携带：

- `source`
- `translations`
- `remarks`
- `file_name`

可以把它理解成“同一个 key 的某个具体原文版本，以及它配套的译文内容”。

### Binding / Scope

`Binding` 表示某个分支当前指向哪个 variant。项目里对外暴露的是 `scope`：

- `rel/current`
- `dev/<version>`

它回答的是“谁现在在使用这版内容”。

### Authority

`Authority` 表示不同 scope 对 canonical variant content 的修改权重。

它回答的是“当多个 scope 命中同一个 variant 时，谁有资格覆盖内容”。

当前可以近似理解为：

- `rel` 最高
- `dev` 次之
- `orphan` 最低

## In-House Mapping

### `rel/current`

当前发布版本正在使用的内容。它代表对外生效的版本，也拥有最高 authority。

### `dev/<version>`

某个开发版本正在准备、验证、补译、对齐的内容。它可以编辑内容，但不能覆盖 rel 正在占用的 canonical content。

### `orphan`

`orphan` 不是 scope，而是 variant 的一种生命周期状态，表示这条 variant 还存在，但当前没有任何 scope 在使用它。之后如果再次遇到相同的 `source`，系统仍然可以复用它。

## Three Rules To Remember

1. 一个 `business_key` 可以有多个 variant，因为原文会演化。
2. 同一个 scope 下，同一个 key 在同一时刻只能有一个 active variant。
3. `rel` 和 `dev` 的行为差异，本质上来自 authority 差异，而不是两套完全不同的数据模型。

## Common Operations

### Dev Import

当 dev 导入一行数据时，系统先看同一个 `business_key + source` 是否已经存在。

- 不存在：创建新 variant，然后绑定到这个 dev scope
- 已存在且被 rel 使用：只绑定到 dev，不覆盖内容
- 已存在且只被 dev 使用：更新内容，并绑定到当前 dev
- 已存在但已经 orphan：复用它，更新内容，并重新绑定到 dev

### Rel Hotfix

如果 rel 只改译文、`source` 没变：

- 直接修改当前 rel 指向的 variant

如果 rel 连 `source` 都改了：

- rel 会去找新的 same-source variant
- 找到就切过去并更新内容
- 找不到就新建一个再切过去
- 旧 variant 如果没人用了，就变成 orphan

### Promote

`Promote` 的核心动作是 rebinding，不是复制内容。

更直白地说，它是让 `rel/current` 改为指向某个 `dev/<version>` 当前正在使用的 variant。

## Final Memory Hook

- `business_key` 是稳定槽位，不是内容本身。
- `variant` 是这个槽位下的一版原文和译文内容。
- `scope` 决定哪个分支当前在用哪一个 variant。
- `authority` 决定哪个分支有资格覆盖 variant 的内容。
