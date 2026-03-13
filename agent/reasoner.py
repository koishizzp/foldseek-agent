"""LLM-backed result explanation for Foldseek hits."""
from __future__ import annotations

import json
import logging
from typing import Any

try:
    from openai import OpenAI
except Exception:  # noqa: BLE001
    OpenAI = None

from .chat import looks_like_why_question
from .settings import Settings

LOGGER = logging.getLogger(__name__)


class ResultReasoner:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = None
        if settings.openai_api_key:
            if OpenAI is None:
                LOGGER.warning("openai package unavailable; using fallback Foldseek reasoner.")
            else:
                self.client = OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)

    def reply(
        self,
        message: str,
        latest_result: dict[str, Any] | None = None,
        conversation: list[dict[str, str]] | None = None,
        current_mode: str = "search",
        previous_best_target: str | None = None,
    ) -> str:
        fallback = self._fallback_reply(message, latest_result, current_mode, previous_best_target)
        if not self.client:
            return fallback

        payload = {
            "message": message,
            "current_mode": current_mode,
            "previous_best_target": previous_best_target,
            "conversation": conversation or [],
            "latest_result": self._compact_result(latest_result),
        }
        try:
            response = self.client.responses.create(
                model=self.settings.llm_model,
                input=[
                    {
                        "role": "system",
                        "content": (
                            "You are a structural-search copilot. Answer in concise Chinese. "
                            "Ground the answer in the provided Foldseek result. "
                            "If you infer beyond the result object, explicitly label it as 推断. "
                            "Do not overclaim biological or functional meaning from structural similarity alone."
                        ),
                    },
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                ],
            )
            text = (response.output_text or "").strip()
            return text or fallback
        except Exception:  # noqa: BLE001
            LOGGER.exception("Foldseek reasoning request failed; using fallback.")
            return fallback

    def _compact_result(self, latest_result: dict[str, Any] | None) -> dict[str, Any] | None:
        if not latest_result:
            return None
        request = latest_result.get("request") if isinstance(latest_result.get("request"), dict) else {}
        hits = latest_result.get("hits") if isinstance(latest_result.get("hits"), list) else []
        summary = latest_result.get("summary") if isinstance(latest_result.get("summary"), dict) else {}
        return {
            "request": request,
            "summary": summary,
            "top_hits": hits[:6],
            "hit_count": len(hits),
        }

    def _fallback_reply(
        self,
        message: str,
        latest_result: dict[str, Any] | None,
        current_mode: str,
        previous_best_target: str | None,
    ) -> str:
        if not latest_result:
            return "我现在还没有可引用的 Foldseek 检索结果。先执行一次检索，或在请求里附带 latest_result / reasoning_context。"

        hits = latest_result.get("hits") if isinstance(latest_result.get("hits"), list) else []
        request = latest_result.get("request") if isinstance(latest_result.get("request"), dict) else {}
        summary = latest_result.get("summary") if isinstance(latest_result.get("summary"), dict) else {}
        if not hits:
            return f"当前结果为空，数据库 {request.get('database', '-')} 下没有保留下来的命中，因此无法比较优先级。"

        best = hits[0]
        reasons = [
            (
                f"当前最值得优先看的命中是 {best['target']}，因为它在这批结果里排第一："
                f"TM-score={float(best['tmscore']):.4f}，prob={float(best['prob']):.4f}，"
                f"e-value={best['evalue']}，RMSD={float(best['rmsd']):.4f}。"
            )
        ]

        if len(hits) > 1:
            second = hits[1]
            delta_tm = float(best["tmscore"]) - float(second["tmscore"])
            reasons.append(
                f"和第二名 {second['target']} 相比，它的 TM-score 高出 {delta_tm:.4f}。这说明它在当前排序标准下更靠前。"
            )
        else:
            reasons.append("当前只有一条命中保留下来，所以它至少是现有结果里唯一可比的候选。")

        reasons.append(
            f"这次检索来自数据库 {request.get('database', '-')}"
            f"，总计返回 {summary.get('count', len(hits))} 条结果。"
        )

        if previous_best_target and best.get("target") and best["target"] != previous_best_target:
            reasons.append("推断：当前最佳命中已经不同于上一轮上下文里的最佳目标，说明你的筛选条件或查询对象可能发生了有效变化。")

        reasons.append("需要注意，Foldseek 排名只能说明结构相似性更强，不等于功能、活性或实验表现一定更好。")

        if current_mode == "search":
            reasons.append("如果你要继续收敛，我建议下一步直接比较前 3 个 hit 的注释、来源库和局部结构差异。")

        if looks_like_why_question(message):
            return "\n".join(reasons)
        return "\n".join(reasons[:4])
