import pandas as pd


class FoldseekParser:
    def parse(self, result_file):
        columns = ["query", "target", "evalue", "tmscore", "rmsd", "prob"]
        df = pd.read_csv(result_file, sep="\t", names=columns)
        return df

    def top_hits(self, df, topk=10):
        df = df.sort_values(by="tmscore", ascending=False)
        return df.head(topk)
