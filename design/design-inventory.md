# 设计盘点矩阵

## 状态说明

- `Solid`: 设计已经在 active docs 和代码中比较清楚
- `Partial`: 设计存在，但还缺少明确边界、取舍记录或补充文档
- `Missing`: 目前主要靠代码隐含，或只有历史材料没有 active 设计资产

## 设计矩阵

| 设计主题 | 当前证据 | 状态 | 还需要补什么 | 推荐后续文档主题 |
| --- | --- | --- | --- | --- |
| 产品边界与兼容策略 | `AGENTS.md`、`docs/system.md`、`docs/contracts.md`、`app/routers/pages.py` | Solid | 仅在未来边界变化时补 ADR | 按需新增 ADR |
| 核心领域模型与术语 | `docs/system.md`、`docs/user-guide.md`、`app/services/branch/models.py`、`app/services/variant/__init__.py` | Solid | 可以补状态转换图和 invariant test matrix，但当前主体已清楚 | 按需新增状态模型说明 |
| workflow 规则 | `docs/workflows.md`、`app/services/branch/*`、`app/services/workflows/*`、相关 tests | Solid | 可补 branch authority 的长期 rationale | ADR 或 authority note |
| API 与 bootstrap 契约 | `docs/contracts.md`、`app/schemas.py`、`app/routers/*` | Solid | 还缺字段演进策略和前后端同步策略 | contract ownership note |
| 运行时与验证流程 | `docs/runtime.md`、`code_review.md`、`AGENTS.md` | Solid | 本次已补“设计过程”层，但后续还可补 feature design template | 按需新增 template |
| 前端页面路由与页面拆分 | `frontend/src/product-app/`、`docs/contracts.md`、`frontend/src/product-app/routes.ts` | Partial | 页面之间已经拆开，但 app-level state 与 side effects 还没有架构文档 | frontend state architecture note |
| 前端共享状态与副作用模型 | `frontend/src/App.tsx` | Partial | 需要明确哪些状态留在 shell，哪些下沉到 page/hook，怎样统一 data refresh 和 action feedback | frontend state architecture note |
| backend 包边界与依赖规则 | `docs/system.md` 的 package map | Partial | 需要明确 router/service/repository/read-model 的允许依赖和禁止依赖 | backend boundaries note |
| repository 与 read model 设计 | `app/services/variant/`、`app/services/read_models/`、archive phase 3 plan | Partial | 需要 query ownership、hydration 策略、性能预算、索引策略 | read model strategy note |
| branch authority 与 version-series 规则 | `app/services/branch/models.py`、`app/services/branch/policy.py`、`docs/system.md` | Partial | 规则存在，但 rationale 和扩展方式还没沉淀成单独设计文档 | branch authority note 或 ADR |
| 契约单一事实来源 | `app/schemas.py` 与 `frontend/src/product-app/types.ts` 双份维护 | Partial | 需要决定是 codegen、shared schema 还是显式同步约定 | contract ownership note |
| 错误语义与 job/report taxonomy | `docs/contracts.md`、`docs/workflows.md`、job/report 代码 | Partial | 需要统一 business status、HTTP error、job failure 的分类和命名规则 | error taxonomy note |
| pivot language 拓扑与异步漂移 | [pivot-language-design.md](pivot-language-design.md)、当前 fill/mutation 代码与讨论记录 | Partial | 需要按设计落地 schema 配置、variant sync state、Fill report，以及 active docs follow-through | pivot language system note |
| 数据演进与兼容策略 | `AGENTS.md`、`docs/runtime.md` 明确 reset 优先 | Partial | 需要补“什么时候 reset 就够，什么时候必须 migration”的决策标准 | change compatibility policy note |
| 非功能需求 | archive 中有 performance 相关材料，但 active docs 较少 | Missing | 需要明确数据规模、性能预算、并发假设、可观测性目标 | non-functional targets note |
| ADR / decision log 机制 | archive 里有旧 ADR，active 工作流里没有 | Missing | 需要重新建立 active ADR 入口和生命周期规则 | ADR index and template |
| 安全、权限、审计 | `docs/contracts.md` 明确 not in scope | Missing | 目前可以继续视为 non-goal，但需要记录未来何时触发这类设计 | 未来按需补充 |

## 当前建议优先级

### P1

- [ ] frontend state architecture
- [ ] read model strategy

### P2

- [ ] contract ownership
- [ ] error taxonomy
- [ ] branch authority

### P3

- [ ] non-functional targets
- [ ] change compatibility policy
- [ ] 建立 active ADR 目录和模板

## 已经比较明确的设计清单

- [x] `/app` 是唯一 operator-facing surface
- [x] API 保持 project-scoped
- [x] project schema 创建后固定
- [x] canonical-source variant model
- [x] `active / orphan / trashed` 生命周期
- [x] import / mutation / replace / trash / restore / fill / QA 的运行时规则
- [x] owner doc + validation + docs validator 的闭环

## 仍需重点补齐的设计清单

- [ ] 前端共享状态架构
- [ ] repository 与 read model 的边界
- [ ] 前后端 contract 的单一事实来源
- [ ] 统一错误与报告 taxonomy
- [ ] 非功能目标和性能预算
- [ ] active ADR / decision log 机制
