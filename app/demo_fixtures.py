from __future__ import annotations

SAMPLES: list[dict] = [
    {
        "sample_id": "core-cycle",
        "label": "Canonical Strings Core Cycle",
        "description": "覆盖目录导入、dev import、rel hotfix、promote、trash、fill 与 QA。",
        "lang": "fr",
        "dev_version": "2.2.3",
        "active_hotfix": {
            "business_key": "common.welcome",
            "lang": "fr",
            "target_text": "Bienvenue hotfix {0}",
        },
        "passive_hotfix": {
            "business_key": "hotfix.passive",
            "file_name": "release/common.xlsx",
            "source": "Passive hotfix source updated",
            "translations_by_lang": {
                "fr": "Correctif passif",
                "en": "Passive hotfix",
            },
            "remarks_by_key": {
                "context": "Passive hotfix updated from rel",
            },
        },
        "trash_keys": ["trash.me"],
        "seed_strings": [
            {
                "file_name": "common/home.xlsx",
                "business_key": "common.welcome",
                "source": "Welcome {0}",
                "translations": {"fr": "Bienvenue {0}", "en": "Welcome {0}"},
                "remarks": {"context": "Shown on home page"},
                "memberships": ["rel"],
            },
            {
                "file_name": "release/locked.xlsx",
                "business_key": "rel.locked.same",
                "source": "Release same source",
                "translations": {"fr": "Release same target", "en": "Release same target EN"},
                "remarks": {"context": "Should become tagged_only"},
                "memberships": ["rel"],
            },
            {
                "file_name": "release/locked.xlsx",
                "business_key": "rel.locked.changed",
                "source": "Release protected source",
                "translations": {"fr": "Release protected target", "en": "Release protected target EN"},
                "remarks": {"context": "Should become protected_skipped"},
                "memberships": ["rel"],
            },
            {
                "file_name": "release/common.xlsx",
                "business_key": "hotfix.passive",
                "source": "Passive hotfix source",
                "translations": {"fr": "Correctif passif ancien", "en": "Passive hotfix old"},
                "remarks": {"context": "Passive hotfix candidate"},
                "memberships": ["rel"],
            },
            {
                "file_name": "release/fill.xlsx",
                "business_key": "fill.rel",
                "source": "Release fill source",
                "translations": {"fr": "Release fill target", "en": "Release fill target EN"},
                "remarks": {"context": "Release fill example"},
                "memberships": ["rel"],
            },
            {
                "file_name": "dev/mutable.xlsx",
                "business_key": "dev.mutable",
                "source": "Mutable source old",
                "translations": {"fr": "Mutable old fr", "en": "Mutable old en"},
                "remarks": {"context": "Updatable by dev import"},
                "memberships": [],
            },
            {
                "file_name": "master/fallback.xlsx",
                "business_key": "fill.master_only",
                "source": "Master fallback source",
                "translations": {"fr": "Depuis master", "en": "From master"},
                "remarks": {"context": "Only in master"},
                "memberships": [],
            },
            {
                "file_name": "master/trash.xlsx",
                "business_key": "trash.me",
                "source": "Trash me source",
                "translations": {"fr": "Supprimer moi", "en": "Trash me"},
                "remarks": {"context": "Trash sample"},
                "memberships": [],
            },
        ],
        "import_workbooks": [
            {
                "relative_path": "incoming/dev_2_2_3.xlsx",
                "sheets": [
                    {
                        "title": "Strings",
                        "rows": [
                            ["file_name", "business_key", "source", "fr", "en", "context"],
                            ["release/locked.xlsx", "rel.locked.same", "Release same source", "Release same target", "Release same target EN", "Should become tagged_only"],
                            ["release/locked.xlsx", "rel.locked.changed", "Release protected source changed", "Release protected target changed", "Release protected target changed EN", "Should become protected_skipped"],
                            ["dev/mutable.xlsx", "dev.mutable", "Mutable source updated", "Mutable updated fr", "Mutable updated en", "Updated by dev import"],
                            ["dev/new.xlsx", "dev.new.entry", "New source from dev", "New target fr", "New target en", "Created by dev import"],
                            ["bad/missing.xlsx", "", "Missing key row", "", "", "Invalid missing business key"],
                            ["bad/source.xlsx", "missing.source", "", "No source", "No source", "Invalid missing source"],
                        ],
                    }
                ],
            }
        ],
        "fill_workbooks": [
            {
                "relative_path": "fill/fill_input.xlsx",
                "sheets": [
                    {
                        "title": "Sheet1",
                        "rows": [
                            ["file_name", "business_key", "source", "fr", "en", "context"],
                            ["common/home.xlsx", "common.welcome", "Welcome {0}", "", "", "Fill from rel"],
                            ["master/fallback.xlsx", "fill.master_only", "Master fallback source", "", "", "Fill from master"],
                            ["release/fill.xlsx", "fill.rel", "Release fill source changed", "", "", "Should mismatch source"],
                            ["missing/fill.xlsx", "fill.missing", "Missing source", "", "", "Missing in base"],
                            ["qa/error.xlsx", "qa.error", "Hello {0} <b>x</b>|y", "Bonjour <b>x</i>|y", "", "QA issue only"],
                        ],
                    }
                ],
            }
        ],
    }
]
