"""Support running via python -m uasset_read."""
import sys
from pathlib import Path

# Inject src/ into Python path so it can be called directly from the project root
_src_dir = Path(__file__).resolve().parent
if str(_src_dir.parent) not in sys.path:
    sys.path.insert(0, str(_src_dir.parent))

from uasset_read.cli import main

if __name__ == "__main__":
    main()
