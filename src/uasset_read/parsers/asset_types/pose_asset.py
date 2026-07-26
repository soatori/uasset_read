"""UPoseAsset Asset type handler (opaque partial metadata).

UPoseAsset::Serialize only calls Super::Serialize, data serialized via UPROPERTY
(PoseNames TArray<FName>, PoseValues TArray<FTransform>).
Handler provides type identification.
"""

from uasset_read.parsers.asset_types.opaque_stub import make_opaque_stub

parse_pose_asset = make_opaque_stub("PoseAsset")
