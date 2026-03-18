"""REST and OpenAI-compatible chat API for Foldseek Agent."""
from __future__ import annotations

from functools import lru_cache
import logging
import os
from pathlib import Path
import re
from secrets import token_hex
import shutil
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from agent.chat import (
    build_chat_completion,
    build_reasoning_context,
    extras_from_latest_result,
    is_reasoning_query,
    latest_user_content,
    normalize_chat_context,
)
from agent.planner import SearchPlanner
from agent.reasoner import ResultReasoner
from agent.service import SearchService
from agent.settings import get_settings

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)
app = FastAPI(title="Foldseek Agent", version="1.3.0")
SAFE_FILENAME_PATTERN = re.compile(r"[^A-Za-z0-9._-]+")
DATABASE_SCAN_MAX_DEPTH = 3
DATABASE_SCAN_LIMIT = 500


@lru_cache(maxsize=1)
def load_chat_ui() -> str:
    return Path(__file__).with_name("chat_ui.html").read_text(encoding="utf-8")


class SearchRequest(BaseModel):
    pdb_path: str = Field(..., description="Path to the query structure file")
    database: str | None = None
    topk: int = Field(default=10, ge=1, le=200)
    min_tmscore: float | None = Field(default=None, ge=0)
    max_evalue: float | None = Field(default=None, ge=0)
    min_prob: float | None = Field(default=None, ge=0)


class EasyClusterRequest(BaseModel):
    input_path: str
    output_prefix: str | None = None
    alignment_type: int | None = None
    coverage: float | None = Field(default=None, ge=0, le=1)


class EasyMultimerSearchRequest(BaseModel):
    pdb_path: str
    database: str
    topk: int = Field(default=10, ge=1, le=200)


class EasyMultimerClusterRequest(BaseModel):
    input_path: str
    output_prefix: str | None = None
    multimer_tmscore: float | None = None
    chain_tmscore: float | None = None
    interface_lddt: float | None = None


class CreateDbRequest(BaseModel):
    input_path: str
    output_db: str | None = None
    prostt5_model: str | None = None


class DownloadDatabaseRequest(BaseModel):
    database_name: str
    output_db: str | None = None


class Result2MsaRequest(BaseModel):
    query_db: str
    target_db: str
    alignment_db: str
    output_msa_db: str | None = None
    msa_format_mode: int | None = None


class Aln2TmScoreRequest(BaseModel):
    query_db: str
    target_db: str
    alignment_db: str
    output_db: str | None = None


class CreateIndexRequest(BaseModel):
    target_db: str


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatReasoningRequest(BaseModel):
    message: str
    conversation: list[ChatMessage] = Field(default_factory=list)
    latest_result: dict[str, Any] | None = None
    current_mode: str = "search"
    previous_best_target: str | None = None


class ChatCompletionRequest(BaseModel):
    model: str | None = None
    messages: list[ChatMessage] = Field(default_factory=list)
    latest_result: dict[str, Any] | None = None
    previous_best_target: str | None = None
    reasoning_context: dict[str, Any] | None = None
    preferred_database: str | None = None


def get_search_service() -> SearchService:
    return SearchService(get_settings())


def get_search_planner() -> SearchPlanner:
    return SearchPlanner(get_settings())


def get_result_reasoner() -> ResultReasoner:
    return ResultReasoner(get_settings())


def get_upload_dir() -> Path:
    settings = get_settings()
    path = Path(settings.upload_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _safe_upload_name(filename: str | None) -> str:
    raw = Path(filename or "upload.bin").name
    sanitized = SAFE_FILENAME_PATTERN.sub("_", raw).strip("._")
    return sanitized or "upload.bin"


def _store_upload(file: UploadFile) -> dict[str, Any]:
    upload_dir = get_upload_dir()
    safe_name = _safe_upload_name(file.filename)
    destination = upload_dir / f"{token_hex(6)}_{safe_name}"
    with destination.open("wb") as handle:
        shutil.copyfileobj(file.file, handle)
    try:
        size = destination.stat().st_size
    finally:
        file.file.close()
    return {
        "filename": safe_name,
        "content_type": file.content_type or "application/octet-stream",
        "path": str(destination.resolve()),
        "size": size,
    }


def _discover_database_candidates(
    root: Path,
    *,
    max_depth: int = DATABASE_SCAN_MAX_DEPTH,
    limit: int = DATABASE_SCAN_LIMIT,
) -> list[dict[str, str]]:
    if not root.exists() or not root.is_dir():
        return []

    results: list[dict[str, str]] = []
    seen_paths: set[str] = set()
    for current_root, dirnames, filenames in os.walk(root):
        current_path = Path(current_root)
        depth = len(current_path.relative_to(root).parts)
        if depth >= max_depth:
            dirnames[:] = []

        for filename in filenames:
            if not filename.endswith(".dbtype"):
                continue
            prefix_path = (current_path / filename).with_suffix("")
            prefix_str = str(prefix_path)
            if prefix_str in seen_paths:
                continue

            try:
                label = prefix_path.relative_to(root).as_posix()
            except ValueError:
                label = prefix_path.name

            results.append({"name": label or prefix_path.name, "path": prefix_str})
            seen_paths.add(prefix_str)
            if len(results) >= limit:
                break

        if len(results) >= limit:
            break

    return sorted(results, key=lambda item: item["name"])


def _wrap(handler):
    try:
        return handler()
    except Exception as exc:
        LOGGER.exception("Foldseek API call failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return load_chat_ui()


@app.get("/chat", response_class=HTMLResponse)
def chat_page() -> str:
    return load_chat_ui()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/foldseek/modules")
def list_modules() -> dict[str, Any]:
    return {"modules": list(SearchService.SUPPORTED_MODULES)}


@app.get("/ui/status")
def ui_status() -> dict[str, Any]:
    def _build_payload() -> dict[str, Any]:
        settings = get_settings()
        return {
            "agent": {"status": "ok", "app_name": settings.app_name},
            "llm": {
                "configured": bool(settings.openai_api_key),
                "model": settings.llm_model,
                "base_url_configured": bool(settings.openai_base_url),
            },
            "foldseek": {
                "binary": settings.foldseek_path,
                "default_database": settings.default_database,
                "available_databases": sorted(settings.databases.keys()),
                "configured_databases": settings.databases,
                "database_scan_roots": settings.database_scan_roots,
                "supported_modules": list(SearchService.SUPPORTED_MODULES),
                "tmp_dir": settings.tmp_dir,
                "result_dir": settings.result_dir,
                "upload_dir": settings.upload_dir,
            },
        }

    return _wrap(_build_payload)


@app.post("/ui/upload")
def upload_file(file: UploadFile = File(...)) -> dict[str, Any]:
    return _wrap(lambda: _store_upload(file))


@app.get("/ui/database_candidates")
def ui_database_candidates(root: str | None = None) -> dict[str, Any]:
    settings = get_settings()
    configured_roots = list(settings.database_scan_roots)
    if not configured_roots:
        return {"roots": [], "selected_root": None, "exists": False, "candidates": []}

    selected_root = root or configured_roots[0]
    if selected_root not in configured_roots:
        raise HTTPException(status_code=400, detail=f"Unknown database scan root: {selected_root}")

    root_path = Path(selected_root)
    exists = root_path.exists() and root_path.is_dir()
    return {
        "roots": configured_roots,
        "selected_root": selected_root,
        "exists": exists,
        "candidates": _discover_database_candidates(root_path) if exists else [],
    }


@app.get("/v1/models")
def list_models() -> dict[str, Any]:
    return {"data": [{"id": "foldseek-search-agent", "object": "model"}]}


@app.post("/search_structure")
def search_structure(req: SearchRequest) -> dict[str, Any]:
    service = get_search_service()
    return _wrap(
        lambda: service.search_structure(
            req.pdb_path,
            database=req.database,
            topk=req.topk,
            min_tmscore=req.min_tmscore,
            max_evalue=req.max_evalue,
            min_prob=req.min_prob,
        )
    )


@app.post("/easy_cluster")
def easy_cluster(req: EasyClusterRequest) -> dict[str, Any]:
    service = get_search_service()
    return _wrap(
        lambda: service.easy_cluster(
            req.input_path,
            output_prefix=req.output_prefix,
            alignment_type=req.alignment_type,
            coverage=req.coverage,
        )
    )


@app.post("/easy_multimersearch")
def easy_multimersearch(req: EasyMultimerSearchRequest) -> dict[str, Any]:
    service = get_search_service()
    return _wrap(lambda: service.multimer_search(req.pdb_path, database=req.database, topk=req.topk))


@app.post("/easy_multimercluster")
def easy_multimercluster(req: EasyMultimerClusterRequest) -> dict[str, Any]:
    service = get_search_service()
    return _wrap(
        lambda: service.easy_multimercluster(
            req.input_path,
            output_prefix=req.output_prefix,
            multimer_tmscore=req.multimer_tmscore,
            chain_tmscore=req.chain_tmscore,
            interface_lddt=req.interface_lddt,
        )
    )


@app.post("/createdb")
def createdb(req: CreateDbRequest) -> dict[str, Any]:
    service = get_search_service()
    return _wrap(
        lambda: service.createdb(
            req.input_path,
            output_db=req.output_db,
            prostt5_model=req.prostt5_model,
        )
    )


@app.post("/databases")
def databases(req: DownloadDatabaseRequest) -> dict[str, Any]:
    service = get_search_service()
    return _wrap(lambda: service.download_database(req.database_name, output_db=req.output_db))


@app.post("/result2msa")
def result2msa(req: Result2MsaRequest) -> dict[str, Any]:
    service = get_search_service()
    return _wrap(
        lambda: service.result2msa(
            req.query_db,
            req.target_db,
            req.alignment_db,
            output_msa_db=req.output_msa_db,
            msa_format_mode=req.msa_format_mode,
        )
    )


@app.post("/aln2tmscore")
def aln2tmscore(req: Aln2TmScoreRequest) -> dict[str, Any]:
    service = get_search_service()
    return _wrap(
        lambda: service.aln2tmscore(
            req.query_db,
            req.target_db,
            req.alignment_db,
            output_db=req.output_db,
        )
    )


@app.post("/createindex")
def createindex(req: CreateIndexRequest) -> dict[str, Any]:
    service = get_search_service()
    return _wrap(lambda: service.createindex(req.target_db))


@app.post("/chat_reasoning")
def chat_reasoning(req: ChatReasoningRequest) -> dict[str, Any]:
    reasoner = get_result_reasoner()
    return _wrap(
        lambda: {
            "reply": reasoner.reply(
                message=req.message,
                latest_result=req.latest_result,
                conversation=[item.model_dump() for item in req.conversation],
                current_mode=req.current_mode,
                previous_best_target=req.previous_best_target,
            )
        }
    )


@app.post("/v1/chat/completions")
def chat_completions(req: ChatCompletionRequest) -> dict[str, Any]:
    content = latest_user_content([item.model_dump() for item in req.messages])
    latest_result, previous_best_target = normalize_chat_context(
        req.latest_result,
        req.previous_best_target,
        req.reasoning_context,
    )

    if is_reasoning_query(content):
        if latest_result:
            reasoner = get_result_reasoner()
            current_mode = str(
                req.reasoning_context.get("current_mode")
                if isinstance(req.reasoning_context, dict)
                else "search"
            )
            reply = reasoner.reply(
                message=content,
                latest_result=latest_result,
                conversation=[item.model_dump() for item in req.messages],
                current_mode=current_mode,
                previous_best_target=previous_best_target,
            )
            extra = extras_from_latest_result(latest_result)
            extra["chat_mode"] = "reasoning"
            extra["reasoning_context"] = build_reasoning_context(
                "reasoning",
                latest_result,
                previous_best_target,
                current_mode=current_mode,
            )
            return build_chat_completion(reply, extra=extra)

        return build_chat_completion(
            "请先执行一次 Foldseek 操作，或在请求里附带 latest_result / reasoning_context 之后再追问。",
            extra={
                "chat_mode": "reasoning",
                "reasoning_context": build_reasoning_context(
                    "reasoning",
                    None,
                    previous_best_target,
                    current_mode="search",
                ),
            },
        )

    planner = get_search_planner()
    service = get_search_service()
    previous_request = latest_result.get("request") if isinstance(latest_result.get("request"), dict) else {}
    plan = planner.plan(
        content,
        service.available_databases(),
        available_modules=service.available_modules(),
        previous_request=previous_request,
        preferred_database=req.preferred_database,
    )
    module = str(plan.get("module") or "easy-search")

    if plan.get("needs_input"):
        return build_chat_completion(
            str(plan.get("question") or "请先补充执行所需的输入参数。"),
            extra={
                "chat_mode": "execution",
                "operation_plan": plan,
                "reasoning_context": build_reasoning_context(
                    "execution",
                    latest_result,
                    previous_best_target,
                    current_mode=module,
                ),
            },
        )

    result = _wrap(lambda: service.execute_plan(plan))
    previous_target = (
        extras_from_latest_result(latest_result)
        .get("best_hit", {})
        .get("target", previous_best_target)
    )
    extra = extras_from_latest_result(result)
    extra["chat_mode"] = "execution"
    extra["operation_plan"] = plan
    extra["operation_result"] = result
    extra["reasoning_context"] = build_reasoning_context(
        "execution",
        result,
        str(previous_target or ""),
        current_mode=module,
    )
    return build_chat_completion(service.format_execution_reply(result), extra=extra)
