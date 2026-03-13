from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml

from .parser import FoldseekParser
from .runner import FoldseekRunner
from .utils import (
    ensure_dir,
    validate_config,
    validate_existing_path,
    validate_query_path,
)


class FoldseekAgent:
    MULTIMER_COLUMNS = [
        "query",
        "target",
        "evalue",
        "complexqtmscore",
        "complexttmscore",
        "qtmscore",
        "ttmscore",
        "interfacelddt",
        "prob",
    ]

    def __init__(self, config_or_path: str | dict[str, Any]):
        if isinstance(config_or_path, dict):
            self.config = config_or_path
        else:
            with open(config_or_path, "r", encoding="utf-8") as f:
                self.config = yaml.safe_load(f)

        validate_config(self.config)
        self.runner = FoldseekRunner(self.config)
        self.parser = FoldseekParser()

    def available_databases(self) -> list[str]:
        return sorted(self.config["databases"].keys())

    def resolve_database(self, database: str) -> str:
        if database in self.config["databases"]:
            return self.config["databases"][database]
        return database

    def _result_dir(self) -> str:
        return ensure_dir(self.config.get("result_dir", "./results"))

    def _unique_path(self, stem: str, suffix: str) -> str:
        result_dir = self._result_dir()
        return str(Path(result_dir) / f"{stem}_{uuid4().hex[:12]}{suffix}")

    def search_structure(
        self,
        pdb_file: str,
        database: str = "afdb50",
        topk: int = 10,
        min_tmscore: float | None = None,
        max_evalue: float | None = None,
        min_prob: float | None = None,
    ):
        validate_query_path(pdb_file)
        db_path = self.resolve_database(database)
        out_file = self._unique_path("foldseek", ".m8")
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

    def search_records(self, *args, **kwargs) -> list[dict[str, Any]]:
        hits = self.search_structure(*args, **kwargs)
        return hits.to_dict(orient="records")

    def multimer_search(
        self,
        pdb_file: str,
        database: str,
        *,
        topk: int = 10,
    ) -> tuple:
        validate_query_path(pdb_file)
        target_path = self.resolve_database(database)
        out_file = self._unique_path("foldseek_multimer", ".tsv")
        self.runner.easy_multimersearch(pdb_file, target_path, out_file)
        df = self.parser.parse_table(out_file, self.MULTIMER_COLUMNS)
        if "complexqtmscore" in df.columns:
            df = df.sort_values(by=["complexqtmscore", "prob"], ascending=False).head(topk)
        else:
            df = df.head(topk)
        summary = {
            "count": int(len(df)),
            "best_target": None if df.empty else str(df.iloc[0]["target"]),
            "best_complexqtmscore": None if df.empty else float(df.iloc[0]["complexqtmscore"]),
            "best_interfacelddt": None if df.empty else float(df.iloc[0]["interfacelddt"]),
        }
        return df, summary

    def easy_cluster(
        self,
        input_path: str,
        *,
        output_prefix: str | None = None,
        alignment_type: int | None = None,
        coverage: float | None = None,
    ) -> dict[str, Any]:
        validate_existing_path(input_path)
        return self.runner.easy_cluster(
            input_path,
            output_prefix or self._unique_path("foldseek_cluster", ""),
            alignment_type=alignment_type,
            coverage=coverage,
        )

    def easy_multimercluster(
        self,
        input_path: str,
        *,
        output_prefix: str | None = None,
        multimer_tmscore: float | None = None,
        chain_tmscore: float | None = None,
        interface_lddt: float | None = None,
    ) -> dict[str, Any]:
        validate_existing_path(input_path)
        return self.runner.easy_multimercluster(
            input_path,
            output_prefix or self._unique_path("foldseek_multimercluster", ""),
            multimer_tmscore=multimer_tmscore,
            chain_tmscore=chain_tmscore,
            interface_lddt=interface_lddt,
        )

    def createdb(
        self,
        input_path: str,
        *,
        output_db: str | None = None,
        prostt5_model: str | None = None,
    ) -> dict[str, Any]:
        validate_existing_path(input_path)
        return self.runner.createdb(
            input_path,
            output_db or self._unique_path("foldseek_db", ""),
            prostt5_model=prostt5_model,
        )

    def databases(
        self,
        database_name: str,
        *,
        output_db: str | None = None,
    ) -> dict[str, Any]:
        return self.runner.databases(
            database_name,
            output_db or self._unique_path(database_name, ""),
        )

    def result2msa(
        self,
        query_db: str,
        target_db: str,
        alignment_db: str,
        *,
        output_msa_db: str | None = None,
        msa_format_mode: int | None = None,
    ) -> dict[str, Any]:
        return self.runner.result2msa(
            query_db,
            target_db,
            alignment_db,
            output_msa_db or self._unique_path("foldseek_msa", ""),
            msa_format_mode=msa_format_mode,
        )

    def aln2tmscore(
        self,
        query_db: str,
        target_db: str,
        alignment_db: str,
        *,
        output_db: str | None = None,
    ) -> dict[str, Any]:
        return self.runner.aln2tmscore(
            query_db,
            target_db,
            alignment_db,
            output_db or self._unique_path("foldseek_tmscore", ""),
        )

    def createindex(self, target_db: str) -> dict[str, Any]:
        return self.runner.createindex(target_db)

    def export_hits_json(self, hits, output_path: str) -> str:
        records = hits.to_dict(orient="records")
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
        return output_path
