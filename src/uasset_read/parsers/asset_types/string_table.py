"""UStringTable Asset type handler (opaque partial metadata).

UStringTable only uses standard UPROPERTY serialization (TableNamespace, StringTable TMap),
no custom Serialize(). Handler provides type identification.
"""

from uasset_read.parsers.asset_types.opaque_stub import make_opaque_stub

parse_string_table = make_opaque_stub("StringTable")
