# 常用命令

## 解析

```bash
python run.py file.uasset                       # JSON（默认）
python run.py file.uasset --markdown            # Markdown + Mermaid
python run.py file.uasset --strict              # 遇警告停止
python run.py file.uasset --tolerant             # 容错模式（默认）
python run.py --batch-dir path/to/dir/           # 批量导出
python run.py --list-formats                     # 列出格式
python run.py file1.uasset --diff file2.uasset   # 对比
```

## 测试与质量

```bash
python -m pytest tests/ -v
python -m pytest tests/ -v -m "not slow"
python -m pytest tests/ -v --cov=uasset_read
python -m pytest tests/{模块}/test_x.py::test_y -v
python -m pytest tests/ -v -m quality
```

pytest 标记：`integration`、`quality`、`regression`、`slow`；`pytest.ini` 已设置 `pythonpath = src`。
