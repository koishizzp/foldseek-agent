from __future__ import annotations

from pathlib import Path
import subprocess
from typing import Any


class FoldseekRunner:
    SEARCH_FORMAT = "query,target,evalue,alntmscore,rmsd,prob"
    MULTIMERSEARCH_FORMAT = (
        "query,target,evalue,complexqtmscore,complexttmscore,"
        "qtmscore,ttmscore,interfacelddt,prob"
    )

    def __init__(self, config: dict[str, Any]):
        self.foldseek = config["foldseek_path"]
        self.tmp_dir = config["tmp_dir"]
        self.search_config = config.get("search", {})
        self.cluster_config = config.get("cluster", {})
        self.multimer_config = config.get("multimer", {})
        self.createdb_config = config.get("createdb", {})
        self.postprocess_config = config.get("postprocess", {})

    def _ensure_parent(self, path: str) -> None:
        parent = Path(path).parent
        if str(parent) not in {"", "."}:
            parent.mkdir(parents=True, exist_ok=True)

    def _ensure_tmp_dir(self, tmp_dir: str | None) -> str:
        resolved = tmp_dir or self.tmp_dir
        Path(resolved).mkdir(parents=True, exist_ok=True)
        return resolved

    def _timeout_for(self, section: dict[str, Any], default: int = 600) -> int | None:
        timeout = section.get("timeout_seconds", default)
        return int(timeout) if timeout else None

    def _flag_args(self, options: dict[str, Any]) -> list[str]:
        args: list[str] = []
        for flag, value in options.items():
            if value is None or value is False:
                continue
            if value is True:
                args.append(flag)
                continue
            if isinstance(value, (list, tuple)):
                for item in value:
                    args.extend([flag, str(item)])
                continue
            args.extend([flag, str(value)])
        return args

    def _run(self, module: str, args: list[str], *, timeout: int | None) -> list[str]:
        cmd = [self.foldseek, module, *args]
        print("Running:", " ".join(cmd))
        subprocess.run(cmd, check=True, timeout=timeout)
        return cmd

    def easy_search(
        self,
        query_pdb: str,
        db_path: str,
        out_file: str,
        *,
        tmp_dir: str | None = None,
        format_output: str | None = None,
        max_seqs: int | None = None,
        evalue: str | float | None = None,
    ) -> dict[str, Any]:
        resolved_tmp = self._ensure_tmp_dir(tmp_dir)
        self._ensure_parent(out_file)
        cmd = self._run(
            "easy-search",
            [
                query_pdb,
                db_path,
                out_file,
                resolved_tmp,
                "--format-output",
                format_output or self.SEARCH_FORMAT,
                "--max-seqs",
                str(max_seqs or self.search_config.get("max_seqs", 100)),
                "-e",
                str(evalue or self.search_config.get("evalue", "1e-3")),
            ],
            timeout=self._timeout_for(self.search_config),
        )
        return {
            "module": "easy-search",
            "command": cmd,
            "result_file": out_file,
            "tmp_dir": resolved_tmp,
            "target_path": db_path,
        }

    def search(self, query_pdb: str, db_path: str, out_file: str) -> str:
        result = self.easy_search(query_pdb, db_path, out_file)
        return str(result["result_file"])

    def easy_cluster(
        self,
        input_path: str,
        result_prefix: str,
        *,
        tmp_dir: str | None = None,
        alignment_type: int | None = None,
        coverage: float | None = None,
    ) -> dict[str, Any]:
        resolved_tmp = self._ensure_tmp_dir(tmp_dir)
        self._ensure_parent(result_prefix)
        cmd = self._run(
            "easy-cluster",
            [
                input_path,
                result_prefix,
                resolved_tmp,
                *self._flag_args(
                    {
                        "--alignment-type": alignment_type,
                        "-c": coverage,
                    }
                ),
            ],
            timeout=self._timeout_for(self.cluster_config),
        )
        return {
            "module": "easy-cluster",
            "command": cmd,
            "input_path": input_path,
            "result_prefix": result_prefix,
            "tmp_dir": resolved_tmp,
            "cluster_tsv": f"{result_prefix}_clu.tsv",
            "repseq_fasta": f"{result_prefix}_rep_seq.fasta",
            "allseq_fasta": f"{result_prefix}_all_seqs.fasta",
        }

    def easy_multimersearch(
        self,
        query_pdb: str,
        db_path: str,
        out_file: str,
        *,
        tmp_dir: str | None = None,
        format_output: str | None = None,
        max_seqs: int | None = None,
        evalue: str | float | None = None,
    ) -> dict[str, Any]:
        resolved_tmp = self._ensure_tmp_dir(tmp_dir)
        self._ensure_parent(out_file)
        cmd = self._run(
            "easy-multimersearch",
            [
                query_pdb,
                db_path,
                out_file,
                resolved_tmp,
                "--format-output",
                format_output or self.MULTIMERSEARCH_FORMAT,
                "--max-seqs",
                str(max_seqs or self.multimer_config.get("max_seqs", self.search_config.get("max_seqs", 100))),
                "-e",
                str(evalue or self.multimer_config.get("evalue", self.search_config.get("evalue", "1e-3"))),
            ],
            timeout=self._timeout_for(self.multimer_config, default=self._timeout_for(self.search_config) or 600),
        )
        return {
            "module": "easy-multimersearch",
            "command": cmd,
            "result_file": out_file,
            "report_file": f"{out_file}_report",
            "tmp_dir": resolved_tmp,
            "target_path": db_path,
        }

    def easy_multimercluster(
        self,
        input_path: str,
        result_prefix: str,
        *,
        tmp_dir: str | None = None,
        multimer_tmscore: float | None = None,
        chain_tmscore: float | None = None,
        interface_lddt: float | None = None,
    ) -> dict[str, Any]:
        resolved_tmp = self._ensure_tmp_dir(tmp_dir)
        self._ensure_parent(result_prefix)
        cmd = self._run(
            "easy-multimercluster",
            [
                input_path,
                result_prefix,
                resolved_tmp,
                *self._flag_args(
                    {
                        "--multimer-tm-threshold": multimer_tmscore,
                        "--chain-tm-threshold": chain_tmscore,
                        "--interface-lddt-threshold": interface_lddt,
                    }
                ),
            ],
            timeout=self._timeout_for(self.multimer_config),
        )
        return {
            "module": "easy-multimercluster",
            "command": cmd,
            "input_path": input_path,
            "result_prefix": result_prefix,
            "tmp_dir": resolved_tmp,
            "cluster_tsv": f"{result_prefix}_cluster.tsv",
            "repseq_fasta": f"{result_prefix}_rep_seq.fasta",
            "cluster_report": f"{result_prefix}_cluster_report",
        }

    def createdb(
        self,
        input_path: str,
        output_db: str,
        *,
        prostt5_model: str | None = None,
    ) -> dict[str, Any]:
        self._ensure_parent(output_db)
        cmd = self._run(
            "createdb",
            [
                input_path,
                output_db,
                *self._flag_args({"--prostt5-model": prostt5_model}),
            ],
            timeout=self._timeout_for(self.createdb_config),
        )
        return {
            "module": "createdb",
            "command": cmd,
            "input_path": input_path,
            "output_db": output_db,
        }

    def databases(
        self,
        database_name: str,
        output_db: str,
        *,
        tmp_dir: str | None = None,
    ) -> dict[str, Any]:
        resolved_tmp = self._ensure_tmp_dir(tmp_dir)
        self._ensure_parent(output_db)
        cmd = self._run(
            "databases",
            [database_name, output_db, resolved_tmp],
            timeout=self._timeout_for(self.createdb_config),
        )
        return {
            "module": "databases",
            "command": cmd,
            "database_name": database_name,
            "output_db": output_db,
            "tmp_dir": resolved_tmp,
        }

    def result2msa(
        self,
        query_db: str,
        target_db: str,
        alignment_db: str,
        output_msa_db: str,
        *,
        msa_format_mode: int | None = None,
    ) -> dict[str, Any]:
        self._ensure_parent(output_msa_db)
        cmd = self._run(
            "result2msa",
            [
                query_db,
                target_db,
                alignment_db,
                output_msa_db,
                *self._flag_args(
                    {
                        "--msa-format-mode": msa_format_mode
                        if msa_format_mode is not None
                        else self.postprocess_config.get("msa_format_mode")
                    }
                ),
            ],
            timeout=self._timeout_for(self.postprocess_config),
        )
        return {
            "module": "result2msa",
            "command": cmd,
            "query_db": query_db,
            "target_db": target_db,
            "alignment_db": alignment_db,
            "output_msa_db": output_msa_db,
        }

    def aln2tmscore(
        self,
        query_db: str,
        target_db: str,
        alignment_db: str,
        output_db: str,
    ) -> dict[str, Any]:
        self._ensure_parent(output_db)
        cmd = self._run(
            "aln2tmscore",
            [query_db, target_db, alignment_db, output_db],
            timeout=self._timeout_for(self.postprocess_config),
        )
        return {
            "module": "aln2tmscore",
            "command": cmd,
            "query_db": query_db,
            "target_db": target_db,
            "alignment_db": alignment_db,
            "output_db": output_db,
        }

    def createindex(
        self,
        target_db: str,
        *,
        tmp_dir: str | None = None,
    ) -> dict[str, Any]:
        resolved_tmp = self._ensure_tmp_dir(tmp_dir)
        cmd = self._run(
            "createindex",
            [target_db, resolved_tmp],
            timeout=self._timeout_for(self.createdb_config),
        )
        return {
            "module": "createindex",
            "command": cmd,
            "target_db": target_db,
            "tmp_dir": resolved_tmp,
        }
