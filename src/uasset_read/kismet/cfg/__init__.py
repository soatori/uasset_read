"""CFG (Control Flow Graph) infrastructure.

Provides basic block construction, dominator tree computation, region decomposition, and structured statement output.
"""

from uasset_read.kismet.cfg.build import build_cfg
from uasset_read.kismet.cfg.dom import compute_dominator_tree

# Internal symbols are imported directly from submodules
# (e.g., from uasset_read.kismet.cfg.stmt import Stmt)

__all__ = [
    "build_cfg",
    "compute_dominator_tree",
]
