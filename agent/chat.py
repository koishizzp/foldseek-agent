"""Helpers for OpenAI-compatible chat handling."""
from __future__ import annotations

from time import time
from typing import Any


def latest_user_content(messages: list[dict[str, Any]] | None) -> str:
    for item in reversed(messages or []):
        if str(item.get("role") or "") == "user":
            return str(item.get("content") or "").strip()
    return ""


def normalize_chat_context(
    latest_result: dict[str, Any] | None,
    previous_best_target: str | None,
    reasoning_context: dict[str, Any] | None,
) -> tuple[dict[str, Any], str]:
    latest_result = latest_result or {}
    previous_best_target = previous_best_target or ""
    reasoning_context = reasoning_context or {}
    if not latest_result and isinstance(reasoning_context.get("latest_result"), dict):
        latest_result = reasoning_context["latest_result"]
    if not previous_best_target and isinstance(reasoning_context.get("previous_best_target"), str):
        previous_best_target = reasoning_context["previous_best_target"]
    return latest_result, previous_best_target


def best_hit_from_result(latest_result: dict[str, Any] | None) -> dict[str, Any]:
    latest_result = latest_result or {}
    summary = latest_result.get("summary")
    if isinstance(summary, dict) and isinstance(summary.get("best_hit"), dict):
        return summary["best_hit"]
    hits = latest_result.get("hits")
    if isinstance(hits, list) and hits and isinstance(hits[0], dict):
        return hits[0]
    return {}


def build_reasoning_context(
    chat_mode: str,
    latest_result: dict[str, Any] | None,
    previous_best_target: str | None,
    *,
    current_mode: str = "search",
) -> dict[str, Any]:
    context = {
        "version": 1,
        "chat_mode": chat_mode,
        "current_mode": current_mode,
        "latest_result": latest_result or {},
        "previous_best_target": previous_best_target or "",
    }
    best_hit = best_hit_from_result(latest_result)
    if best_hit.get("target"):
        context["latest_best_target"] = best_hit["target"]
    return context


def extras_from_latest_result(latest_result: dict[str, Any] | None) -> dict[str, Any]:
    latest_result = latest_result or {}
    summary = latest_result.get("summary") if isinstance(latest_result.get("summary"), dict) else {}
    best_hit = best_hit_from_result(latest_result)
    request = latest_result.get("request") if isinstance(latest_result.get("request"), dict) else {}
    extra: dict[str, Any] = {"module": latest_result.get("module")}
    if best_hit:
        extra["best_hit"] = best_hit
    if summary:
        extra["summary"] = summary
    if request:
        extra["search_request"] = request
        extra["database"] = request.get("database")
    extra["total_hits"] = int(summary.get("count") or len(latest_result.get("hits") or []))
    return extra


def is_reasoning_query(content: str) -> bool:
    text = content.lower().strip()
    if not text:
        return False
    execution_keywords = (
        "search",
        "cluster",
        "createdb",
        "result2msa",
        "aln2tmscore",
        "createindex",
        "检索",
        "聚类",
        "建库",
        "创建数据库",
        "下载数据库",
        "索引",
        "foldseek",
    )
    reasoning_keywords = (
        "why",
        "explain",
        "compare",
        "reason",
        "为什么",
        "解释",
        "比较",
        "分析",
        "哪个更好",
        "哪一个更好",
        "差别",
    )
    if any(keyword in text for keyword in reasoning_keywords):
        return True
    return False if any(keyword in text for keyword in execution_keywords) else False


def looks_like_why_question(content: str) -> bool:
    text = content.lower()
    return any(keyword in text for keyword in ("why", "reason", "为什么", "理由", "解释"))


def build_chat_completion(
    content: str,
    *,
    model: str = "foldseek-search-agent",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": f"chatcmpl-{int(time())}",
        "object": "chat.completion",
        "created": int(time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
    }
    for key, value in (extra or {}).items():
        payload[key] = value
    return payload
