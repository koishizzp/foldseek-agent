import json
from pathlib import Path

import pandas as pd
import pytest
import yaml

from agent.foldseek_agent import FoldseekAgent
from agent.parser import FoldseekParser


class DummyRunner:
    def __init__(self, output_path):
        self.output_path = output_path

    def search(self, query_pdb, db_path, out_file):
        Path(out_file).write_text(Path(self.output_path).read_text(encoding="utf-8"), encoding="utf-8")
        return out_file


@pytest.fixture
def test_config(tmp_path):
    config = {
        "foldseek_path": "foldseek",
        "databases": {
            "afdb50": "/data/foldseek/afdb50",
            "pdb": "/data/foldseek/pdb",
        },
        "tmp_dir": str(tmp_path / "tmp"),
        "result_dir": str(tmp_path / "results"),
        "search": {"max_seqs": 100, "evalue": "1e-3"},
    }
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")
    return config_path


def _mock_result_file(tmp_path):
    mock_result = tmp_path / "mock.m8"
    mock_result.write_text(
        "q1\tt1\t1e-5\t0.9\t1.2\t0.95\n"
        "q1\tt2\t1e-4\t0.8\t1.5\t0.90\n"
        "q1\tt3\t1e-2\t0.2\t5.2\t0.40\n",
        encoding="utf-8",
    )
    return mock_result


@pytest.fixture
def query_pdb(tmp_path):
    path = tmp_path / "query.pdb"
    path.write_text("HEADER TEST\n", encoding="utf-8")
    return path


def test_search_structure_returns_top_hits(tmp_path, test_config, query_pdb):
    agent = FoldseekAgent(str(test_config))
    agent.runner = DummyRunner(_mock_result_file(tmp_path))

    hits = agent.search_structure(str(query_pdb), topk=1)

    assert isinstance(hits, pd.DataFrame)
    assert len(hits) == 1
    assert hits.iloc[0]["target"] == "t1"


def test_search_structure_supports_filters(tmp_path, test_config, query_pdb):
    agent = FoldseekAgent(str(test_config))
    agent.runner = DummyRunner(_mock_result_file(tmp_path))

    hits = agent.search_structure(
        str(query_pdb),
        min_tmscore=0.75,
        max_evalue=1e-3,
        min_prob=0.85,
    )

    assert set(hits["target"]) == {"t1", "t2"}


def test_unknown_database_allows_raw_path(tmp_path, test_config, query_pdb):
    agent = FoldseekAgent(str(test_config))
    agent.runner = DummyRunner(_mock_result_file(tmp_path))

    hits = agent.search_structure(str(query_pdb), database="/raw/db/prefix", topk=1)

    assert len(hits) == 1


def test_export_json(tmp_path, test_config, query_pdb):
    agent = FoldseekAgent(str(test_config))
    agent.runner = DummyRunner(_mock_result_file(tmp_path))

    hits = agent.search_structure(str(query_pdb), topk=2)
    output = tmp_path / "hits" / "top_hits.json"
    result = agent.export_hits_json(hits, str(output))

    payload = json.loads(Path(result).read_text(encoding="utf-8"))
    assert isinstance(payload, list)
    assert payload[0]["target"] == "t1"


def test_parser_summary_handles_empty():
    parser = FoldseekParser()
    empty = pd.DataFrame(columns=FoldseekParser.COLUMNS)

    summary = parser.summary(empty)

    assert summary["count"] == 0
    assert summary["best_target"] is None
