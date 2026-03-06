from __future__ import annotations

SAMPLES: list[dict] = [
    {
        "sample_id": "core-cycle",
        "label": "核心生命周期验证样例",
        "description": "覆盖 update dev、hotfix、promote、archive、delete、fill、QA。",
        "lang": "fr",
        "target_col_index": 3,
        "update_dev_version": "2.4.0-dev1",
        "promote_release_version": "2.4.0",
        "active_hotfix": {
            "key": "common.welcome",
            "lang": "fr",
            "target_text": "Bienvenue release hotfix {0}",
        },
        "passive_hotfix": {
            "key": "hotfix.passive",
            "src": "Passive hotfix source",
            "version_tag": "2.3.1-hotfix",
            "targets_by_lang": {
                "fr": "Correctif passif",
                "en": "Passive hotfix",
            },
        },
        "delete_keys": [
            "delete.hit",
            "delete.miss",
        ],
        "release_seed": [
            {
                "key": "common.welcome",
                "src": "Welcome {0}",
                "version_tag": "2.3.0",
                "targets": {"fr": "Bienvenue release {0}"},
            },
            {
                "key": "promote.conflict_keep_release",
                "src": "Old release source",
                "version_tag": "2.3.0",
                "targets": {"fr": "Conserver release"},
            },
            {
                "key": "promote.deprecated",
                "src": "Deprecated source",
                "version_tag": "2.3.0",
                "targets": {"fr": "Cle obsolete"},
            },
            {
                "key": "fill.src_mismatch",
                "src": "Expected source",
                "version_tag": "2.3.0",
                "targets": {"fr": "Release mismatch text"},
            },
            {
                "key": "delete.hit",
                "src": "Delete me",
                "version_tag": "2.3.0",
                "targets": {"fr": "Supprimer moi"},
            },
            {
                "key": "archive.override",
                "src": "Archive from release",
                "version_tag": "2.3.0",
                "targets": {"fr": "Archive version release"},
            },
        ],
        "master_seed": [
            {
                "key": "fill.master_fallback",
                "src": "Master fallback source",
                "version_tag": "master-2026.01",
                "targets": {"fr": "Depuis master"},
            },
            {
                "key": "archive.keep_master",
                "src": "Master only source",
                "version_tag": "master-2026.01",
                "targets": {"fr": "Conserver master"},
            },
            {
                "key": "archive.override",
                "src": "Archive from master old",
                "version_tag": "master-2026.01",
                "targets": {"fr": "Archive version master"},
            },
        ],
        "import_workbooks": [
            {
                "relative_path": "incoming/core_content.xlsx",
                "sheets": [
                    {
                        "title": "Translations",
                        "rows": [
                            ["key", "src", "fr"],
                            ["common.welcome", "Welcome {0}", "Bienvenue dev {0}"],
                            ["promote.added", "Added from dev", "Ajoute depuis dev"],
                            ["promote.conflict_keep_release", "New dev source", "Texte dev en conflit"],
                            ["fill.master_fallback", "Master fallback source", "Depuis dev"],
                            ["qa.error", "Hello {0} <b>x</b>|y", "Bonjour <b>x</i>|y"],
                            ["", "Missing key row", "Ligne invalide"],
                            ["delete.hit", "Delete me", "Supprimer moi depuis dev"],
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
                            ["key", "src", "fr"],
                            ["common.welcome", "Welcome {0}", ""],
                            ["fill.master_fallback", "Master fallback source", ""],
                            ["fill.missing", "Missing base", ""],
                            ["fill.src_mismatch", "Workbook source changed", ""],
                            ["qa.error", "Hello {0} <b>x</b>|y", "Bonjour <b>x</i>|y"],
                        ],
                    }
                ],
            }
        ],
    }
]
