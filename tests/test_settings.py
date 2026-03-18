from pathlib import Path

import yaml

from agent.settings import Settings


def test_settings_from_env_resolves_paths_and_openai_aliases(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "foldseek_root": str(tmp_path / "foldseek-root"),
                "foldseek_path": "foldseek",
                "default_database": "afdb50",
                "databases": {"afdb50": "db/afdb50", "pdb": "db/pdb"},
                "database_scan_roots": ["db_scan"],
                "tmp_dir": "tmp",
                "result_dir": "results",
                "search": {"max_seqs": 50, "evalue": "1e-5", "timeout_seconds": 30},
                "cluster": {"timeout_seconds": 120},
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("OPENAI_MODEL", "gpt-4.1-mini")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("FOLDSEEK_AGENT_CONFIG", str(config_path))

    settings = Settings.from_env()

    assert settings.llm_model == "gpt-4.1-mini"
    assert settings.openai_api_key == "test-key"
    assert settings.databases["afdb50"] == str(Path(tmp_path / "foldseek-root" / "db" / "afdb50"))
    assert settings.database_scan_roots == [str(Path(tmp_path / "foldseek-root" / "db_scan"))]
    assert settings.tmp_dir == str(Path(tmp_path / "foldseek-root" / "tmp"))
    assert settings.upload_dir == str(Path(tmp_path / "foldseek-root" / "uploads"))
    assert settings.search_max_seqs == 50
    assert settings.search_timeout_seconds == 30
    assert settings.to_agent_config()["database_scan_roots"] == [str(Path(tmp_path / "foldseek-root" / "db_scan"))]
    assert settings.to_agent_config()["cluster"]["timeout_seconds"] == 120


def test_settings_database_scan_roots_can_be_overridden_from_env(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump({"foldseek_root": str(tmp_path / "foldseek-root")}), encoding="utf-8")

    monkeypatch.setenv("FOLDSEEK_AGENT_CONFIG", str(config_path))
    monkeypatch.setenv(
        "FOLDSEEK_AGENT_DATABASE_SCAN_ROOTS_JSON",
        '["scan_a","/mnt/custom/databases"]',
    )

    settings = Settings.from_env()

    assert settings.database_scan_roots == [
        str(Path(tmp_path / "foldseek-root" / "scan_a")),
        "/mnt/custom/databases",
    ]
