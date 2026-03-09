# Design Pattern 与抽象层次审查（variants / branches）

## 审查范围
- 入口文档：`docs/README.md`
- 代码重点：`app/services/variant/*`、`app/services/workflows/*`、`app/routers/common.py`

---

## 总体结论
当前实现以“可运行优先”为主，业务路径完整，但在设计模式和抽象层次上存在两类结构性问题：

1. **`strings(variants)` 语义与技术实现耦合，且 DTO/映射逻辑分散**：同一业务对象在多个服务中重复拼装，字段语义（string / variant / canonical）混杂，导致维护成本上升。
2. **`dev`/`rel` 分支行为缺少统一基类（或策略抽象）**：大量以 `scope_type="dev"|"rel"` 的字符串分支驱动逻辑，缺少 branch 能力模型，导致规则散落和扩展困难。

---

## 发现 1：String/Variant 概念层与 API 兼容层混在一起

### 证据
- `StringService` 本质上通过 `VariantService` 转发并做“string 语义兼容”，但仍直接操作 variant/binding 细节，出现命名跨层（如 `string_id` 实际等于 `variant_id`）。
- `VariantService` 注释称“Compatibility facade”，但 facade 公开了几乎全部底层能力，成为“穿透式门面”，没有形成真正的防腐层。

### 风险
- 语义漂移：API 叫 string，内部叫 variant，且 `string_id=variant_id` 是隐式约定。
- 迁移困难：一旦将 string 与 variant 解耦（例如引入独立 string identity），多个服务和路由会同时受影响。

### 建议
- 采用 **Anti-Corruption Layer + Translator**：
  - `StringService` 仅暴露 String 语义，不再透传 variant 原语。
  - 新建集中 translator（如 `StringViewAssembler`）统一执行 string<->variant 映射。
- 在类型上引入明确别名或 dataclass：`StringId` / `VariantId`，避免同值异义。

---

## 发现 2：DTO 组装逻辑重复，违反单一职责

### 证据
- `StringService.get_membership_strings` 手工拼装完整 string 视图。
- `DevVersionService._scope_entry_to_string_detail` 再次拼装几乎同构结构。
- `PreferredEntryViewService.compat_entry_view` 也在做相同职责（但字段策略略不同）。

### 风险
- 字段新增/语义变化时，三处以上同步修改，极易出现行为不一致。
- 测试会被迫覆盖多个“实现细节不同、语义应一致”的出口。

### 建议
- 引入 **Assembler/Mapper 模式**：单点产出 `StringDetail` / `PreferredEntryView`。
- `workflows` 与 `compatibility` 仅消费 assembler，不再各自拼字段。

---

## 发现 3：Scope/Branch 使用裸字符串，规则分散

### 证据
- 路由层 `parse_scope_ref` 通过 `{"rel", "dev"}` 做字符串校验。
- DB 层也用 `CHECK (scope_type IN ('rel', 'dev'))` 固定字面量。
- 服务层大量直接写入 `"rel"/"dev"/"current"`，如绑定、统计、清理、优先级选择等。

### 风险
- 分支规则不可发现：行为定义散在 router/service/repository/SQL。
- 扩展新分支（如 `qa`）成本高且容易遗漏。

### 建议
- 引入 **Value Object + Enum**：`ScopeType`, `ScopeRef`。
- 建立统一的 `ScopePolicy`（例如 dev 是否允许复用 rel 绑定 variant、rel 是否允许直接修改 canonical）。
- 将 SQL 常量集中到仓储级常量/查询构建器，减少跨层硬编码。

---

## 发现 4：缺失 branch 基类（dev/rel 行为未抽象）

### 证据
- `DevVersionService` 与 `RelService` 都围绕“读取成员 -> 选择 variant -> bind_scope -> 输出 report”展开，但流程模板未抽象。
- `PromoteService` 充当跨分支流程编排器，却直接依赖字符串 scope 与多个服务细节。

### 风险
- 跨分支流程（如 promote/hotfix/import）只靠约定维持一致性。
- 新增分支或更改分支规则时，修改点分散在多个服务。

### 建议（重点）
可引入一个轻量分支能力模型（Template Method + Strategy）：

- `BranchBase`（抽象基类）
  - `scope_ref()`
  - `list_members(project_id)`
  - `bind(entry_id, variant_id)`
  - `selection_policy(entry)`
  - `mutation_policy()`
- `DevBranch` / `RelBranch`
  - 分别实现 dev 与 rel 的策略差异（如 rel 的 `current` 固定值、dev 的 version 粒度）。
- `PromotionOrchestrator`
  - 仅依赖 `BranchBase` 接口进行 source->target 同步，不依赖字面量。

这样可把“分支是什么”和“流程做什么”分离：
- 流程层：编排生命周期。
- 分支层：声明规则与能力。

---

## 发现 5：Facade 层抽象泄漏（接口过宽）

### 证据
- `VariantService` 暴露 entry/catalog/binding/lifecycle/views 几乎全部方法。
- 上层（如 `StringService`）可以轻易绕过 intended abstraction，直接拼接跨层流程。

### 风险
- facade 变成“全能服务”，增加耦合，削弱模块边界。
- 后续重构会波及所有调用点。

### 建议
- 拆分接口：`EntryQueryPort`、`VariantMutationPort`、`ScopeBindingPort`。
- `StringService`/`WorkflowService` 仅依赖各自最小接口（ISP 原则）。

---

## 推荐重构顺序（低风险）
1. **先收敛 DTO 组装**：新增 assembler，替换重复拼装代码（不改行为）。
2. **再收敛 Scope 常量**：引入 enum/value object，减少裸字符串。
3. **引入 BranchBase**：先在 `PromoteService` 接入，再逐步迁移 `RelService`/`DevVersionService`。
4. **最后收紧 Facade 接口**：将 `VariantService` 从兼容入口过渡到最小能力接口。

---

## 结语
当前实现已经具备较强业务可用性，但“变更放大系数”偏高。你关注的两个点（`strings(variants)` 封装、`dev/rel` 基类缺失）确实是最关键的架构杠杆位：
- 前者决定语义一致性与 API 可演进性；
- 后者决定流程扩展性与规则可治理性。

优先做“组装收敛 + branch 抽象”两件事，通常能以较小风险获得最明显的维护收益。
