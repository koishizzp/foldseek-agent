from pathlib import Path

import pandas as pd
import yaml

from agent.foldseek_agent import FoldseekAgent


class DummyRunner:
    def __init__(self, output_path):
        self.output_path = output_path

    def search(self, query_pdb, db_path, out_file):
        Path(out_file).write_text(Path(self.output_path).read_text(encoding="utf-8"), encoding="utf-8")
        return out_file


def test_search_structure_returns_top_hits(tmp_path):
    config = {
        "foldseek_path": "foldseek",
        "databases": {"afdb50": "/data/foldseek/afdb50"},
        "tmp_dir": str(tmp_path / "tmp"),
        "result_dir": str(tmp_path / "results"),
        "search": {"max_seqs": 100, "evalue": "1e-3"},
    }
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")

    mock_result = tmp_path / "mock.m8"
    mock_result.write_text(
        "q1\tt1\t1e-5\t0.9\t1.2\t0.95\n"
        "q1\tt2\t1e-4\t0.8\t1.5\t0.90\n",
        encoding="utf-8",
    )

    agent = FoldseekAgent(str(config_path))
    agent.runner = DummyRunner(mock_result)

    hits = agent.search_structure("example.pdb", topk=1)

    assert isinstance(hits, pd.DataFrame)
    assert len(hits) == 1
    assert hits.iloc[0]["target"] == "t1"
