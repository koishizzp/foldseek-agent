from __future__ import annotations

import os
import subprocess


class FoldseekRunner:
    def __init__(self, config: dict):
        self.foldseek = config["foldseek_path"]
        self.tmp_dir = config["tmp_dir"]
        self.search_config = config.get("search", {})

    def _build_command(self, query_pdb: str, db_path: str, out_file: str) -> list[str]:
        return [
            self.foldseek,
            "easy-search",
            query_pdb,
            db_path,
            out_file,
            self.tmp_dir,
            "--format-output",
            "query,target,evalue,alntmscore,rmsd,prob",
            "--max-seqs",
            str(self.search_config.get("max_seqs", 100)),
            "-e",
            str(self.search_config.get("evalue", "1e-3")),
        ]

    def search(self, query_pdb: str, db_path: str, out_file: str) -> str:
        os.makedirs(self.tmp_dir, exist_ok=True)
        os.makedirs(os.path.dirname(out_file) or ".", exist_ok=True)

        cmd = self._build_command(query_pdb, db_path, out_file)
        print("Running:", " ".join(cmd))

        timeout = self.search_config.get("timeout_seconds")
        subprocess.run(cmd, check=True, timeout=timeout)
        return out_file
