from pathlib import Path

import yaml

from .parser import FoldseekParser
from .runner import FoldseekRunner


class FoldseekAgent:
    def __init__(self, config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)

        self.runner = FoldseekRunner(self.config)
        self.parser = FoldseekParser()

    def search_structure(self, pdb_file, database="afdb50", topk=10):
        db_path = self.config["databases"][database]
        result_dir = self.config.get("result_dir", "./results")
        out_file = str(Path(result_dir) / "result.m8")

        result_file = self.runner.search(pdb_file, db_path, out_file)
        df = self.parser.parse(result_file)
        hits = self.parser.top_hits(df, topk)
        return hits
