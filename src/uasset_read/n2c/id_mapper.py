"""N2CIdMapper — GUID ↔ 短 ID 双向映射器。

将完整的节点 GUID（如 "4A3B2C1D-..."）映射为紧凑短 ID（"N1", "N2"...），
用于 N2CStruct 序列化时的 token 压缩（~60% 节省）。
"""


class N2CIdMapper:
    """GUID ↔ 短 ID 映射器。

    用法:
        mapper = N2CIdMapper()
        short_id = mapper.to_short("4A3B2C1D-...")  # → "N1"
        guid = mapper.to_guid("N1")                   # → "4A3B2C1D-..."

    短 ID 格式: "N{N}"（N1, N2, N3...），按注册顺序分配。
    重复注册同一 GUID 返回相同的短 ID（幂等）。
    """

    def __init__(self) -> None:
        self._guid_to_short: dict[str, str] = {}
        self._short_to_guid: dict[str, str] = {}
        self._counter = 0

    def register(self, guid: str) -> str:
        """注册 GUID，返回短 ID。已注册则返回现有映射。"""
        if guid in self._guid_to_short:
            return self._guid_to_short[guid]
        self._counter += 1
        short_id = f"N{self._counter}"
        self._guid_to_short[guid] = short_id
        self._short_to_guid[short_id] = guid
        return short_id

    def to_short(self, guid: str) -> str | None:
        """GUID → 短 ID。未注册返回 None。"""
        return self._guid_to_short.get(guid)

    def to_guid(self, short_id: str) -> str | None:
        """短 ID → GUID。未注册返回 None。"""
        return self._short_to_guid.get(short_id)

    def reset(self) -> None:
        """清空所有映射（测试用）。"""
        self._guid_to_short.clear()
        self._short_to_guid.clear()
        self._counter = 0
