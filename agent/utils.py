from __future__ import annotations

from pathlib import Path
from typing import Iterable


REQUIRED_CONFIG_KEYS = ("foldseek_path", "databases", "tmp_dir")


def ensure_dir(path: str | Path) -> str:
    Path(path).mkdir(parents=True, exist_ok=True)
    return str(path)


def validate_config(config: dict) -> None:
    missing = [key for key in REQUIRED_CONFIG_KEYS if key not in config]
    if missing:
        raise ValueError(f"Missing required config key(s): {', '.join(missing)}")

    if not isinstance(config.get("databases"), dict):
        raise ValueError("`databases` must be a dictionary of name -> path")


def validate_database_name(database: str, allowed: Iterable[str]) -> None:
    if database not in allowed:
        available = ", ".join(sorted(allowed))
        raise KeyError(f"Unknown database `{database}`. Available databases: {available}")


def validate_query_path(path: str | Path) -> None:
    query_path = Path(path)
    if not query_path.exists():
        raise FileNotFoundError(f"Query structure file does not exist: {query_path}")
    if not query_path.is_file():
        raise ValueError(f"Query structure path is not a file: {query_path}")


def validate_existing_path(path: str | Path) -> None:
    target_path = Path(path)
    if not target_path.exists():
        raise FileNotFoundError(f"Path does not exist: {target_path}")
