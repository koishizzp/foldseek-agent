from agent.planner import SearchPlanner
from agent.settings import Settings


def test_fallback_plan_routes_cluster_request():
    planner = SearchPlanner(Settings())
    plan = planner.plan(
        'please cluster "/tmp/input_dir"',
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
        "convert search results to MSA",
        available_databases=["afdb50"],
        available_modules=["easy-search", "result2msa"],
    )

    assert plan["module"] == "result2msa"
    assert plan["needs_input"] is True


def test_fallback_plan_extracts_bare_path_for_createindex():
    planner = SearchPlanner(Settings())
    plan = planner.plan(
        "create index for /tmp/mydb",
        available_databases=["afdb50"],
        available_modules=["easy-search", "createindex"],
    )

    assert plan["module"] == "createindex"
    assert plan["action"] == "execute"
    assert plan["params"]["target_db"] == "/tmp/mydb"


def test_fallback_plan_accepts_raw_database_path_for_search():
    planner = SearchPlanner(Settings())
    plan = planner.plan(
        "search /tmp/query.pdb against /mnt/db/custom top5",
        available_databases=["afdb50"],
        available_modules=["easy-search"],
    )

    assert plan["module"] == "easy-search"
    assert plan["action"] == "execute"
    assert plan["params"]["pdb_path"] == "/tmp/query.pdb"
    assert plan["params"]["database"] == "/mnt/db/custom"


def test_fallback_plan_prefers_explicit_database_selection():
    planner = SearchPlanner(Settings())
    plan = planner.plan(
        "search /tmp/query.pdb",
        available_databases=["afdb50"],
        available_modules=["easy-search"],
        preferred_database="/mnt/db/custom",
    )

    assert plan["module"] == "easy-search"
    assert plan["action"] == "execute"
    assert plan["params"]["database"] == "/mnt/db/custom"


def test_fallback_plan_extracts_tmp_dir_and_output_path():
    planner = SearchPlanner(Settings())
    plan = planner.plan(
        "easy-search /tmp/query.pdb against afdb50 top8 tmp_dir=/tmp/foldseek output=/tmp/hits.json",
        available_databases=["afdb50"],
        available_modules=["easy-search"],
    )

    assert plan["module"] == "easy-search"
    assert plan["action"] == "execute"
    assert plan["params"]["tmp_dir"] == "/tmp/foldseek"
    assert plan["params"]["output_path"] == "/tmp/hits.json"
