from pathlib import Path

import pandas as pd

from agent.service import SearchService
from agent.settings import Settings


class StubAgent:
    def available_databases(self):
        return ["afdb50"]

    def search_with_summary(
        self,
        pdb_path,
        *,
        database,
        topk,
        min_tmscore=None,
        max_evalue=None,
        min_prob=None,
        tmp_dir=None,
    ):
        hits = pd.DataFrame(
            [
                {
                    "query": "q1",
                    "target": "hitA",
                    "evalue": 1e-5,
                    "tmscore": 0.91,
                    "rmsd": 1.2,
                    "prob": 0.95,
                }
            ]
        )
        summary = {
            "count": 1,
            "best_target": "hitA",
            "best_tmscore": 0.91,
            "median_tmscore": 0.91,
            "median_rmsd": 1.2,
        }
        return hits.head(topk), summary

    def multimer_search(self, pdb_path, database, *, topk=10, tmp_dir=None):
        hits = pd.DataFrame(
            [
                {
                    "query": "q1",
                    "target": "multiA",
                    "evalue": 1e-5,
                    "complexqtmscore": 0.88,
                    "prob": 0.93,
                }
            ]
        )
        summary = {"count": 1, "best_target": "multiA", "best_complexqtmscore": 0.88}
        return hits.head(topk), summary


def test_search_service_exports_json(tmp_path):
    service = SearchService(
        settings=Settings(tmp_dir=str(tmp_path / "tmp"), databases={"afdb50": "/tmp/afdb50"}),
        search_agent=StubAgent(),
    )
    output_path = tmp_path / "out" / "hits.json"

    result = service.search_structure(
        "/tmp/query.pdb",
        database="afdb50",
        topk=1,
        tmp_dir=str(tmp_path / "job_tmp"),
        output_path=str(output_path),
    )

    assert result["request"]["tmp_dir"] == str(tmp_path / "job_tmp")
    assert result["output_path"] == str(output_path)
    assert output_path.exists()
    assert '"target": "hitA"' in output_path.read_text(encoding="utf-8")


def test_search_service_exports_json_into_directory(tmp_path):
    service = SearchService(
        settings=Settings(tmp_dir=str(tmp_path / "tmp"), databases={"afdb50": "/tmp/afdb50"}),
        search_agent=StubAgent(),
    )
    output_dir = tmp_path / "out_dir"

    result = service.search_structure(
        "/tmp/query.pdb",
        database="afdb50",
        topk=1,
        output_path=str(output_dir),
    )

    expected_path = output_dir / "foldseek_hits.json"
    assert result["output_path"] == str(expected_path)
    assert expected_path.exists()
