from pathlib import Path

from agent.runner import FoldseekRunner


def _base_config(tmp_path):
    return {
        "foldseek_path": "foldseek",
        "tmp_dir": str(tmp_path / "tmp"),
        "result_dir": str(tmp_path / "results"),
        "databases": {"afdb50": str(tmp_path / "db")},
        "search": {"max_seqs": 50, "evalue": "1e-4", "timeout_seconds": 30},
    }


def test_easy_cluster_builds_expected_command(monkeypatch, tmp_path):
    commands = []

    def fake_run(cmd, check, timeout):
        commands.append({"cmd": cmd, "check": check, "timeout": timeout})

    monkeypatch.setattr("agent.runner.subprocess.run", fake_run)
    input_file = tmp_path / "input.pdb"
    input_file.write_text("HEADER\n", encoding="utf-8")
    runner = FoldseekRunner(_base_config(tmp_path))

    result = runner.easy_cluster(str(input_file), str(tmp_path / "cluster_out"), alignment_type=1, coverage=0.9)

    assert commands
    command = commands[0]["cmd"]
    assert command[:2] == ["foldseek", "easy-cluster"]
    assert "--alignment-type" in command
    assert "-c" in command
    assert result["cluster_tsv"].endswith("_clu.tsv")


def test_createindex_builds_expected_command(monkeypatch, tmp_path):
    commands = []

    def fake_run(cmd, check, timeout):
        commands.append({"cmd": cmd, "check": check, "timeout": timeout})

    monkeypatch.setattr("agent.runner.subprocess.run", fake_run)
    runner = FoldseekRunner(_base_config(tmp_path))

    result = runner.createindex(str(tmp_path / "target_db"))

    assert commands[0]["cmd"][:2] == ["foldseek", "createindex"]
    assert result["module"] == "createindex"
