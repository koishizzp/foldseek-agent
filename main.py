from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from agent.service import SearchService
from agent.settings import Settings


SUBCOMMANDS = {
    "search",
    "easy-cluster",
    "easy-multimersearch",
    "easy-multimercluster",
    "createdb",
    "databases",
    "result2msa",
    "aln2tmscore",
    "createindex",
    "list-configured-databases",
}


def build_search_parser(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("pdb_file", help="Path to query structure file")
    parser.add_argument("--database", default=None, help="Database name from config or raw database path")
    parser.add_argument("--topk", type=int, default=10, help="Number of top hits")
    parser.add_argument("--min-tmscore", type=float, default=None)
    parser.add_argument("--max-evalue", type=float, default=None)
    parser.add_argument("--min-prob", type=float, default=None)
    parser.add_argument("--json-out", default=None, help="Optional JSON output path")
    parser.add_argument("--summary", action="store_true", help="Print search summary")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Foldseek Agent CLI")
    parser.add_argument("--config", default="config/config.yaml", help="Config yaml path")
    subparsers = parser.add_subparsers(dest="command")

    search = subparsers.add_parser("search", help="Run easy-search")
    build_search_parser(search)

    multimer_search = subparsers.add_parser("easy-multimersearch", help="Run easy-multimersearch")
    multimer_search.add_argument("pdb_file", help="Path to multimer query structure file")
    multimer_search.add_argument("--database", required=True, help="Database name from config or raw database path")
    multimer_search.add_argument("--topk", type=int, default=10)

    easy_cluster = subparsers.add_parser("easy-cluster", help="Run easy-cluster")
    easy_cluster.add_argument("input_path", help="Input file or directory")
    easy_cluster.add_argument("--output-prefix", default=None)
    easy_cluster.add_argument("--alignment-type", type=int, default=None)
    easy_cluster.add_argument("--coverage", type=float, default=None)

    easy_multimercluster = subparsers.add_parser("easy-multimercluster", help="Run easy-multimercluster")
    easy_multimercluster.add_argument("input_path", help="Input file or directory")
    easy_multimercluster.add_argument("--output-prefix", default=None)
    easy_multimercluster.add_argument("--multimer-tmscore", type=float, default=None)
    easy_multimercluster.add_argument("--chain-tmscore", type=float, default=None)
    easy_multimercluster.add_argument("--interface-lddt", type=float, default=None)

    createdb = subparsers.add_parser("createdb", help="Run createdb")
    createdb.add_argument("input_path", help="Input file or directory")
    createdb.add_argument("--output-db", default=None)
    createdb.add_argument("--prostt5-model", default=None)

    databases = subparsers.add_parser("databases", help="Download a prebuilt Foldseek database")
    databases.add_argument("database_name", help="Prebuilt Foldseek database name")
    databases.add_argument("--output-db", default=None)

    result2msa = subparsers.add_parser("result2msa", help="Run result2msa")
    result2msa.add_argument("query_db")
    result2msa.add_argument("target_db")
    result2msa.add_argument("alignment_db")
    result2msa.add_argument("--output-msa-db", default=None)
    result2msa.add_argument("--msa-format-mode", type=int, default=None)

    aln2tmscore = subparsers.add_parser("aln2tmscore", help="Run aln2tmscore")
    aln2tmscore.add_argument("query_db")
    aln2tmscore.add_argument("target_db")
    aln2tmscore.add_argument("alignment_db")
    aln2tmscore.add_argument("--output-db", default=None)

    createindex = subparsers.add_parser("createindex", help="Run createindex")
    createindex.add_argument("target_db")

    subparsers.add_parser("list-configured-databases", help="List configured local database aliases")
    return parser


def build_legacy_search_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Foldseek Agent CLI")
    parser.add_argument("--config", default="config/config.yaml", help="Config yaml path")
    build_search_parser(parser)
    return parser


def _service(config_path: str) -> SearchService:
    settings = Settings.from_env(config_path)
    return SearchService(settings)


def _dump_payload(payload: Any, json_out: str | None = None) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    print(text)
    if json_out:
        with open(json_out, "w", encoding="utf-8") as handle:
            handle.write(text + "\n")


def _run_search(service: SearchService, args: argparse.Namespace) -> None:
    result = service.search_structure(
        args.pdb_file,
        database=args.database,
        topk=args.topk,
        min_tmscore=args.min_tmscore,
        max_evalue=args.max_evalue,
        min_prob=args.min_prob,
    )
    print(json.dumps(result["hits"], ensure_ascii=False, indent=2))
    if args.summary:
        print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
    if args.json_out:
        _dump_payload(result, args.json_out)


def main(argv: list[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] not in SUBCOMMANDS and not argv[0].startswith("-"):
        args = build_legacy_search_parser().parse_args(argv)
        _run_search(_service(args.config), args)
        return

    parser = build_parser()
    args = parser.parse_args(argv)
    service = _service(args.config)

    if args.command in {None, "search"}:
        _run_search(service, args)
        return

    if args.command == "list-configured-databases":
        print("\n".join(service.available_databases()))
        return

    if args.command == "easy-multimersearch":
        _dump_payload(service.multimer_search(args.pdb_file, database=args.database, topk=args.topk))
        return

    if args.command == "easy-cluster":
        _dump_payload(
            service.easy_cluster(
                args.input_path,
                output_prefix=args.output_prefix,
                alignment_type=args.alignment_type,
                coverage=args.coverage,
            )
        )
        return

    if args.command == "easy-multimercluster":
        _dump_payload(
            service.easy_multimercluster(
                args.input_path,
                output_prefix=args.output_prefix,
                multimer_tmscore=args.multimer_tmscore,
                chain_tmscore=args.chain_tmscore,
                interface_lddt=args.interface_lddt,
            )
        )
        return

    if args.command == "createdb":
        _dump_payload(
            service.createdb(
                args.input_path,
                output_db=args.output_db,
                prostt5_model=args.prostt5_model,
            )
        )
        return

    if args.command == "databases":
        _dump_payload(service.download_database(args.database_name, output_db=args.output_db))
        return

    if args.command == "result2msa":
        _dump_payload(
            service.result2msa(
                args.query_db,
                args.target_db,
                args.alignment_db,
                output_msa_db=args.output_msa_db,
                msa_format_mode=args.msa_format_mode,
            )
        )
        return

    if args.command == "aln2tmscore":
        _dump_payload(
            service.aln2tmscore(
                args.query_db,
                args.target_db,
                args.alignment_db,
                output_db=args.output_db,
            )
        )
        return

    if args.command == "createindex":
        _dump_payload(service.createindex(args.target_db))
        return

    parser.error(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    main()
