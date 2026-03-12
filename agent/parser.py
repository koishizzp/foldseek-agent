from __future__ import annotations

import pandas as pd


class FoldseekParser:
    COLUMNS = ["query", "target", "evalue", "tmscore", "rmsd", "prob"]

    def parse(self, result_file: str) -> pd.DataFrame:
        df = pd.read_csv(result_file, sep="\t", names=self.COLUMNS)
        for col in ("evalue", "tmscore", "rmsd", "prob"):
            df[col] = pd.to_numeric(df[col], errors="coerce")
        return df

    def filter_hits(
        self,
        df: pd.DataFrame,
        min_tmscore: float | None = None,
        max_evalue: float | None = None,
        min_prob: float | None = None,
    ) -> pd.DataFrame:
        filtered = df
        if min_tmscore is not None:
            filtered = filtered[filtered["tmscore"] >= min_tmscore]
        if max_evalue is not None:
            filtered = filtered[filtered["evalue"] <= max_evalue]
        if min_prob is not None:
            filtered = filtered[filtered["prob"] >= min_prob]
        return filtered

    def top_hits(self, df: pd.DataFrame, topk: int = 10) -> pd.DataFrame:
        return df.sort_values(by=["tmscore", "prob"], ascending=False).head(topk)

    def summary(self, df: pd.DataFrame) -> dict:
        if df.empty:
            return {
                "count": 0,
                "best_target": None,
                "best_tmscore": None,
                "median_tmscore": None,
                "median_rmsd": None,
            }

        best = df.sort_values(by=["tmscore", "prob"], ascending=False).iloc[0]
        return {
            "count": int(len(df)),
            "best_target": str(best["target"]),
            "best_tmscore": float(best["tmscore"]),
            "median_tmscore": float(df["tmscore"].median()),
            "median_rmsd": float(df["rmsd"].median()),
        }
