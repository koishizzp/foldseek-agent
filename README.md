# Foldseek Agent

Foldseek Agent is a server-oriented Python wrapper around Foldseek. It keeps the useful architecture patterns from `D:\esm3-agent\esm3-agent`:

- env-based configuration
- OpenAI-compatible LLM integration
- FastAPI service layer
- OpenAI-style `POST /v1/chat/completions`
- result reasoning with `latest_result` and `reasoning_context`

It does not copy unrelated parts such as training data, surrogate models, ESM3 services, or GFP workflows.

## Supported Foldseek modules

This repo now covers the agreed 8+1 module set:

1. `easy-search`
2. `easy-cluster`
3. `easy-multimersearch`
4. `easy-multimercluster`
5. `createdb`
6. `databases`
7. `result2msa`
8. `aln2tmscore`
9. `createindex`

The command syntax follows the official Foldseek documentation:

- [Foldseek README](https://github.com/steineggerlab/foldseek)

## Repository layout

```text
agent/
  foldseek_agent.py   # high-level Foldseek operations
  runner.py           # subprocess wrapper for the 8+1 modules
  parser.py           # tabular result parsing
  service.py          # structured service layer
  settings.py         # .env / env / yaml settings
  planner.py          # NL -> easy-search parameters
  reasoner.py         # follow-up ranking explanation
  chat.py             # OpenAI-style chat helpers

api/
  main.py             # FastAPI app

config/
  config.yaml         # default server-side config

main.py               # CLI entrypoint
start_agent.sh        # Linux startup helper
start_all.sh          # managed startup with log/PID/health wait
stop_all.sh           # managed shutdown
status_all.sh         # managed status inspection
restart.sh            # restart helper
smoke_test.sh         # API smoke test
```

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Configuration

Default config file: `config/config.yaml`

It is already aligned with your target server root:

```yaml
foldseek_root: /mnt/disk3/tio_nekton4/foldseek
foldseek_path: foldseek
default_database: afdb50
```

Database prefixes, temp directories, and result directories can be set either in YAML or via environment variables.

### Reused OpenAI-compatible variables

The repo accepts the same LLM variables as `esm3-agent`:

```bash
OPENAI_API_KEY=...
OPENAI_BASE_URL=...
OPENAI_MODEL=gpt-4o-mini
```

### Foldseek Agent variables

See `.env.example`. The important ones are:

```bash
FOLDSEEK_AGENT_API_HOST=0.0.0.0
FOLDSEEK_AGENT_API_PORT=8000
FOLDSEEK_AGENT_CONFIG=config/config.yaml

FOLDSEEK_AGENT_FOLDSEEK_ROOT=/mnt/disk3/tio_nekton4/foldseek
FOLDSEEK_AGENT_FOLDSEEK_PATH=foldseek
FOLDSEEK_AGENT_DEFAULT_DATABASE=afdb50
FOLDSEEK_AGENT_DATABASES_JSON='{"afdb50":"/mnt/disk3/tio_nekton4/foldseek/<afdb50_db_path>"}'
FOLDSEEK_AGENT_TMP_DIR=/mnt/disk3/tio_nekton4/foldseek/tmp
FOLDSEEK_AGENT_RESULT_DIR=/mnt/disk3/tio_nekton4/foldseek/results
FOLDSEEK_AGENT_BASE_URL=http://127.0.0.1:8000
FOLDSEEK_AGENT_API_LOG=logs/foldseek-agent.log
FOLDSEEK_AGENT_API_PID_FILE=logs/foldseek-agent.pid
```

## CLI

Legacy search mode is still supported:

```bash
python main.py /abs/path/query.pdb --database afdb50 --topk 10 --summary
```

Configured database aliases:

```bash
python main.py --config config/config.yaml list-configured-databases
```

Subcommands for the 8+1 module set:

```bash
python main.py search /abs/path/query.pdb --database afdb50 --topk 5
python main.py easy-cluster /abs/path/input_dir --output-prefix /abs/path/out/cluster
python main.py easy-multimersearch /abs/path/query.pdb --database afdb50 --topk 5
python main.py easy-multimercluster /abs/path/input_dir --output-prefix /abs/path/out/mcluster
python main.py createdb /abs/path/input_dir --output-db /abs/path/db/mydb
python main.py databases afdb50 --output-db /abs/path/db/afdb50
python main.py result2msa queryDB targetDB alnDB --output-msa-db msaDB --msa-format-mode 6
python main.py aln2tmscore queryDB targetDB alnDB --output-db tmscoreDB
python main.py createindex /abs/path/db/mydb
```

## API

Start the API:

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

or:

```bash
./start_agent.sh
```

Managed service scripts:

```bash
chmod +x start_all.sh stop_all.sh status_all.sh restart.sh start.sh stop.sh status.sh
./start_all.sh
./status_all.sh
./stop_all.sh
./restart.sh
```

Health and status:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/ui/status
curl http://127.0.0.1:8000/foldseek/modules
```

### Search-style endpoints

```bash
curl -X POST http://127.0.0.1:8000/search_structure \
  -H "Content-Type: application/json" \
  -d '{
    "pdb_path": "/abs/path/query.pdb",
    "database": "afdb50",
    "topk": 5,
    "min_tmscore": 0.6
  }'
```

```bash
curl -X POST http://127.0.0.1:8000/easy_multimersearch \
  -H "Content-Type: application/json" \
  -d '{
    "pdb_path": "/abs/path/query_multimer.pdb",
    "database": "afdb50",
    "topk": 5
  }'
```

### Utility/module endpoints

```bash
curl -X POST http://127.0.0.1:8000/easy_cluster \
  -H "Content-Type: application/json" \
  -d '{"input_path":"/abs/path/input_dir","output_prefix":"/abs/path/out/cluster"}'

curl -X POST http://127.0.0.1:8000/easy_multimercluster \
  -H "Content-Type: application/json" \
  -d '{"input_path":"/abs/path/input_dir","output_prefix":"/abs/path/out/mcluster"}'

curl -X POST http://127.0.0.1:8000/createdb \
  -H "Content-Type: application/json" \
  -d '{"input_path":"/abs/path/input_dir","output_db":"/abs/path/db/mydb"}'

curl -X POST http://127.0.0.1:8000/databases \
  -H "Content-Type: application/json" \
  -d '{"database_name":"afdb50","output_db":"/abs/path/db/afdb50"}'

curl -X POST http://127.0.0.1:8000/result2msa \
  -H "Content-Type: application/json" \
  -d '{"query_db":"queryDB","target_db":"targetDB","alignment_db":"alnDB","output_msa_db":"msaDB","msa_format_mode":6}'

curl -X POST http://127.0.0.1:8000/aln2tmscore \
  -H "Content-Type: application/json" \
  -d '{"query_db":"queryDB","target_db":"targetDB","alignment_db":"alnDB","output_db":"tmscoreDB"}'

curl -X POST http://127.0.0.1:8000/createindex \
  -H "Content-Type: application/json" \
  -d '{"target_db":"/abs/path/db/mydb"}'
```

### OpenAI-compatible chat endpoint

This endpoint is still centered on `easy-search` for natural-language requests:

```bash
curl -X POST http://127.0.0.1:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "foldseek-search-agent",
    "messages": [
      {
        "role": "user",
        "content": "Use afdb50 to search /abs/path/query.pdb and return top 5 hits"
      }
    ]
  }'
```

For follow-up ranking questions, pass back the previous `reasoning_context`.

## Server deployment

Recommended layout after you move this repo to the server:

1. repo root: `/mnt/disk3/tio_nekton4/foldseek-agent`
2. Foldseek deployment root: `/mnt/disk3/tio_nekton4/foldseek`
3. `.env` points `FOLDSEEK_AGENT_FOLDSEEK_ROOT` to `/mnt/disk3/tio_nekton4/foldseek`
4. LLM access reuses the same `OPENAI_*` variables as `esm3-agent`

## Smoke test

```bash
./smoke_test.sh
```

If you also set `FOLDSEEK_AGENT_SMOKE_PDB_PATH`, the script will exercise `/search_structure` too.

## Ops scripts

This repo is a single-service deployment, so `start_all.sh` means "start the Foldseek Agent API stack":

```bash
./start_all.sh
```

It will:

1. load `.env` if present
2. create `logs/`
3. start `start_agent.sh` in background
4. write PID to `logs/foldseek-agent.pid`
5. wait for `/health`

Status:

```bash
./status_all.sh
```

Stop:

```bash
./stop_all.sh
```

Short wrappers are also provided:

```bash
./start.sh
./status.sh
./stop.sh
```

## Tests

```bash
pytest -q
```

Current coverage includes:

- search parsing and filtering
- settings loading
- API endpoints
- command construction for new modules
