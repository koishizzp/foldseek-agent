from agent.planner import SearchPlanner
from agent.settings import Settings


def test_fallback_plan_routes_cluster_request():
    planner = SearchPlanner(Settings())
    plan = planner.plan(
        '请对 "/tmp/input_dir" 做聚类',
        available_databases=["afdb50", "pdb"],
        available_modules=[
            "easy-search",
            "easy-cluster",
            "easy-multimersearch",
            "easy-multimercluster",
            "createdb",
            "databases",
            "result2msa",
            "aln2tmscore",
            "createindex",
        ],
    )

    assert plan["module"] == "easy-cluster"
    assert plan["action"] == "execute"
    assert plan["params"]["input_path"] == "/tmp/input_dir"


def test_fallback_plan_requests_missing_result2msa_inputs():
    planner = SearchPlanner(Settings())
    plan = planner.plan(
        "请把结果转成 MSA",
        available_databases=["afdb50"],
        available_modules=["easy-search", "result2msa"],
    )

    assert plan["module"] == "result2msa"
    assert plan["needs_input"] is True


def test_fallback_plan_extracts_bare_path_for_createindex():
    planner = SearchPlanner(Settings())
    plan = planner.plan(
        "为 /tmp/mydb 创建索引",
        available_databases=["afdb50"],
        available_modules=["easy-search", "createindex"],
    )

    assert plan["module"] == "createindex"
    assert plan["action"] == "execute"
    assert plan["params"]["target_db"] == "/tmp/mydb"
