from __future__ import annotations

import json
from pathlib import Path

import yaml

from .parser import FoldseekParser
from .runner import FoldseekRunner
from .utils import ensure_dir, validate_config, validate_database_name


class FoldseekAgent:
    def __init__(self, config_path: str):
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)

        validate_config(self.config)
        self.runner = FoldseekRunner(self.config)
        self.parser = FoldseekParser()

    def available_databases(self) -> list[str]:
        return sorted(self.config["databases"].keys())

    def search_structure(
        self,
        pdb_file: str,
        database: str = "afdb50",
        topk: int = 10,
        min_tmscore: float | None = None,
        max_evalue: float | None = None,
        min_prob: float | None = None,
    ):
        validate_database_name(database, self.config["databases"])

        db_path = self.config["databases"][database]
        result_dir = ensure_dir(self.config.get("result_dir", "./results"))
        out_file = str(Path(result_dir) / "result.m8")

        result_file = self.runner.search(pdb_file, db_path, out_file)
        df = self.parser.parse(result_file)
        filtered = self.parser.filter_hits(
            df,
            min_tmscore=min_tmscore,
            max_evalue=max_evalue,
            min_prob=min_prob,
        )
        return self.parser.top_hits(filtered, topk)

    def search_with_summary(self, *args, **kwargs) -> tuple:
        hits = self.search_structure(*args, **kwargs)
        return hits, self.parser.summary(hits)

    def export_hits_json(self, hits, output_path: str) -> str:
        records = hits.to_dict(orient="records")
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
        return output_path
