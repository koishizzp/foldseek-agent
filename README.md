# Foldseek Agent

这是一个面向服务器部署的 Foldseek Python Agent。它参考了 `D:\esm3-agent\esm3-agent` 里真正有用的架构部分：

- 基于环境变量和 `.env` 的配置加载
- OpenAI 兼容 LLM 接入
- FastAPI 服务层
- OpenAI 风格的 `POST /v1/chat/completions`
- 基于 `latest_result` 和 `reasoning_context` 的结果解释
- 浏览器工作台
- 文件上传到服务器后直接复用

没有照搬无关内容，比如训练数据、surrogate、ESM3 服务、GFP 专用工作流。

## 已支持的 Foldseek 模块

当前仓库已经覆盖 8+1 模块：

1. `easy-search`
2. `easy-cluster`
3. `easy-multimersearch`
4. `easy-multimercluster`
5. `createdb`
6. `databases`
7. `result2msa`
8. `aln2tmscore`
9. `createindex`

命令语义对齐 Foldseek 官方文档：

- [Foldseek README](https://github.com/steineggerlab/foldseek)

## 目录结构

```text
agent/
  foldseek_agent.py   # Foldseek 高层操作封装
  runner.py           # 8+1 模块的 subprocess 封装
  parser.py           # 表格结果解析
  service.py          # 结构化服务层
  settings.py         # .env / 环境变量 / yaml 配置
  planner.py          # 自然语言 -> Foldseek 模块与参数
  reasoner.py         # 结果追问解释
  chat.py             # OpenAI 风格 chat 辅助函数

api/
  main.py             # FastAPI 应用入口
  chat_ui.html        # 浏览器工作台

config/
  config.yaml         # 默认服务器配置

main.py               # CLI 入口
start_agent.sh        # 直接启动 API
start_all.sh          # 带日志/PID/健康检查等待的启动脚本
stop_all.sh           # 停止脚本
status_all.sh         # 状态检查脚本
restart.sh            # 重启脚本
smoke_test.sh         # API 冒烟测试
```

## 安装

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

注意：上传接口依赖 `python-multipart`，已经包含在 `requirements.txt` 里。

## 配置

默认配置文件是 `config/config.yaml`。

它已经按你的目标服务器路径预设：

```yaml
foldseek_root: /mnt/disk3/tio_nekton4/foldseek
foldseek_path: foldseek
default_database: afdb50
```

数据库前缀、临时目录、结果目录、上传目录，既可以在 YAML 里配置，也可以通过环境变量覆盖。

### 与 `esm3-agent` 复用的 LLM 变量

这个仓库支持和 `esm3-agent` 一样的 OpenAI 兼容变量：

```bash
OPENAI_API_KEY=...
OPENAI_BASE_URL=...
OPENAI_MODEL=gpt-4o-mini
```

### Foldseek Agent 自己的变量

完整示例见 `.env.example`，重点变量如下：

```bash
FOLDSEEK_AGENT_API_HOST=0.0.0.0
FOLDSEEK_AGENT_API_PORT=8100
FOLDSEEK_AGENT_CONFIG=config/config.yaml

FOLDSEEK_AGENT_FOLDSEEK_ROOT=/mnt/disk3/tio_nekton4/foldseek
FOLDSEEK_AGENT_FOLDSEEK_PATH=foldseek
FOLDSEEK_AGENT_DEFAULT_DATABASE=afdb50
FOLDSEEK_AGENT_DATABASES_JSON='{"afdb50":"/mnt/disk3/tio_nekton4/foldseek/<afdb50_db_path>"}'
FOLDSEEK_AGENT_TMP_DIR=/mnt/disk3/tio_nekton4/foldseek/tmp
FOLDSEEK_AGENT_RESULT_DIR=/mnt/disk3/tio_nekton4/foldseek/results
FOLDSEEK_AGENT_UPLOAD_DIR=/mnt/disk3/tio_nekton4/foldseek-agent/uploads
FOLDSEEK_AGENT_BASE_URL=http://127.0.0.1:8100
FOLDSEEK_AGENT_API_LOG=logs/foldseek-agent.log
FOLDSEEK_AGENT_API_PID_FILE=logs/foldseek-agent.pid
```

## CLI 用法

旧的搜索模式仍然可用：

```bash
python main.py /abs/path/query.pdb --database afdb50 --topk 10 --summary
```

列出已配置的数据库别名：

```bash
python main.py --config config/config.yaml list-configured-databases
```

8+1 模块对应的子命令：

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

## API 用法

启动 API：

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8100
```

Port note: keep Foldseek Agent on `8100` so it does not conflict with `esm3-agent`, which now reserves `8000` for its canonical Python Agent API.

或者：

```bash
./start_agent.sh
```

如果希望用带日志、PID、健康检查等待的托管脚本：

```bash
chmod +x start_all.sh stop_all.sh status_all.sh restart.sh start.sh stop.sh status.sh
./start_all.sh
./status_all.sh
./stop_all.sh
./restart.sh
```

健康检查与状态接口：

```bash
curl http://127.0.0.1:8100/health
curl http://127.0.0.1:8100/ui/status
curl http://127.0.0.1:8100/foldseek/modules
```

### 搜索类接口

```bash
curl -X POST http://127.0.0.1:8100/search_structure \
  -H "Content-Type: application/json" \
  -d '{
    "pdb_path": "/abs/path/query.pdb",
    "database": "afdb50",
    "topk": 5,
    "min_tmscore": 0.6
  }'
```

```bash
curl -X POST http://127.0.0.1:8100/easy_multimersearch \
  -H "Content-Type: application/json" \
  -d '{
    "pdb_path": "/abs/path/query_multimer.pdb",
    "database": "afdb50",
    "topk": 5
  }'
```

### 工具类接口

```bash
curl -X POST http://127.0.0.1:8100/easy_cluster \
  -H "Content-Type: application/json" \
  -d '{"input_path":"/abs/path/input_dir","output_prefix":"/abs/path/out/cluster"}'

curl -X POST http://127.0.0.1:8100/easy_multimercluster \
  -H "Content-Type: application/json" \
  -d '{"input_path":"/abs/path/input_dir","output_prefix":"/abs/path/out/mcluster"}'

curl -X POST http://127.0.0.1:8100/createdb \
  -H "Content-Type: application/json" \
  -d '{"input_path":"/abs/path/input_dir","output_db":"/abs/path/db/mydb"}'

curl -X POST http://127.0.0.1:8100/databases \
  -H "Content-Type: application/json" \
  -d '{"database_name":"afdb50","output_db":"/abs/path/db/afdb50"}'

curl -X POST http://127.0.0.1:8100/result2msa \
  -H "Content-Type: application/json" \
  -d '{"query_db":"queryDB","target_db":"targetDB","alignment_db":"alnDB","output_msa_db":"msaDB","msa_format_mode":6}'

curl -X POST http://127.0.0.1:8100/aln2tmscore \
  -H "Content-Type: application/json" \
  -d '{"query_db":"queryDB","target_db":"targetDB","alignment_db":"alnDB","output_db":"tmscoreDB"}'

curl -X POST http://127.0.0.1:8100/createindex \
  -H "Content-Type: application/json" \
  -d '{"target_db":"/abs/path/db/mydb"}'
```

### 上传接口

如果你想先把本地文件传到服务器，再把服务器路径用于聊天或模块执行，可以直接调用：

```bash
curl -X POST http://127.0.0.1:8100/ui/upload \
  -F "file=@/local/path/query.pdb"
```

返回结果里会包含服务器绝对路径，例如：

```json
{
  "filename": "query.pdb",
  "content_type": "chemical/x-pdb",
  "path": "/mnt/disk3/tio_nekton4/foldseek-agent/uploads/abc123_query.pdb",
  "size": 12345
}
```

### OpenAI 兼容聊天接口

这个入口现在会优先用 LLM/启发式规则把自然语言路由到 8+1 模块中的合适操作。

例如：

- “用 afdb50 检索 /abs/path/query.pdb，返回前 5 个结果”
- “为 /abs/path/db/mydb 创建索引”
- “把 /abs/path/input_dir 做聚类”
- “下载 afdb50 数据库到 /abs/path/db/afdb50”

请求示例：

```bash
curl -X POST http://127.0.0.1:8100/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "foldseek-search-agent",
    "messages": [
      {
        "role": "user",
        "content": "用 afdb50 检索 /abs/path/query.pdb，返回前 5 个结果"
      }
    ]
  }'
```

如果继续追问排序原因，传回上一轮的 `reasoning_context` 即可。

## 浏览器工作台

服务启动后，直接访问：

```text
http://服务器IP:8100/
```

页面里有三块：

1. 左侧 `LLM Chat`
   - 用自然语言调用 Foldseek 模块
   - 搜索后继续追问时自动带上下文
2. 右侧 `Direct Module Runner`
   - 直接选择模块并发送 JSON
   - 适合 `createdb`、`result2msa`、`createindex` 这种精确执行场景
3. 上方 `文件上传`
   - 把本地文件上传到服务器
   - 返回服务器绝对路径
   - 一键插入聊天框或当前模块 JSON

## 服务器部署建议

后续你把仓库迁到服务器时，建议按这个布局：

1. 仓库根目录：`/mnt/disk3/tio_nekton4/foldseek-agent`
2. Foldseek 部署根目录：`/mnt/disk3/tio_nekton4/foldseek`
3. `.env` 里把 `FOLDSEEK_AGENT_FOLDSEEK_ROOT` 指向 `/mnt/disk3/tio_nekton4/foldseek`
4. LLM 继续复用和 `esm3-agent` 相同的 `OPENAI_*` 变量
5. 建议单独给 `FOLDSEEK_AGENT_UPLOAD_DIR` 预留一个可写目录

## 冒烟测试

```bash
./smoke_test.sh
```

如果设置了 `FOLDSEEK_AGENT_SMOKE_PDB_PATH`，脚本还会顺带调用 `/search_structure`。

## 运维脚本说明

这个仓库是单服务部署，所以 `start_all.sh` 的含义是“启动 Foldseek Agent API 整套服务”：

```bash
./start_all.sh
```

它会做这些事：

1. 读取 `.env`
2. 创建 `logs/`
3. 后台启动 `start_agent.sh`
4. 写 PID 到 `logs/foldseek-agent.pid`
5. 等待 `/health` 成功
6. 尽量打印可从浏览器访问的服务器地址

查看状态：

```bash
./status_all.sh
```

停止服务：

```bash
./stop_all.sh
```

也提供短名包装：

```bash
./start.sh
./status.sh
./stop.sh
```

## 测试

```bash
pytest -q
```

当前测试覆盖：

- 搜索结果解析与过滤
- 配置加载
- API 接口
- 文件上传
- 模块路由规划
- 新增模块的命令构造
