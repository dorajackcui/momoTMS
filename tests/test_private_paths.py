from pathlib import Path


def test_branch_cycle_smoke_docs_and_scripts_do_not_embed_local_user_paths() -> None:
    root = Path(__file__).resolve().parents[1]
    paths = [
        root / "docs" / "testing.md",
        root / "scripts" / "run_branch_cycle_smoke.py",
    ]
    optional_local_scripts = [
        root / "scripts" / "profile_bootstrap.py",
    ]
    paths.extend(path for path in optional_local_scripts if path.exists())

    private_user_fragment = "yizhi" + "003"
    offenders: list[str] = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        if private_user_fragment in text.lower():
            offenders.append(str(path.relative_to(root)))

    assert offenders == []
