#!/usr/bin/env python
"""uasset_read — 虚幻引擎 .uasset 文件 Python 解析器。

直接调用：

    python run.py path/to/file.uasset
    python run.py path/to/file.uasset --text
    python run.py path/to/file.uasset --markdown
    python run.py path/to/file.uasset --cpp-skeleton
    python run.py path/to/file.uasset --blueprint-text
    python run.py path/to/file.uasset --blueprint-ue-text
    python run.py path/to/file.uasset --batch-dir path/to/dir/
    python run.py path/to/file.uasset --output output.json
    python run.py path/to/file.uasset --tolerant
    python run.py path/to/file.uasset --strict
    python run.py path/to/file.uasset --verbose
"""
import sys
from pathlib import Path

# 注入 src/ 到 Python 路径
_src_dir = Path(__file__).resolve().parent / "src"
if str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))

from uasset_read.cli import main

if __name__ == "__main__":
    main()
