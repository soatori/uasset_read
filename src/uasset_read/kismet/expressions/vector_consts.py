from __future__ import annotations

"""Kismet expression -- vector and transform constant expressions."""


from dataclasses import dataclass
from typing import TYPE_CHECKING

from uasset_read.kismet.expressions.base import KismetExpression
from uasset_read.kismet.tokens import EExprToken
from uasset_read.constants import UE5_LARGE_WORLD_COORDINATES

if TYPE_CHECKING:
    from uasset_read.kismet.archive import FKismetArchive


def _is_lwc(archive: "FKismetArchive") -> bool:
    """Check if Large World Coordinates (double-width vectors) are enabled."""
    summary = getattr(archive, "summary", None)
    if summary is None:
        return False
    return getattr(summary, "file_version_ue5", 0) >= UE5_LARGE_WORLD_COORDINATES


@dataclass
class EX_VectorConst(KismetExpression):
    """Vector constant (X, Y, Z).

    Reads doubles when summary.file_version_ue5 >= UE5_LARGE_WORLD_COORDINATES,
    otherwise reads floats.
    """

    X: float = 0.0
    Y: float = 0.0
    Z: float = 0.0

    @property
    def Token(self):
        return EExprToken.EX_VectorConst

    @classmethod
    def from_archive(cls, archive: FKismetArchive, name_map: list[str]) -> EX_VectorConst:
        if _is_lwc(archive):
            x = archive.read_f64()
            y = archive.read_f64()
            z = archive.read_f64()
        else:
            x = archive.read_f32()
            y = archive.read_f32()
            z = archive.read_f32()
        return cls(X=x, Y=y, Z=z)

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["Value"] = f"({self.X}, {self.Y}, {self.Z})"
        return d


@dataclass
class EX_RotationConst(KismetExpression):
    """Rotation constant expression (EX_RotationConst, 0x22).

    Reads doubles when summary.file_version_ue5 >= UE5_LARGE_WORLD_COORDINATES.
    """

    Pitch: float = 0.0
    Yaw: float = 0.0
    Roll: float = 0.0

    @property
    def Token(self):
        return EExprToken.EX_RotationConst

    @classmethod
    def from_archive(cls, archive: FKismetArchive, name_map: list[str]) -> EX_RotationConst:
        if _is_lwc(archive):
            p = archive.read_f64()
            y = archive.read_f64()
            r = archive.read_f64()
        else:
            p = archive.read_f32()
            y = archive.read_f32()
            r = archive.read_f32()
        return cls(Pitch=p, Yaw=y, Roll=r)

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["Value"] = f"(Pitch={self.Pitch}, Yaw={self.Yaw}, Roll={self.Roll})"
        return d


@dataclass
class EX_TransformConst(KismetExpression):
    """Transform constant expression (EX_TransformConst, 0x2B).

    UE FTransform serialization order: quaternion rotation (XYZW) -> translation (XYZ) -> scale (XYZ).
    Reads doubles when summary.file_version_ue5 >= UE5_LARGE_WORLD_COORDINATES.
    Field naming retains Pitch/Yaw/Roll as translation components to align with design documents.
    """

    X: float = 0.0
    Y: float = 0.0
    Z: float = 0.0
    W: float = 0.0
    Pitch: float = 0.0
    Yaw: float = 0.0
    Roll: float = 0.0
    SX: float = 1.0
    SY: float = 1.0
    SZ: float = 1.0

    @property
    def Token(self):
        return EExprToken.EX_TransformConst

    @classmethod
    def from_archive(cls, archive: FKismetArchive, name_map: list[str]) -> EX_TransformConst:
        read_num = archive.read_f64 if _is_lwc(archive) else archive.read_f32
        # Rotation (quat): X, Y, Z, W
        rx = read_num()
        ry = read_num()
        rz = read_num()
        rw = read_num()
        # Translation: X, Y, Z
        tx = read_num()
        ty = read_num()
        tz = read_num()
        # Scale: X, Y, Z
        sx = read_num()
        sy = read_num()
        sz = read_num()
        return cls(
            X=rx,
            Y=ry,
            Z=rz,
            W=rw,
            Pitch=tx,
            Yaw=ty,
            Roll=tz,
            SX=sx,
            SY=sy,
            SZ=sz,
        )


@dataclass
class EX_Vector3fConst(KismetExpression):
    """3-component float vector constant (EX_Vector3fConst, 0x41)."""

    X: float = 0.0
    Y: float = 0.0
    Z: float = 0.0

    @property
    def Token(self):
        return EExprToken.EX_Vector3fConst

    @classmethod
    def from_archive(cls, archive: FKismetArchive, name_map: list[str]) -> EX_Vector3fConst:
        x = archive.read_f32()
        y = archive.read_f32()
        z = archive.read_f32()
        return cls(X=x, Y=y, Z=z)

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["Value"] = f"({self.X}, {self.Y}, {self.Z})"
        return d
