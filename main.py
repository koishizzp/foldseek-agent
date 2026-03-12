from __future__ import annotations

import argparse
import json

from agent.foldseek_agent import FoldseekAgent


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Foldseek Agent CLI")
    parser.add_argument("pdb_file", help="Path to query PDB file")
    parser.add_argument("--config", default="config/config.yaml", help="Config yaml path")
    parser.add_argument("--database", default="afdb50", help="Database name from config")
    parser.add_argument("--topk", type=int, default=10, help="Number of top hits")
    parser.add_argument("--min-tmscore", type=float, default=None)
    parser.add_argument("--max-evalue", type=float, default=None)
    parser.add_argument("--min-prob", type=float, default=None)
    parser.add_argument("--json-out", default=None, help="Optional path to export hits as JSON")
    parser.add_argument("--summary", action="store_true", help="Print hit summary")
    parser.add_argument("--list-databases", action="store_true", help="List configured database names and exit")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    agent = FoldseekAgent(args.config)

    if args.list_databases:
        print("\n".join(agent.available_databases()))
        return

    hits, summary = agent.search_with_summary(
        args.pdb_file,
        database=args.database,
        topk=args.topk,
        min_tmscore=args.min_tmscore,
        max_evalue=args.max_evalue,
        min_prob=args.min_prob,
    )
    print(hits)

    if args.summary:
        print(json.dumps(summary, indent=2))

    if args.json_out:
        exported = agent.export_hits_json(hits, args.json_out)
        print(f"Exported hits to {exported}")


if __name__ == "__main__":
    main()
