"""LLM-backed planner for Foldseek module routing."""
from __future__ import annotations

import json
import logging
import re
from typing import Any

try:
    from openai import OpenAI
except Exception:  # noqa: BLE001
    OpenAI = None

from .settings import Settings

LOGGER = logging.getLogger(__name__)

STRUCTURE_PATH_PATTERN = re.compile(r"""["']?((?:[A-Za-z]:\\|/|\.{1,2}[\\/])?[^\s"'`]+?\.(?:pdb|cif|mmcif|ent))["']?""", re.IGNORECASE)
GENERIC_PATH_PATTERN = re.compile(r"""["']((?:[^"']*[\\/][^"']*|[^"']+\.db[^"']*))["']""")
BARE_PATH_PATTERN = re.compile(r"""((?:[A-Za-z]:\\|/|\.{1,2}[\\/])\S+)""")
TOPK_PATTERN = re.compile(r"""(?:top\s*|前\s*)(\d{1,3})""", re.IGNORECASE)
FLOAT_PATTERN = r"""([0-9]*\.?[0-9]+(?:e[-+]?\d+)?)"""
TM_PATTERN = re.compile(rf"""tm(?:-?score)?\s*(?:>=|>|至少|不低于)\s*{FLOAT_PATTERN}""", re.IGNORECASE)
EVALUE_PATTERN = re.compile(rf"""e-?value\s*(?:<=|<|不高于|至多)\s*{FLOAT_PATTERN}""", re.IGNORECASE)
PROB_PATTERN = re.compile(rf"""prob(?:ability)?\s*(?:>=|>|至少|不低于)\s*{FLOAT_PATTERN}""", re.IGNORECASE)

MODULE_HINTS = {
    "easy-multimercluster": ("multimercluster", "easy-multimercluster", "multimer cluster", "复合物聚类", "多聚体聚类"),
    "easy-multimersearch": ("multimersearch", "easy-multimersearch", "multimer search", "复合物搜索", "多聚体搜索"),
    "easy-cluster": ("easy-cluster", "cluster", "聚类"),
    "createdb": ("createdb", "create db", "创建数据库", "建库"),
    "databases": ("download database", "download databases", "databases", "下载数据库"),
    "result2msa": ("result2msa", "msa", "多序列比对", "生成msa"),
    "aln2tmscore": ("aln2tmscore", "tmscore", "tm score 重评分", "重算tmscore"),
    "createindex": ("createindex", "create index", "建立索引", "创建索引"),
    "easy-search": ("easy-search", "search", "检索", "查找", "foldseek"),
}


def _strip_code_fences(text: str) -> str:
    value = text.strip()
    if value.startswith("```"):
        value = re.sub(r"^```(?:json)?", "", value, count=1).strip()
        if value.endswith("```"):
            value = value[:-3].strip()
    return value


def _extract_structure_paths(message: str) -> list[str]:
    return [item.group(1).strip() for item in STRUCTURE_PATH_PATTERN.finditer(message)]


def _extract_generic_paths(message: str) -> list[str]:
    values = [item.group(1).strip() for item in GENERIC_PATH_PATTERN.finditer(message)]
    values.extend(item.group(1).strip().rstrip(".,);") for item in BARE_PATH_PATTERN.finditer(message))
    values.extend(_extract_structure_paths(message))
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped


def _parse_threshold(pattern: re.Pattern[str], message: str) -> float | None:
    match = pattern.search(message)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


class SearchPlanner:
    """Natural-language planner for routing user requests to Foldseek modules."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = None
        if settings.openai_api_key:
            if OpenAI is None:
                LOGGER.warning("openai package unavailable; using heuristic Foldseek planner.")
            else:
                self.client = OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)

    def plan(
        self,
        message: str,
        available_databases: list[str],
        available_modules: list[str] | None = None,
        previous_request: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        modules = available_modules or list(MODULE_HINTS)
        fallback = self._fallback_plan(message, available_databases, modules, previous_request)
        if not self.client:
            return fallback

        prompt = {
            "task": message,
            "available_databases": available_databases,
            "available_modules": modules,
            "previous_request": previous_request or {},
            "output_format": {
                "action": "execute or clarify",
                "module": "one of available_modules",
                "params": "object",
                "needs_input": "bool",
                "question": "string or null",
            },
        }
        try:
            response = self.client.responses.create(
                model=self.settings.llm_model,
                input=[
                    {
                        "role": "system",
                        "content": (
                            "You route natural-language requests to Foldseek modules. "
                            "Use only the provided module names. Output valid JSON only. "
                            "If required inputs are missing, set action=clarify and needs_input=true."
                        ),
                    },
                    {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
                ],
            )
            raw = _strip_code_fences(response.output_text or "")
            decoded = json.loads(raw)
            return self._sanitize_plan(decoded, message, available_databases, modules, previous_request, fallback)
        except Exception:  # noqa: BLE001
            LOGGER.exception("Foldseek planner failed; using heuristic fallback.")
            return fallback

    def _fallback_plan(
        self,
        message: str,
        available_databases: list[str],
        available_modules: list[str],
        previous_request: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        previous_request = previous_request or {}
        module = self._infer_module(message, available_modules)
        generic_paths = _extract_generic_paths(message)
        structure_paths = _extract_structure_paths(message)
        database = self._infer_database(message, available_databases) or previous_request.get("database")
        if database not in available_databases:
            database = (
                self.settings.default_database
                if self.settings.default_database in available_databases
                else (available_databases[0] if available_databases else "")
            )

        topk_match = TOPK_PATTERN.search(message.lower())
        topk = int(topk_match.group(1)) if topk_match else int(previous_request.get("topk") or 10)
        topk = max(1, min(topk, 200))

        params: dict[str, Any] = {}
        question: str | None = None

        if module == "easy-search":
            pdb_path = structure_paths[0] if structure_paths else previous_request.get("pdb_path")
            params = {
                "pdb_path": pdb_path,
                "database": database,
                "topk": topk,
                "min_tmscore": _parse_threshold(TM_PATTERN, message),
                "max_evalue": _parse_threshold(EVALUE_PATTERN, message),
                "min_prob": _parse_threshold(PROB_PATTERN, message),
            }
            if not pdb_path:
                question = "请提供要检索的结构文件路径，例如 /path/to/query.pdb。"

        elif module == "easy-multimersearch":
            pdb_path = structure_paths[0] if structure_paths else None
            params = {"pdb_path": pdb_path, "database": database, "topk": topk}
            if not pdb_path:
                question = "请提供复合体结构文件路径，例如 /path/to/query_multimer.pdb。"

        elif module in {"easy-cluster", "easy-multimercluster", "createdb", "createindex"}:
            input_path = generic_paths[0] if generic_paths else None
            if module == "easy-cluster":
                params = {"input_path": input_path}
            elif module == "easy-multimercluster":
                params = {"input_path": input_path}
            elif module == "createdb":
                output_db = generic_paths[1] if len(generic_paths) > 1 else None
                params = {"input_path": input_path, "output_db": output_db}
            else:
                params = {"target_db": input_path}
            if not input_path:
                question = "请提供输入路径。比如输入目录、结构文件路径，或数据库前缀路径。"

        elif module == "databases":
            params = {"database_name": database or None}
            if not params["database_name"]:
                question = "请说明要下载哪个 Foldseek 预构建数据库，例如 afdb50 或 pdb。"

        elif module in {"result2msa", "aln2tmscore"}:
            items = generic_paths[:3]
            params = {
                "query_db": items[0] if len(items) > 0 else None,
                "target_db": items[1] if len(items) > 1 else None,
                "alignment_db": items[2] if len(items) > 2 else None,
            }
            if module == "result2msa":
                params["msa_format_mode"] = 6
            if len(items) < 3:
                question = "请提供 query_db、target_db 和 alignment_db 三个路径或前缀。"

        needs_input = question is not None
        return {
            "action": "clarify" if needs_input else "execute",
            "module": module,
            "params": params,
            "needs_input": needs_input,
            "question": question,
        }

    def _infer_database(self, message: str, available_databases: list[str]) -> str | None:
        text = message.lower()
        for name in available_databases:
            if name.lower() in text:
                return name
        return None

    def _infer_module(self, message: str, available_modules: list[str]) -> str:
        text = message.lower()
        for module in (
            "easy-multimercluster",
            "easy-multimersearch",
            "easy-cluster",
            "createdb",
            "databases",
            "result2msa",
            "aln2tmscore",
            "createindex",
            "easy-search",
        ):
            if module not in available_modules:
                continue
            if any(keyword in text for keyword in MODULE_HINTS.get(module, ())):
                return module
        return "easy-search" if "easy-search" in available_modules else available_modules[0]

    def _sanitize_plan(
        self,
        decoded: dict[str, Any],
        message: str,
        available_databases: list[str],
        available_modules: list[str],
        previous_request: dict[str, Any] | None,
        fallback: dict[str, Any],
    ) -> dict[str, Any]:
        if not isinstance(decoded, dict):
            return fallback
        module = str(decoded.get("module") or fallback["module"]).strip()
        if module not in available_modules:
            module = fallback["module"]
        params = decoded.get("params") if isinstance(decoded.get("params"), dict) else dict(fallback["params"])
        question = decoded.get("question")
        needs_input = bool(decoded.get("needs_input"))
        action = str(decoded.get("action") or ("clarify" if needs_input else "execute")).strip().lower()
        if action not in {"execute", "clarify"}:
            action = fallback["action"]
        if not isinstance(question, str) or not question.strip():
            question = fallback.get("question")

        if module in {"easy-search", "easy-multimersearch"}:
            database = str(params.get("database") or fallback["params"].get("database") or "").strip()
            if database not in available_databases:
                database = fallback["params"].get("database")
            params["database"] = database
            try:
                params["topk"] = max(1, min(int(params.get("topk", fallback["params"].get("topk", 10))), 200))
            except (TypeError, ValueError):
                params["topk"] = fallback["params"].get("topk", 10)

        if module == "easy-search":
            for name in ("min_tmscore", "max_evalue", "min_prob"):
                value = params.get(name)
                if value in (None, ""):
                    params[name] = fallback["params"].get(name)
                else:
                    try:
                        params[name] = float(value)
                    except (TypeError, ValueError):
                        params[name] = fallback["params"].get(name)

        if module in {"easy-search", "easy-multimersearch"} and not params.get("pdb_path"):
            needs_input = True
            action = "clarify"
            question = question or fallback.get("question") or "请提供结构文件路径。"

        if module in {"easy-cluster", "easy-multimercluster", "createdb"} and not params.get("input_path"):
            needs_input = True
            action = "clarify"

        if module == "createindex" and not params.get("target_db"):
            needs_input = True
            action = "clarify"

        if module == "databases" and not params.get("database_name"):
            needs_input = True
            action = "clarify"

        if module in {"result2msa", "aln2tmscore"}:
            required = ("query_db", "target_db", "alignment_db")
            if any(not params.get(name) for name in required):
                needs_input = True
                action = "clarify"

        return {
            "action": action,
            "module": module,
            "params": params,
            "needs_input": needs_input,
            "question": question,
        }
