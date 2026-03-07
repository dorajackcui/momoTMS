# Momo TMS

一个围绕 `canonical strings + rel/dev memberships + trash` 的本地化管理原型。

当前实现已经不再兼容旧的 `snapshot / branch_heads / archive / delete-by-branch` 模型，按重做后的新设计运行。

## Current Model

- `string`：按 `business_key` 在 project 内唯一
- `master`：所有未删除 strings 的隐式全集
- `rel`：当前上线集合 membership
- `dev_version`：开发候选集合 membership
- `dev import`：
  - 新 key：创建 canonical string 并打上 `dev` tag
  - 已存在且不在 `rel`：更新 canonical 内容并打上 `dev` tag
  - 已存在且在 `rel`：只加 `dev` tag，不覆盖 canonical 内容
- 删除：`master soft delete + 30 天垃圾桶 + restore`
- `promote`：将目标 `dev_version` 集合切换为新的 `rel`，并清理当前版本线的 `dev` tags

## Quick Start

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
uvicorn app.main:app --reload
```

打开：

- Workbench: [http://127.0.0.1:8000/workbench](http://127.0.0.1:8000/workbench)
- OpenAPI: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

首次进入如果库里没有 demo 数据，先执行 `POST /api/demo/reset`，或者在 workbench 里点“重置演示环境”。

## Environment

- Python 虚拟环境默认放在 [`/Users/zhiyangcui/Documents/Momo_TMS/.venv`](/Users/zhiyangcui/Documents/Momo_TMS/.venv)
- Playwright 浏览器可以放在仓库内目录：[`/Users/zhiyangcui/Documents/Momo_TMS/.playwright`](/Users/zhiyangcui/Documents/Momo_TMS/.playwright)

## Main API

- `GET /api/state`
- `POST /api/demo/reset`
- `GET /api/strings`
- `GET /api/strings/{business_key}`
- `POST /api/imports/directory`
- `GET /api/imports`
- `GET /api/imports/{import_batch_id}/report`
- `POST /api/dev-versions/import`
- `GET /api/dev-versions`
- `GET /api/dev-versions/{version}`
- `POST /api/rel/hotfix/active`
- `POST /api/rel/hotfix/passive`
- `POST /api/promote/preview`
- `POST /api/promote/execute`
- `POST /api/trash/delete`
- `POST /api/trash/restore`
- `POST /api/fill`
- `POST /api/qa`
- `GET /api/jobs`
- `GET /api/jobs/{job_id}`
- `GET /api/jobs/{job_id}/report`
- `GET /api/jobs/{job_id}/artifact/{name}`

## Test

后端测试：

```bash
. .venv/bin/activate
python -m pytest -q
```

E2E：

```bash
. .venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

另开一个终端：

```bash
PLAYWRIGHT_BROWSERS_PATH=.playwright npm run test:e2e
```

## Repo Structure

- [`app/db.py`](/Users/zhiyangcui/Documents/Momo_TMS/app/db.py)：SQLite schema 与初始化
- [`app/main.py`](/Users/zhiyangcui/Documents/Momo_TMS/app/main.py)：FastAPI 入口
- [`app/services/workbench_service.py`](/Users/zhiyangcui/Documents/Momo_TMS/app/services/workbench_service.py)：job orchestration
- [`app/static/workbench.html`](/Users/zhiyangcui/Documents/Momo_TMS/app/static/workbench.html)：最小验证 workbench
- [`app/demo_fixtures.py`](/Users/zhiyangcui/Documents/Momo_TMS/app/demo_fixtures.py)：demo seed 和样例 Excel
- [`tests/`](/Users/zhiyangcui/Documents/Momo_TMS/tests)：单元测试与 E2E

## Docs

- [项目需求说明](docs/PROJECT_REQUIREMENTS.md)
- [架构与设计说明](docs/ARCHITECTURE_DESIGN.md)
- [能力与 API 对齐总表](docs/API_ALIGNMENT_SUMMARY.md)
- [页面设计](docs/Page%20design.md)

## Notes

- 当前实现先支持单默认 project，但表结构已预留 `project_id`
- `promote` 后不保留旧 dev 集合作为运行时查询对象；历史追溯依赖 jobs 和 reports
- 这是破坏式重构版本，不做旧数据库和旧接口兼容
