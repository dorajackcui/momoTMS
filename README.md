# Momo TMS (MVP)

一个面向 Windows Excel 本地化流程的 Translation Management System 原型，覆盖以下能力：

- Import batch（整包/目录导入）
- Snapshot 化版本管理（dev/release/master）
- Dev LWW 更新
- Release hotfix（active single / passive single）
- Promote（dev_last -> new release，src 冲突保旧 release）
- Fill（release > master 回填，严格仅写 target 列）
- QA 规则引擎（`{}`、`<>`、`|`）

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
uvicorn app.main:app --reload
```

## Windows Agent Note

If the agent cannot access your user-level Python install, copy Python into the workspace once and recreate `.venv`:

```powershell
cd d:\tms\Momo_TMS
.\scripts\bootstrap_local_python.ps1 -PythonHome "C:\Users\yizhi003\AppData\Local\Programs\Python\Python311"
.\.venv\Scripts\python.exe -m pip install -e .[dev]
```

## API 概览

- `POST /import`
- `GET /import/{id}/report`
- `POST /snapshot`
- `POST /update/dev`
- `POST /update/release/active_single`
- `POST /update/release/passive_single`
- `POST /promote`
- `POST /fill`

## 核心规则实现说明

- Promote 目标 key 空间固定为 `Keys(dev_last)`。
- 同 key 且 src 变化的冲突，采用 release 上一版条目（保旧）。
- Fill 匹配要求同 key 且 src_hash 一致；优先级 release > master。
- Fill 不增删行、不改结构，仅写入 target 列。

## 备注

当前版本聚焦 MVP 的后端核心逻辑与数据结构。后续可追加：

- Web UI（批次上传、报表可视化）
- 权限模型 UI 与审计日志
- 更细粒度 diff/report
- 大体量 Excel 并行与性能优化

## 项目文档

- [项目需求说明](docs/PROJECT_REQUIREMENTS.md)
- [架构与设计说明](docs/ARCHITECTURE_DESIGN.md)
- [项目进度说明](docs/PROJECT_PROGRESS.md)
