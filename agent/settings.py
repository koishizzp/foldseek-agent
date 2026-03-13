"""Environment-aware runtime settings for Foldseek Agent."""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
import json
import os
from pathlib import Path
from typing import Any

import yaml


def _load_env_file(path: str = ".env") -> dict[str, str]:
    env: dict[str, str] = {}
    file_path = Path(path)
    if not file_path.exists():
        return env

    for raw_line in file_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def _env_source() -> dict[str, str]:
    data = _load_env_file()
    data.update(os.environ)
    return data


def _env_get(data: dict[str, str], name: str, default: str | None = None) -> str | None:
    return data.get(name, default)


def _env_get_first(data: dict[str, str], names: list[str], default: str | None = None) -> str | None:
    for name in names:
        if name in data:
            return data[name]
    return default


def _to_int(value: str | None, default: int) -> int:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _to_optional_str(value: str | None, default: str | None = None) -> str | None:
    if value is None:
        return default
    cleaned = value.strip()
    return cleaned if cleaned else default


def _load_yaml_config(path: str) -> dict[str, Any]:
    config_path = Path(path)
    if not config_path.exists():
        return {}
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        return raw
    return {}


def _resolve_path(value: str | None, *, root: str | None, base_dir: Path) -> str | None:
    if value is None:
        return None
    candidate = Path(value)
    if candidate.is_absolute():
        return str(candidate)
    if root:
        return str(Path(root) / candidate)
    return str(base_dir / candidate)


def _resolve_tool_path(value: str | None, *, root: str | None) -> str | None:
    if value is None:
        return None
    if "/" not in value and "\\" not in value and not value.startswith("."):
        return value
    candidate = Path(value)
    if candidate.is_absolute():
        return str(candidate)
    if root:
        return str(Path(root) / candidate)
    return str(candidate)


def _parse_databases(
    value: Any,
    *,
    root: str | None,
    base_dir: Path,
) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, str] = {}
    for key, raw_path in value.items():
        if not isinstance(key, str) or not isinstance(raw_path, str):
            continue
        resolved = _resolve_path(raw_path, root=root, base_dir=base_dir)
        if resolved:
            result[key] = resolved
    return result


@dataclass(slots=True)
class Settings:
    app_name: str = "Foldseek Agent"
    log_level: str = "INFO"
    llm_model: str = "gpt-4o-mini"
    openai_api_key: str | None = None
    openai_base_url: str | None = None
    request_timeout: int = 120

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    config_path: str = "config/config.yaml"

    foldseek_root: str | None = None
    foldseek_path: str = "foldseek"
    tmp_dir: str = "./tmp"
    result_dir: str = "./results"
    upload_dir: str = "./uploads"
    default_database: str = "afdb50"
    databases: dict[str, str] = field(default_factory=dict)
    extra_config: dict[str, Any] = field(default_factory=dict)

    search_max_seqs: int = 100
    search_evalue: str = "1e-3"
    search_timeout_seconds: int = 600

    @classmethod
    def from_env(cls, config_path_override: str | None = None) -> "Settings":
        data = _env_source()
        defaults = cls()
        config_path = config_path_override or _env_get(data, "FOLDSEEK_AGENT_CONFIG", defaults.config_path) or defaults.config_path
        config_path_obj = Path(config_path)
        yaml_config = _load_yaml_config(config_path)
        config_dir = config_path_obj.parent if config_path_obj.parent != Path("") else Path.cwd()

        foldseek_root = _to_optional_str(
            _env_get(data, "FOLDSEEK_AGENT_FOLDSEEK_ROOT"),
            _to_optional_str(yaml_config.get("foldseek_root")) if isinstance(yaml_config, dict) else None,
        )

        databases = _parse_databases(yaml_config.get("databases", {}), root=foldseek_root, base_dir=config_dir)
        raw_databases_json = _to_optional_str(_env_get(data, "FOLDSEEK_AGENT_DATABASES_JSON"))
        if raw_databases_json:
            decoded = json.loads(raw_databases_json)
            databases = _parse_databases(decoded, root=foldseek_root, base_dir=config_dir)

        search_config = yaml_config.get("search", {}) if isinstance(yaml_config.get("search"), dict) else {}
        extra_sections = {
            name: dict(yaml_config.get(name, {}))
            for name in ("cluster", "multimer", "createdb", "postprocess")
            if isinstance(yaml_config.get(name), dict)
        }

        return cls(
            app_name=_env_get(data, "FOLDSEEK_AGENT_APP_NAME", defaults.app_name) or defaults.app_name,
            log_level=_env_get(data, "FOLDSEEK_AGENT_LOG_LEVEL", defaults.log_level) or defaults.log_level,
            llm_model=_env_get_first(data, ["FOLDSEEK_AGENT_LLM_MODEL", "OPENAI_MODEL"], defaults.llm_model)
            or defaults.llm_model,
            openai_api_key=_to_optional_str(
                _env_get_first(data, ["FOLDSEEK_AGENT_OPENAI_API_KEY", "OPENAI_API_KEY"])
            ),
            openai_base_url=_to_optional_str(
                _env_get_first(data, ["FOLDSEEK_AGENT_OPENAI_BASE_URL", "OPENAI_BASE_URL"])
            ),
            request_timeout=_to_int(_env_get(data, "FOLDSEEK_AGENT_REQUEST_TIMEOUT"), defaults.request_timeout),
            api_host=_env_get(data, "FOLDSEEK_AGENT_API_HOST", defaults.api_host) or defaults.api_host,
            api_port=_to_int(_env_get(data, "FOLDSEEK_AGENT_API_PORT"), defaults.api_port),
            config_path=config_path,
            foldseek_root=foldseek_root,
            foldseek_path=_resolve_tool_path(
                _env_get(data, "FOLDSEEK_AGENT_FOLDSEEK_PATH", yaml_config.get("foldseek_path", defaults.foldseek_path))
                or defaults.foldseek_path,
                root=foldseek_root,
            )
            or defaults.foldseek_path,
            tmp_dir=_resolve_path(
                _env_get(data, "FOLDSEEK_AGENT_TMP_DIR", yaml_config.get("tmp_dir", defaults.tmp_dir)),
                root=foldseek_root,
                base_dir=config_dir,
            )
            or defaults.tmp_dir,
            result_dir=_resolve_path(
                _env_get(data, "FOLDSEEK_AGENT_RESULT_DIR", yaml_config.get("result_dir", defaults.result_dir)),
                root=foldseek_root,
                base_dir=config_dir,
            )
            or defaults.result_dir,
            upload_dir=_resolve_path(
                _env_get(data, "FOLDSEEK_AGENT_UPLOAD_DIR", yaml_config.get("upload_dir", defaults.upload_dir)),
                root=foldseek_root,
                base_dir=config_dir,
            )
            or defaults.upload_dir,
            default_database=_env_get(
                data,
                "FOLDSEEK_AGENT_DEFAULT_DATABASE",
                yaml_config.get("default_database", defaults.default_database),
            )
            or defaults.default_database,
            databases=databases,
            extra_config=extra_sections,
            search_max_seqs=_to_int(
                _env_get(
                    data,
                    "FOLDSEEK_AGENT_SEARCH_MAX_SEQS",
                    str(search_config.get("max_seqs", defaults.search_max_seqs)),
                ),
                defaults.search_max_seqs,
            ),
            search_evalue=str(
                _env_get(
                    data,
                    "FOLDSEEK_AGENT_SEARCH_EVALUE",
                    str(search_config.get("evalue", defaults.search_evalue)),
                )
                or defaults.search_evalue
            ),
            search_timeout_seconds=_to_int(
                _env_get(
                    data,
                    "FOLDSEEK_AGENT_SEARCH_TIMEOUT",
                    str(search_config.get("timeout_seconds", defaults.search_timeout_seconds)),
                ),
                defaults.search_timeout_seconds,
            ),
        )

    def to_agent_config(self) -> dict[str, Any]:
        return {
            "foldseek_root": self.foldseek_root,
            "foldseek_path": self.foldseek_path,
            "databases": self.databases,
            "tmp_dir": self.tmp_dir,
            "result_dir": self.result_dir,
            "upload_dir": self.upload_dir,
            "default_database": self.default_database,
            "search": {
                "max_seqs": self.search_max_seqs,
                "evalue": self.search_evalue,
                "timeout_seconds": self.search_timeout_seconds,
            },
            **self.extra_config,
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.from_env()
