"""AnimDataModel Asset metadata extractor (partial metadata).

UAnimDataModel uses standard UPROPERTY serialization (no custom Serialize()),
currently only extracts raw byte samples for diagnostics.
"""

from uasset_read.parsers.asset_types.opaque_stub import make_opaque_stub

parse_anim_data_model = make_opaque_stub("AnimationDataModel")
