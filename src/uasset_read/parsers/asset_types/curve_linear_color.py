"""UCurveLinearColor Asset type handler (opaque partial metadata).

UCurveLinearColor contains RGBA curve data (4 FRichCurve channels).
Pure UPROPERTY serialization, no custom Serialize().
"""

from uasset_read.parsers.asset_types.opaque_stub import make_opaque_stub

parse_curve_linear_color = make_opaque_stub("CurveLinearColor")
