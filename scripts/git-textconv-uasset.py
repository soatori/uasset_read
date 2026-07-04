#!/usr/bin/env python
"""Git textconv 驱动脚本 — 输出 .uasset 的人类可读文本摘要到 stdout。

用法（由 git 自动调用）：

    python scripts/git-textconv-uasset.py path/to/file.uasset

或在 .gitattributes 中配置：

    *.uasset diff=uasset-read

然后在 git config 中设置：

    git config diff.uasset-read.textconv "python scripts/git-textconv-uasset.py"
"""
from __future__ import annotations

import sys
from pathlib import Path

# 注入 src/ 到 Python 路径
_src_dir = Path(__file__).resolve().parent.parent / "src"
if str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))

from uasset_read.core import parse_single


def main() -> int:
    if len(sys.argv) < 2:
        print("用法: git-textconv-uasset.py <file.uasset>", file=sys.stderr)
        return 1

    file_path = sys.argv[1]
    p = Path(file_path)
    if not p.is_file():
        print(f"文件不存在: {file_path}", file=sys.stderr)
        return 1

    try:
        output = parse_single(
            str(p),
            format="text",
            tolerant=True,
            verbose=False,
        )
    except Exception as e:
        # textconv 脚本不应崩溃，否则 git diff 会失败
        print(f"[解析错误] {p.name}: {e}", file=sys.stderr)
        return 1

    sys.stdout.write(output)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
