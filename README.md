# Foldseek Agent

一个轻量的 Python 封装，用于调用 `foldseek easy-search` 并对检索结果进行解析、过滤、汇总和导出。

## 功能亮点

- 基于 YAML 配置管理 Foldseek 路径、数据库和搜索参数。
- 支持结果阈值过滤（`tmscore`、`evalue`、`prob`）。
- 支持 Top-K 排序输出和结果摘要统计。
- 支持 CLI 直接调用并导出 JSON。
- 内置单元测试，支持本地快速回归。

## 快速开始

```bash
python main.py example.pdb --config config/config.yaml --database afdb50 --topk 10 --summary
```

输出 JSON：

```bash
python main.py example.pdb --json-out results/hits.json
```

列出可用数据库：

```bash
python main.py dummy.pdb --list-databases
```

> 提示：`--list-databases` 模式不会执行 Foldseek 检索，`pdb_file` 参数会被忽略。

## 配置文件

示例见 `config/config.yaml`。

必填项：

- `foldseek_path`
- `databases`（非空字典）
- `tmp_dir`

可选项：

- `result_dir`
- `search.max_seqs`
- `search.evalue`
- `search.timeout_seconds`

## 测试

```bash
pytest -q
```
