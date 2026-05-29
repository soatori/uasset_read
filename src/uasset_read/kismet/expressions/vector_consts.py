"""Kismet 表达式 — 向量和变换常量表达式。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from uasset_read.kismet.expressions.base import KismetExpression
from uasset_read.kismet.tokens import EExprToken

if TYPE_CHECKING:
    from uasset_read.kismet.archive import FKismetArchive


@dataclass
class EX_VectorConst(KismetExpression):
    """向量常量 (X, Y, Z)"""

    X: float = 0.0
    Y: float = 0.0
    Z: float = 0.0

    @property
    def Token(self):
        return EExprToken.EX_VectorConst

    @classmethod
    def from_archive(cls, archive: FKismetArchive, name_map: list[str]) -> EX_VectorConst:
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
    """Rotation constant expression (EX_RotationConst, 0x22)."""

    Pitch: float = 0.0
    Yaw: float = 0.0
    Roll: float = 0.0

    @property
    def Token(self):
        return EExprToken.EX_RotationConst

    @classmethod
    def from_archive(cls, archive: FKismetArchive, name_map: list[str]) -> EX_RotationConst:
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

    UE FTransform 序列化顺序：四元数旋转 (XYZW) -> 平移 (XYZ) -> 缩放 (XYZ)。
    字段命名保留 Pitch/Yaw/Roll 作为平移分量以对齐计划文档。
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
        # Rotation (quat): X, Y, Z, W
        rx = archive.read_f32()
        ry = archive.read_f32()
        rz = archive.read_f32()
        rw = archive.read_f32()
        # Translation: X, Y, Z
        tx = archive.read_f32()
        ty = archive.read_f32()
        tz = archive.read_f32()
        # Scale: X, Y, Z
        sx = archive.read_f32()
        sy = archive.read_f32()
        sz = archive.read_f32()
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
