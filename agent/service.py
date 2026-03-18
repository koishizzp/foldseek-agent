"""Structured service layer for Foldseek searches and utilities."""
from __future__ import annotations

import json
from math import isfinite
from pathlib import Path
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

    def execute_plan(self, plan: dict[str, Any]) -> dict[str, Any]:
        module = str(plan.get("module") or "").strip()
        params = dict(plan.get("params") or {})

        if module == "easy-search":
            return self.search_structure(
                params["pdb_path"],
                database=params.get("database"),
                topk=int(params.get("topk") or 10),
                min_tmscore=params.get("min_tmscore"),
                max_evalue=params.get("max_evalue"),
                min_prob=params.get("min_prob"),
                tmp_dir=params.get("tmp_dir"),
                output_path=params.get("output_path"),
            )
        if module == "easy-multimersearch":
            return self.multimer_search(
                params["pdb_path"],
                database=str(params["database"]),
                topk=int(params.get("topk") or 10),
                tmp_dir=params.get("tmp_dir"),
                output_path=params.get("output_path"),
            )
        if module == "easy-cluster":
            return self.easy_cluster(
                params["input_path"],
                output_prefix=params.get("output_prefix"),
                alignment_type=params.get("alignment_type"),
                coverage=params.get("coverage"),
            )
        if module == "easy-multimercluster":
            return self.easy_multimercluster(
                params["input_path"],
                output_prefix=params.get("output_prefix"),
                multimer_tmscore=params.get("multimer_tmscore"),
                chain_tmscore=params.get("chain_tmscore"),
                interface_lddt=params.get("interface_lddt"),
            )
        if module == "createdb":
            return self.createdb(
                params["input_path"],
                output_db=params.get("output_db"),
                prostt5_model=params.get("prostt5_model"),
            )
        if module == "databases":
            return self.download_database(
                params["database_name"],
                output_db=params.get("output_db"),
            )
        if module == "result2msa":
            return self.result2msa(
                params["query_db"],
                params["target_db"],
                params["alignment_db"],
                output_msa_db=params.get("output_msa_db"),
                msa_format_mode=params.get("msa_format_mode"),
            )
        if module == "aln2tmscore":
            return self.aln2tmscore(
                params["query_db"],
                params["target_db"],
                params["alignment_db"],
                output_db=params.get("output_db"),
            )
        if module == "createindex":
            return self.createindex(params["target_db"])

        raise ValueError(f"Unsupported Foldseek module: {module}")

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

    def _resolved_tmp_dir(self, tmp_dir: str | None) -> str:
        return str(tmp_dir or self.settings.tmp_dir)

    def _export_records_json(
        self,
        records: list[dict[str, Any]],
        output_path: str | None,
        *,
        default_name: str,
    ) -> str | None:
        if not output_path:
            return None
        destination = Path(output_path)
        if output_path.endswith(("/", "\\")) or destination.suffix == "":
            destination = destination / default_name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(destination)

    def search_structure(
        self,
        pdb_path: str,
        *,
        database: str | None = None,
        topk: int = 10,
        min_tmscore: float | None = None,
        max_evalue: float | None = None,
        min_prob: float | None = None,
        tmp_dir: str | None = None,
        output_path: str | None = None,
    ) -> dict[str, Any]:
        resolved_database = self._resolve_database(database)
        hits, summary = self.agent.search_with_summary(
            pdb_path,
            database=resolved_database,
            topk=topk,
            min_tmscore=min_tmscore,
            max_evalue=max_evalue,
            min_prob=min_prob,
            tmp_dir=tmp_dir,
        )
        records = self._normalize_records(hits.to_dict(orient="records"))
        exported_output = self._export_records_json(records, output_path, default_name="foldseek_hits.json")
        result = {
            "module": "easy-search",
            "request": {
                "pdb_path": pdb_path,
                "database": resolved_database,
                "topk": int(topk),
                "min_tmscore": min_tmscore,
                "max_evalue": max_evalue,
                "min_prob": min_prob,
                "tmp_dir": self._resolved_tmp_dir(tmp_dir),
            },
            "hits": records,
            "summary": {key: _normalize_number(value) for key, value in summary.items()},
        }
        if exported_output:
            result["output_path"] = exported_output
        result["summary"] = self._summary_with_best_hit(result)
        return result

    def multimer_search(
        self,
        pdb_path: str,
        *,
        database: str,
        topk: int = 10,
        tmp_dir: str | None = None,
        output_path: str | None = None,
    ) -> dict[str, Any]:
        hits, summary = self.agent.multimer_search(pdb_path, database, topk=topk, tmp_dir=tmp_dir)
        records = self._normalize_records(hits.to_dict(orient="records"))
        result = {
            "module": "easy-multimersearch",
            "request": {
                "pdb_path": pdb_path,
                "database": database,
                "topk": int(topk),
                "tmp_dir": self._resolved_tmp_dir(tmp_dir),
            },
            "hits": records,
            "summary": {key: _normalize_number(value) for key, value in summary.items()},
        }
        exported_output = self._export_records_json(records, output_path, default_name="foldseek_multimer_hits.json")
        if exported_output:
            result["output_path"] = exported_output
        return result

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
        module = str(result.get("module") or "easy-search")
        if module == "easy-multimersearch":
            hits = result.get("hits", [])
            if not hits:
                return "已执行 easy-multimersearch，但当前没有保留下来的复合体命中。"
            best = hits[0]
            return (
                f"已完成 easy-multimersearch，最佳复合体命中是 {best['target']}。"
                f" complexqTM={float(best.get('complexqtmscore') or 0):.4f}，"
                f" prob={float(best.get('prob') or 0):.4f}。"
            )

        if module in {"easy-cluster", "easy-multimercluster", "createdb", "databases", "result2msa", "aln2tmscore", "createindex"}:
            artifacts = []
            for key in ("result_prefix", "output_db", "output_msa_db", "cluster_tsv", "repseq_fasta", "allseq_fasta", "target_db"):
                value = result.get(key)
                if value:
                    artifacts.append(f"{key}={value}")
            suffix = f" 产物: {', '.join(artifacts)}。" if artifacts else ""
            return f"已执行 {module}。{suffix}".strip()

        summary = result.get("summary", {})
        hits = result.get("hits", [])
        if not hits:
            database = result.get("request", {}).get("database", "-")
            return f"已执行 Foldseek 检索，但数据库 {database} 下没有结果通过当前过滤条件。"

        best = hits[0]
        lines = [
            (
                f"已完成 Foldseek 检索，最佳命中是 {best['target']} "
                f"(TM-score={float(best['tmscore']):.4f}, prob={float(best['prob']):.4f}, "
                f"e-value={best['evalue']}, RMSD={float(best['rmsd']):.4f})。"
            ),
            (
                f"当前从 {result.get('request', {}).get('database', '-')} 返回 "
                f"{summary.get('count', len(hits))} 条结果，topk={result.get('request', {}).get('topk', len(hits))}。"
            ),
        ]
        if len(hits) > 1:
            preview = ", ".join(
                f"{item['target']}({float(item['tmscore']):.3f})"
                for item in hits[: min(3, len(hits))]
            )
            lines.append(f"前几名命中: {preview}。")
        lines.append("如果要继续问为什么某个命中更值得关注，请带上 latest_result 或 reasoning_context。")
        return "\n".join(lines)
