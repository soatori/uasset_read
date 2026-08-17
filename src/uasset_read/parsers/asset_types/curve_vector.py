"""UCurveVector Asset type handler (opaque partial metadata).

UCurveVector contains XYZ curve data (3 FRichCurve channels).
Pure UPROPERTY serialization, no custom Serialize().
"""

from uasset_read.parsers.asset_types.opaque_stub import make_opaque_stub

parse_curve_vector = make_opaque_stub("CurveVector")
