"""Package readers.

The direct binary reader lives in :mod:`uasset_read.v2.package.legacy`
(``LegacyPackageReader``). The former v1→v2 adapter was removed: the public
``parse_package_document()`` API builds documents directly via the reader.
"""

from __future__ import annotations
