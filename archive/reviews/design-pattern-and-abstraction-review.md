# Design Pattern And Abstraction Review (Archived)

Archived on March 14, 2026 during the documentation system refactor. Keep this memo as a historical review artifact, not as active implementation guidance.

## 审查范围

- 入口文档：`docs/README.md`
- 代码重点：`app/services/variant/*`、`app/services/workflows/*`、`app/routers/common.py`

## 总体结论

当前实现以“可运行优先”为主，业务路径完整，但在设计模式和抽象层次上存在两类结构性问题：

1. `strings(variants)` 语义与技术实现耦合，且 DTO/映射逻辑分散。
2. `dev`/`rel` 分支行为缺少统一基类（或策略抽象）。

## 发现 1：String/Variant 概念层与 API 兼容层混在一起

### 证据

- `StringService` 本质上通过 `VariantService` 转发并做“string 语义兼容”，但仍直接操作 variant 和 binding 细节，出现命名跨层。
- `VariantService` 注释称“Compatibility facade”，但公开了几乎全部底层能力，没有形成真正的防腐层。

### 风险

- 语义漂移：API 叫 string，内部叫 variant，且 `string_id=variant_id` 是隐式约定。
- 迁移困难：一旦将 string 与 variant 解耦，多个服务和路由会同时受影响。

### 建议

- 采用 Anti-Corruption Layer + Translator。
- 让 `StringService` 只暴露 String 语义，不再透传 variant 原语。
- 新建集中 translator 统一执行 string 和 variant 的映射。

## 发现 2：DTO 组装逻辑重复，违反单一职责

### 证据

- `StringService.get_membership_strings` 手工拼装完整 string 视图。
- `DevVersionService._scope_entry_to_string_detail` 再次拼装几乎同构结构。
- `PreferredEntryViewService.compat_entry_view` 也在做相同职责，但字段策略略有不同。

### 风险

- 字段新增或语义变化时，需要三处以上同步修改。
- 测试会被迫覆盖多个“实现细节不同、语义应一致”的出口。

### 建议

- 引入 Assembler 或 Mapper 模式，单点产出 `StringDetail` / `PreferredEntryView`。
- `workflows` 与 `compatibility` 仅消费 assembler，不再各自拼字段。

## 发现 3：Scope/Branch 使用裸字符串，规则分散

### 证据

- 路由层 `parse_scope_ref` 通过 `{\"rel\", \"dev\"}` 做字符串校验。
- DB 层也用 `CHECK (scope_type IN ('rel', 'dev'))` 固定字面量。
- 服务层大量直接写入 `"rel"` / `"dev"` / `"current"`。

### 风险

- 分支规则不可发现：行为定义散在 router、service、repository、SQL。
- 扩展新分支成本高且容易遗漏。

### 建议

- 引入 Value Object + Enum：`ScopeType`、`ScopeRef`。
- 建立统一的 `ScopePolicy`。
- 将 SQL 常量集中到仓储级常量或查询构建器。

## 发现 4：缺失 branch 基类（dev/rel 行为未抽象）

### 证据

- `DevVersionService` 与 `RelService` 都围绕“读取成员 -> 选择 variant -> bind_scope -> 输出 report”展开，但流程模板未抽象。
- `PromoteService` 充当跨分支流程编排器，却直接依赖字符串 scope 与多个服务细节。

### 风险

- 跨分支流程只靠约定维持一致性。
- 新增分支或修改分支规则时，修改点分散在多个服务。

### 建议

- 引入一个轻量 branch 能力模型（Template Method + Strategy）。
- 让流程层负责编排，让分支层负责声明规则与能力。

## 发现 5：Facade 层抽象泄漏（接口过宽）

### 证据

- `VariantService` 暴露 entry、catalog、binding、lifecycle、views 的几乎全部方法。
- 上层可以轻易绕过 intended abstraction，直接拼接跨层流程。

### 风险

- facade 变成“全能服务”，增加耦合，削弱模块边界。
- 后续重构会波及所有调用点。

### 建议

- 拆分接口：`EntryQueryPort`、`VariantMutationPort`、`ScopeBindingPort`。
- 上层服务只依赖各自最小接口。

## 推荐重构顺序

1. 先收敛 DTO 组装。
2. 再收敛 Scope 常量。
3. 引入 BranchBase。
4. 最后收紧 Facade 接口。
