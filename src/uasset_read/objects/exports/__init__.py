"""常见 UE 资产类型"""
# 导入所有资产类型以触发注册
from uasset_read.objects.exports.mesh import UStaticMesh, USkeletalMesh
from uasset_read.objects.exports.texture import UTexture2D, UTextureCube
from uasset_read.objects.exports.material import UMaterial, UMaterialInstance

__all__ = [
    "UStaticMesh",
    "USkeletalMesh",
    "UTexture2D",
    "UTextureCube",
    "UMaterial",
    "UMaterialInstance",
]
