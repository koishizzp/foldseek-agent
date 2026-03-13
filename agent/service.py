"""Structured service layer for Foldseek searches and utilities."""
from __future__ import annotations

from math import isfinite
from typing import Any

from .foldseek_agent import FoldseekAgent
from .settings import Settings, get_settings


def _normalize_number(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not isfinite(value):
            return None
        return value
    return value


class SearchService:
    SUPPORTED_MODULES = [
        "easy-search",
        "easy-cluster",
        "easy-multimersearch",
        "easy-multimercluster",
        "createdb",
        "databases",
        "result2msa",
        "aln2tmscore",
        "createindex",
    ]

    def __init__(
        self,
        settings: Settings | None = None,
        search_agent: FoldseekAgent | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.agent = search_agent or FoldseekAgent(self.settings.to_agent_config())

    def available_databases(self) -> list[str]:
        return self.agent.available_databases()

    def available_modules(self) -> list[str]:
        return list(self.SUPPORTED_MODULES)

    def _resolve_database(self, database: str | None) -> str:
        available = self.available_databases()
        if database:
            return database
        if self.settings.default_database in available:
            return self.settings.default_database
        if not available:
            raise ValueError("No Foldseek databases are configured")
        return available[0]

    def _summary_with_best_hit(self, result: dict[str, Any]) -> dict[str, Any]:
        summary = dict(result["summary"])
        hits = result["hits"]
        summary["best_hit"] = hits[0] if hits else None
        return summary

    def _normalize_records(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {key: _normalize_number(value) for key, value in record.items()}
            for record in records
        ]

    def _normalize_operation(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            key: [str(item) for item in value] if key == "command" else _normalize_number(value)
            for key, value in payload.items()
        }

    def search_structure(
        self,
        pdb_path: str,
        *,
        database: str | None = None,
        topk: int = 10,
        min_tmscore: float | None = None,
        max_evalue: float | None = None,
        min_prob: float | None = None,
    ) -> dict[str, Any]:
        resolved_database = self._resolve_database(database)
        hits, summary = self.agent.search_with_summary(
            pdb_path,
            database=resolved_database,
            topk=topk,
            min_tmscore=min_tmscore,
            max_evalue=max_evalue,
            min_prob=min_prob,
        )
        records = self._normalize_records(hits.to_dict(orient="records"))
        result = {
            "module": "easy-search",
            "request": {
                "pdb_path": pdb_path,
                "database": resolved_database,
                "topk": int(topk),
                "min_tmscore": min_tmscore,
                "max_evalue": max_evalue,
                "min_prob": min_prob,
            },
            "hits": records,
            "summary": {key: _normalize_number(value) for key, value in summary.items()},
        }
        result["summary"] = self._summary_with_best_hit(result)
        return result

    def multimer_search(
        self,
        pdb_path: str,
        *,
        database: str,
        topk: int = 10,
    ) -> dict[str, Any]:
        hits, summary = self.agent.multimer_search(pdb_path, database, topk=topk)
        records = self._normalize_records(hits.to_dict(orient="records"))
        return {
            "module": "easy-multimersearch",
            "request": {
                "pdb_path": pdb_path,
                "database": database,
                "topk": int(topk),
            },
            "hits": records,
            "summary": {key: _normalize_number(value) for key, value in summary.items()},
        }

    def easy_cluster(
        self,
        input_path: str,
        *,
        output_prefix: str | None = None,
        alignment_type: int | None = None,
        coverage: float | None = None,
    ) -> dict[str, Any]:
        return self._normalize_operation(
            self.agent.easy_cluster(
                input_path,
                output_prefix=output_prefix,
                alignment_type=alignment_type,
                coverage=coverage,
            )
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
        return self._normalize_operation(
            self.agent.easy_multimercluster(
                input_path,
                output_prefix=output_prefix,
                multimer_tmscore=multimer_tmscore,
                chain_tmscore=chain_tmscore,
                interface_lddt=interface_lddt,
            )
        )

    def createdb(
        self,
        input_path: str,
        *,
        output_db: str | None = None,
        prostt5_model: str | None = None,
    ) -> dict[str, Any]:
        return self._normalize_operation(
            self.agent.createdb(
                input_path,
                output_db=output_db,
                prostt5_model=prostt5_model,
            )
        )

    def download_database(
        self,
        database_name: str,
        *,
        output_db: str | None = None,
    ) -> dict[str, Any]:
        return self._normalize_operation(self.agent.databases(database_name, output_db=output_db))

    def result2msa(
        self,
        query_db: str,
        target_db: str,
        alignment_db: str,
        *,
        output_msa_db: str | None = None,
        msa_format_mode: int | None = None,
    ) -> dict[str, Any]:
        return self._normalize_operation(
            self.agent.result2msa(
                query_db,
                target_db,
                alignment_db,
                output_msa_db=output_msa_db,
                msa_format_mode=msa_format_mode,
            )
        )

    def aln2tmscore(
        self,
        query_db: str,
        target_db: str,
        alignment_db: str,
        *,
        output_db: str | None = None,
    ) -> dict[str, Any]:
        return self._normalize_operation(
            self.agent.aln2tmscore(
                query_db,
                target_db,
                alignment_db,
                output_db=output_db,
            )
        )

    def createindex(self, target_db: str) -> dict[str, Any]:
        return self._normalize_operation(self.agent.createindex(target_db))

    def format_execution_reply(self, result: dict[str, Any]) -> str:
        summary = result.get("summary", {})
        hits = result.get("hits", [])
        if not hits:
            database = result.get("request", {}).get("database", "-")
            return f"Foldseek search finished, but no hits passed the filters in database {database}."

        best = hits[0]
        lines = [
            (
                f"Foldseek search finished. Best hit: {best['target']} "
                f"(TM-score={float(best['tmscore']):.4f}, prob={float(best['prob']):.4f}, "
                f"e-value={best['evalue']}, RMSD={float(best['rmsd']):.4f})."
            ),
            (
                f"Returned {summary.get('count', len(hits))} hits from "
                f"{result.get('request', {}).get('database', '-')}, topk={result.get('request', {}).get('topk', len(hits))}."
            ),
        ]
        if len(hits) > 1:
            preview = ", ".join(
                f"{item['target']}({float(item['tmscore']):.3f})"
                for item in hits[: min(3, len(hits))]
            )
            lines.append(f"Top hits: {preview}.")
        lines.append("Ask a follow-up with latest_result or reasoning_context if you want a ranking explanation.")
        return "\n".join(lines)
