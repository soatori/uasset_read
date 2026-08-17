"""UCurveFloat Asset type handler (opaque partial metadata).

UCurveFloat contains FRichCurve keyframe data.
Pure UPROPERTY serialization, no custom Serialize().
"""

from uasset_read.parsers.asset_types.opaque_stub import make_opaque_stub

parse_curve_float = make_opaque_stub("CurveFloat")
