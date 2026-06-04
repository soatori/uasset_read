"""支持 python -m uasset_read 直接运行。"""
import sys
from pathlib import Path

# 注入 src/ 到 Python 路径，确保从项目根目录可直接调用
_src_dir = Path(__file__).resolve().parent
if str(_src_dir.parent) not in sys.path:
    sys.path.insert(0, str(_src_dir.parent))

from uasset_read.cli import main

if __name__ == "__main__":
    main()
