from fastapi.testclient import TestClient

from api.main import app
from agent.settings import Settings


class DummyService:
    def available_databases(self):
        return ["afdb50", "pdb"]

    def available_modules(self):
        return [
            "easy-search",
            "easy-cluster",
            "easy-multimersearch",
            "easy-multimercluster",
            "createdb",
            "databases",
            "result2msa",
            "aln2tmscore",
            "createindex",
        ]

    def search_structure(
        self,
        pdb_path,
        *,
        database=None,
        topk=10,
        min_tmscore=None,
        max_evalue=None,
        min_prob=None,
    ):
        return {
            "module": "easy-search",
            "request": {
                "pdb_path": pdb_path,
                "database": database or "afdb50",
                "topk": topk,
                "min_tmscore": min_tmscore,
                "max_evalue": max_evalue,
                "min_prob": min_prob,
            },
            "hits": [
                {
                    "query": "q1",
                    "target": "hitA",
                    "evalue": 1e-5,
                    "tmscore": 0.91,
                    "rmsd": 1.2,
                    "prob": 0.95,
                }
            ],
            "summary": {
                "count": 1,
                "best_target": "hitA",
                "best_tmscore": 0.91,
                "median_tmscore": 0.91,
                "median_rmsd": 1.2,
                "best_hit": {
                    "query": "q1",
                    "target": "hitA",
                    "evalue": 1e-5,
                    "tmscore": 0.91,
                    "rmsd": 1.2,
                    "prob": 0.95,
                },
            },
        }

    def format_execution_reply(self, result):
        if result.get("module") == "createindex":
            return "indexed"
        return f"best={result['summary']['best_target']}"

    def multimer_search(self, pdb_path, *, database, topk=10):
        return {
            "module": "easy-multimersearch",
            "request": {"pdb_path": pdb_path, "database": database, "topk": topk},
            "hits": [{"query": "q1", "target": "multiA", "complexqtmscore": 0.88, "prob": 0.93}],
            "summary": {"count": 1, "best_target": "multiA", "best_complexqtmscore": 0.88},
        }

    def easy_cluster(self, input_path, *, output_prefix=None, alignment_type=None, coverage=None):
        return {
            "module": "easy-cluster",
            "input_path": input_path,
            "result_prefix": output_prefix or "/tmp/cluster",
            "alignment_type": alignment_type,
            "coverage": coverage,
        }

    def easy_multimercluster(
        self,
        input_path,
        *,
        output_prefix=None,
        multimer_tmscore=None,
        chain_tmscore=None,
        interface_lddt=None,
    ):
        return {
            "module": "easy-multimercluster",
            "input_path": input_path,
            "result_prefix": output_prefix or "/tmp/mcluster",
        }

    def createdb(self, input_path, *, output_db=None, prostt5_model=None):
        return {
            "module": "createdb",
            "input_path": input_path,
            "output_db": output_db or "/tmp/db",
            "prostt5_model": prostt5_model,
        }

    def download_database(self, database_name, *, output_db=None):
        return {
            "module": "databases",
            "database_name": database_name,
            "output_db": output_db or "/tmp/downloaded_db",
        }

    def result2msa(self, query_db, target_db, alignment_db, *, output_msa_db=None, msa_format_mode=None):
        return {
            "module": "result2msa",
            "query_db": query_db,
            "target_db": target_db,
            "alignment_db": alignment_db,
            "output_msa_db": output_msa_db or "/tmp/msa_db",
            "msa_format_mode": msa_format_mode,
        }

    def aln2tmscore(self, query_db, target_db, alignment_db, *, output_db=None):
        return {
            "module": "aln2tmscore",
            "query_db": query_db,
            "target_db": target_db,
            "alignment_db": alignment_db,
            "output_db": output_db or "/tmp/tmscore_db",
        }

    def createindex(self, target_db):
        return {"module": "createindex", "target_db": target_db}

    def execute_plan(self, plan):
        module = plan["module"]
        params = plan["params"]
        if module == "easy-search":
            return self.search_structure(
                params["pdb_path"],
                database=params.get("database"),
                topk=params.get("topk", 10),
                min_tmscore=params.get("min_tmscore"),
                max_evalue=params.get("max_evalue"),
                min_prob=params.get("min_prob"),
            )
        if module == "createindex":
            return self.createindex(params["target_db"])
        raise AssertionError(f"unexpected module {module}")


class DummyPlanner:
    def __init__(self, plan):
        self._plan = plan
        self.calls = []

    def plan(
        self,
        message,
        available_databases,
        available_modules=None,
        previous_request=None,
        preferred_database=None,
    ):
        self.calls.append(
            {
                "message": message,
                "available_databases": list(available_databases),
                "available_modules": list(available_modules or []),
                "previous_request": dict(previous_request or {}),
                "preferred_database": preferred_database,
            }
        )
        return dict(self._plan)


class DummyReasoner:
    def reply(self, **kwargs):
        return "reasoned"


def test_search_structure_endpoint(monkeypatch):
    monkeypatch.setattr("api.main.get_search_service", lambda: DummyService())
    client = TestClient(app)

    response = client.post(
        "/search_structure",
        json={"pdb_path": "/tmp/query.pdb", "database": "afdb50", "topk": 3},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["best_target"] == "hitA"


def test_home_returns_html():
    client = TestClient(app)
    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Foldseek Agent 工作台" in response.text


def test_upload_endpoint(monkeypatch, tmp_path):
    settings = Settings(upload_dir=str(tmp_path / "uploads"))
    monkeypatch.setattr("api.main.get_settings", lambda: settings)
    client = TestClient(app)

    response = client.post(
        "/ui/upload",
        files={"file": ("query.pdb", b"HEADER TEST\n", "chemical/x-pdb")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["filename"] == "query.pdb"
    assert payload["path"].endswith("query.pdb")
    assert (tmp_path / "uploads").exists()


def test_chat_completions_execution(monkeypatch):
    monkeypatch.setattr("api.main.get_search_service", lambda: DummyService())
    planner = DummyPlanner(
        {
            "action": "execute",
            "module": "easy-search",
            "params": {
                "pdb_path": "/tmp/query.pdb",
                "database": "afdb50",
                "topk": 5,
                "min_tmscore": 0.8,
                "max_evalue": None,
                "min_prob": None,
            },
            "needs_input": False,
            "question": None,
        }
    )
    monkeypatch.setattr("api.main.get_search_planner", lambda: planner)
    client = TestClient(app)

    response = client.post(
        "/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "search /tmp/query.pdb top5"}]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["chat_mode"] == "execution"
    assert payload["best_hit"]["target"] == "hitA"
    assert payload["choices"][0]["message"]["content"] == "best=hitA"
    assert payload["operation_plan"]["module"] == "easy-search"
    assert planner.calls[0]["preferred_database"] is None


def test_chat_completions_passes_preferred_database(monkeypatch):
    monkeypatch.setattr("api.main.get_search_service", lambda: DummyService())
    planner = DummyPlanner(
        {
            "action": "execute",
            "module": "easy-search",
            "params": {
                "pdb_path": "/tmp/query.pdb",
                "database": "/mnt/db/custom",
                "topk": 5,
                "min_tmscore": None,
                "max_evalue": None,
                "min_prob": None,
            },
            "needs_input": False,
            "question": None,
        }
    )
    monkeypatch.setattr("api.main.get_search_planner", lambda: planner)
    client = TestClient(app)

    response = client.post(
        "/v1/chat/completions",
        json={
            "messages": [{"role": "user", "content": "search /tmp/query.pdb"}],
            "preferred_database": "/mnt/db/custom",
        },
    )

    assert response.status_code == 200
    assert planner.calls[0]["preferred_database"] == "/mnt/db/custom"


def test_chat_completions_reasoning(monkeypatch):
    monkeypatch.setattr("api.main.get_result_reasoner", lambda: DummyReasoner())
    client = TestClient(app)
    latest_result = DummyService().search_structure("/tmp/query.pdb")

    response = client.post(
        "/v1/chat/completions",
        json={
            "messages": [{"role": "user", "content": "why is the first hit better?"}],
            "latest_result": latest_result,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["chat_mode"] == "reasoning"
    assert payload["choices"][0]["message"]["content"] == "reasoned"


def test_modules_endpoint():
    client = TestClient(app)

    response = client.get("/foldseek/modules")

    assert response.status_code == 200
    payload = response.json()
    assert "createindex" in payload["modules"]


def test_ui_status_contains_upload_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "api.main.get_settings",
        lambda: Settings(
            upload_dir=str(tmp_path / "uploads"),
            databases={"afdb50": "/tmp/afdb50"},
            database_scan_roots=[str(tmp_path / "db_scan")],
        ),
    )
    client = TestClient(app)

    response = client.get("/ui/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["foldseek"]["upload_dir"] == str(tmp_path / "uploads")
    assert payload["foldseek"]["available_databases"] == ["afdb50"]
    assert payload["foldseek"]["database_scan_roots"] == [str(tmp_path / "db_scan")]


def test_ui_database_candidates_lists_detected_prefixes(monkeypatch, tmp_path):
    root = tmp_path / "db_scan"
    root.mkdir()
    (root / "afdb50.dbtype").write_text("", encoding="utf-8")
    nested = root / "nested"
    nested.mkdir()
    (nested / "pdb.dbtype").write_text("", encoding="utf-8")

    monkeypatch.setattr(
        "api.main.get_settings",
        lambda: Settings(database_scan_roots=[str(root)]),
    )
    client = TestClient(app)

    response = client.get("/ui/database_candidates", params={"root": str(root)})

    assert response.status_code == 200
    payload = response.json()
    assert payload["selected_root"] == str(root)
    assert payload["exists"] is True
    assert payload["candidates"] == [
        {"name": "afdb50", "path": str(root / "afdb50")},
        {"name": "nested/pdb", "path": str(root / "nested" / "pdb")},
    ]


def test_ui_database_candidates_rejects_unknown_root(monkeypatch, tmp_path):
    allowed_root = tmp_path / "allowed"
    allowed_root.mkdir()
    monkeypatch.setattr(
        "api.main.get_settings",
        lambda: Settings(database_scan_roots=[str(allowed_root)]),
    )
    client = TestClient(app)

    response = client.get("/ui/database_candidates", params={"root": str(tmp_path / "other")})

    assert response.status_code == 400
    assert "Unknown database scan root" in response.json()["detail"]


def test_ui_status_returns_error_detail_when_settings_fail(monkeypatch):
    monkeypatch.setattr(
        "api.main.get_settings",
        lambda: (_ for _ in ()).throw(ValueError("bad settings")),
    )
    client = TestClient(app)

    response = client.get("/ui/status")

    assert response.status_code == 500
    assert response.json()["detail"] == "bad settings"


def test_easy_cluster_endpoint(monkeypatch):
    monkeypatch.setattr("api.main.get_search_service", lambda: DummyService())
    client = TestClient(app)

    response = client.post(
        "/easy_cluster",
        json={"input_path": "/tmp/input_dir", "output_prefix": "/tmp/out", "alignment_type": 1, "coverage": 0.9},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["module"] == "easy-cluster"
    assert payload["alignment_type"] == 1


def test_createindex_endpoint(monkeypatch):
    monkeypatch.setattr("api.main.get_search_service", lambda: DummyService())
    client = TestClient(app)

    response = client.post("/createindex", json={"target_db": "/tmp/db"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["module"] == "createindex"


def test_chat_completions_createindex_execution(monkeypatch):
    monkeypatch.setattr("api.main.get_search_service", lambda: DummyService())
    monkeypatch.setattr(
        "api.main.get_search_planner",
        lambda: DummyPlanner(
            {
                "action": "execute",
                "module": "createindex",
                "params": {"target_db": "/tmp/db"},
                "needs_input": False,
                "question": None,
            }
        ),
    )
    client = TestClient(app)

    response = client.post(
        "/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "create index for /tmp/db"}]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["chat_mode"] == "execution"
    assert payload["operation_plan"]["module"] == "createindex"
    assert payload["choices"][0]["message"]["content"] == "indexed"
