"""Planner that converts natural language into Foldseek search parameters."""
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

QUOTED_PATH_PATTERN = re.compile(r"""["']([^"']+\.(?:pdb|cif|mmcif|ent))["']""", re.IGNORECASE)
PLAIN_PATH_PATTERN = re.compile(
    r"""((?:[A-Za-z]:\\|/|\.{1,2}[\\/])?[^\s"'`]+?\.(?:pdb|cif|mmcif|ent))""",
    re.IGNORECASE,
)
TOPK_PATTERN = re.compile(r"""(?:top\s*|前)(\d{1,3})""", re.IGNORECASE)
FLOAT_PATTERN = r"""([0-9]*\.?[0-9]+(?:e[-+]?\d+)?)"""
TM_PATTERN = re.compile(rf"""tm(?:-?score)?\s*(?:>=|>|至少|不低于)\s*{FLOAT_PATTERN}""", re.IGNORECASE)
EVALUE_PATTERN = re.compile(rf"""e-?value\s*(?:<=|<|不高于|至多)\s*{FLOAT_PATTERN}""", re.IGNORECASE)
PROB_PATTERN = re.compile(rf"""prob(?:ability)?\s*(?:>=|>|至少|不低于)\s*{FLOAT_PATTERN}""", re.IGNORECASE)


def extract_structure_path(message: str) -> str | None:
    quoted = QUOTED_PATH_PATTERN.search(message)
    if quoted:
        return quoted.group(1).strip()
    plain = PLAIN_PATH_PATTERN.search(message)
    if plain:
        return plain.group(1).strip()
    return None


def _parse_threshold(pattern: re.Pattern[str], message: str) -> float | None:
    match = pattern.search(message)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def _strip_code_fences(text: str) -> str:
    value = text.strip()
    if value.startswith("```"):
        value = re.sub(r"^```(?:json)?", "", value, count=1).strip()
        if value.endswith("```"):
            value = value[:-3].strip()
    return value


class SearchPlanner:
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
        previous_request: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        fallback = self._fallback_plan(message, available_databases, previous_request)
        if not self.client:
            return fallback

        prompt = {
            "task": message,
            "available_databases": available_databases,
            "previous_request": previous_request or {},
            "output_format": {
                "action": "search or clarify",
                "pdb_path": "string or null",
                "database": "string",
                "topk": "int",
                "min_tmscore": "float or null",
                "max_evalue": "float or null",
                "min_prob": "float or null",
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
                            "You convert user requests into Foldseek search parameters. "
                            "Output valid JSON only. If a structure path is missing, set action=clarify "
                            "and needs_input=true."
                        ),
                    },
                    {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
                ],
            )
            raw = _strip_code_fences(response.output_text or "")
            decoded = json.loads(raw)
            return self._sanitize_plan(decoded, message, available_databases, previous_request, fallback)
        except Exception:  # noqa: BLE001
            LOGGER.exception("Foldseek planner failed; using heuristic fallback.")
            return fallback

    def _fallback_plan(
        self,
        message: str,
        available_databases: list[str],
        previous_request: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        previous_request = previous_request or {}
        pdb_path = extract_structure_path(message) or previous_request.get("pdb_path")
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
        min_tmscore = _parse_threshold(TM_PATTERN, message)
        max_evalue = _parse_threshold(EVALUE_PATTERN, message)
        min_prob = _parse_threshold(PROB_PATTERN, message)
        needs_input = not bool(pdb_path)
        question = None
        if needs_input:
            question = "请提供要检索的结构文件路径，例如 /path/to/query.pdb，或直接调用 /search_structure。"
        return {
            "action": "clarify" if needs_input else "search",
            "pdb_path": pdb_path,
            "database": database,
            "topk": topk,
            "min_tmscore": min_tmscore,
            "max_evalue": max_evalue,
            "min_prob": min_prob,
            "needs_input": needs_input,
            "question": question,
        }

    def _infer_database(self, message: str, available_databases: list[str]) -> str | None:
        text = message.lower()
        for name in available_databases:
            if name.lower() in text:
                return name
        return None

    def _sanitize_plan(
        self,
        decoded: dict[str, Any],
        message: str,
        available_databases: list[str],
        previous_request: dict[str, Any] | None,
        fallback: dict[str, Any],
    ) -> dict[str, Any]:
        if not isinstance(decoded, dict):
            return fallback
        previous_request = previous_request or {}
        database = str(decoded.get("database") or fallback["database"] or "").strip()
        if database not in available_databases:
            database = fallback["database"]

        try:
            topk = int(decoded.get("topk", fallback["topk"]))
        except (TypeError, ValueError):
            topk = fallback["topk"]
        topk = max(1, min(topk, 200))

        def normalize_float(name: str) -> float | None:
            value = decoded.get(name)
            if value in (None, ""):
                return fallback.get(name)
            try:
                return float(value)
            except (TypeError, ValueError):
                return fallback.get(name)

        pdb_path = (
            str(decoded.get("pdb_path") or "").strip()
            or extract_structure_path(message)
            or previous_request.get("pdb_path")
        )
        needs_input = bool(decoded.get("needs_input")) or not bool(pdb_path)
        action = str(decoded.get("action") or ("clarify" if needs_input else "search")).strip().lower()
        if action not in {"search", "clarify"}:
            action = "clarify" if needs_input else "search"

        question = decoded.get("question")
        if not isinstance(question, str) or not question.strip():
            question = fallback.get("question")

        return {
            "action": action,
            "pdb_path": pdb_path,
            "database": database,
            "topk": topk,
            "min_tmscore": normalize_float("min_tmscore"),
            "max_evalue": normalize_float("max_evalue"),
            "min_prob": normalize_float("min_prob"),
            "needs_input": needs_input,
            "question": question,
        }
