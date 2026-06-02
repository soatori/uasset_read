"""Pin 连接关系恢复机制测试。"""
import struct
import pytest
from unittest.mock import MagicMock, patch, PropertyMock, call
from uasset_read.constants import MAX_FTEXT_CONSUMPTION
from uasset_read.serializers.graph import (
    read_ue_graph_pin,
    read_pin_reference,
    _recover_pin_array_count,
)


class _TrackingArchive:
    """位置追踪 mock archive，自动管理 tell()/seek() 状态。"""

    def __init__(self, read_increment=4):
        self._pos = 0
        self._read_increment = read_increment
        self._seek_calls = []

    def tell(self):
        return self._pos

    def seek(self, pos, *args, **kwargs):
        self._seek_calls.append(pos)
        self._pos = pos

    def advance(self, n):
        """手动推进位置 n 字节。"""
        self._pos += n

    def read_i32(self):
        self._pos += 4
        return 0

    def read_u8(self):
        self._pos += 1
        return 1  # EGPD_Output

    def read_bytes(self, n):
        self._pos += n
        return b'\x00' * n

    def read(self, n=None):
        if n is None:
            n = 1
        self._pos += n
        return b'\x00' * n

    def read_name(self, name_map):
        self._pos += 8  # u32 index + u32 number
        return name_map[0] if name_map else "TestPin"

    @property
    def seek_calls(self):
        return list(self._seek_calls)


def _make_ftext_side_effect(consumed_values):
    """构造 _read_ftext_value 的 side_effect，自动推进 archive 位置。

    consumed_values: 每次调用的消耗字节数列表。
    返回 (value, flags, history_type, consumed) 元组。
    """
    call_count = [0]

    def side_effect(archive, tolerant=True):
        idx = call_count[0]
        consumed = consumed_values[idx]
        call_count[0] += 1
        # 推进 archive 位置以模拟真实消耗
        archive.advance(consumed)
        return (f"Value{idx}", 0, -1, consumed)

    return side_effect


def _make_pin_args():
    """构造 read_ue_graph_pin 的标准参数。"""
    name_map = ["TestPin"]
    summary = MagicMock()
    summary.name_map = name_map
    export_map = []
    import_map = []
    return name_map, summary, export_map, import_map


# FText 头部大小：flags(i32, 4B) + history_type(u8, 1B) = 5 字节
_FTEXT_HEADER_SIZE = 5


class TestFTextSafetyNet:
    """FText 解析安全网测试。"""

    @patch("uasset_read.serializers.graph.read_pin_array", return_value=[])
    @patch("uasset_read.serializers.graph.read_pin_reference", return_value=None)
    @patch("uasset_read.serializers.graph._read_guid", return_value="00000000-0000-0000-0000-000000000000")
    @patch("uasset_read.serializers.graph.peek_valid_pin_array_count", return_value=0)
    @patch("uasset_read.serializers.graph._read_fstring_safe", return_value="")
    @patch("uasset_read.serializers.graph.read_ed_graph_pin_type")
    @patch("uasset_read.serializers.graph._read_ftext_value")
    @pytest.mark.parametrize("large_consumption", [15000, 20000, 50000],
                             ids=["15KB", "20KB", "50KB"])
    def test_ftext_safety_net_triggers_on_large_consumption(
        self, mock_ftext, mock_pin_type, mock_fstring,
        mock_probe, mock_guid, mock_pin_ref, mock_pin_array,
        large_consumption,
    ):
        """验证 PinFriendlyName FText 消耗超过阈值时触发安全网，值被设为 None。"""
        assert large_consumption > MAX_FTEXT_CONSUMPTION

        archive = _TrackingArchive()
        archive.advance(20)  # OwningNode(4) + PinId(16)

        # 模拟两次 FText 调用都消耗超大值
        mock_ftext.side_effect = _make_ftext_side_effect(
            [large_consumption, large_consumption]
        )
        mock_pin_type.return_value = MagicMock()
        name_map, summary, export_map, import_map = _make_pin_args()

        result = read_ue_graph_pin(
            archive, name_map, summary, export_map, import_map,
            trace_mode=False,
        )

        # 安全网应将 pin_friendly_name 设为 None
        assert result.pin_friendly_name is None
        # 安全网触发后应有 seek 回退调用
        assert len(archive.seek_calls) > 0
        # seek 回退目标应小于大消耗后的位置，证明 seek 确实回退了
        post_consumption_pos = 20 + 4 + 16 + 8 + large_consumption  # header + read ops + ftext
        assert archive.seek_calls[0] < post_consumption_pos, (
            f"安全网 seek 目标 {archive.seek_calls[0]} 应小于消耗后位置 {post_consumption_pos}"
        )
        # seek 目标应为 ftext_start_pos + 5（跳过 5 字节 FText 头部）
        # ftext_start_pos = OwningNode(4) + PinId(16) + PinName(8) = 28 加上 mock advance(20)
        # 注意：实际 ftext_start_pos 由函数内部决定，seek 应跳过头部
        assert archive.seek_calls[0] > 20, (
            f"seek 目标应大于 OwningNode+PinId 的起始位置 20"
        )

    @patch("uasset_read.serializers.graph.read_pin_array", return_value=[])
    @patch("uasset_read.serializers.graph.read_pin_reference", return_value=None)
    @patch("uasset_read.serializers.graph._read_guid", return_value="00000000-0000-0000-0000-000000000000")
    @patch("uasset_read.serializers.graph.peek_valid_pin_array_count", return_value=0)
    @patch("uasset_read.serializers.graph._read_fstring_safe", return_value="")
    @patch("uasset_read.serializers.graph.read_ed_graph_pin_type")
    @patch("uasset_read.serializers.graph._read_ftext_value")
    def test_ftext_safety_net_allows_normal_consumption(
        self, mock_ftext, mock_pin_type, mock_fstring,
        mock_probe, mock_guid, mock_pin_ref, mock_pin_array,
    ):
        """验证 FText 安全网允许正常消耗通过，值被保留。"""
        normal_consumption = 100

        archive = _TrackingArchive()
        archive.advance(20)

        # 模拟 FText 正常消耗
        mock_ftext.side_effect = _make_ftext_side_effect(
            [normal_consumption, normal_consumption]
        )
        mock_pin_type.return_value = MagicMock()
        name_map, summary, export_map, import_map = _make_pin_args()

        result = read_ue_graph_pin(
            archive, name_map, summary, export_map, import_map,
            trace_mode=False,
        )

        # 正常消耗: pin_friendly_name 应保留原值 (不是 None)
        assert result.pin_friendly_name is not None
        # 正常路径不应有 FText 安全网 seek 回退调用
        # （LinkedTo/SubPins 的 probe seek 不计入）
        # FText 安全网 seek 会 seek 到 ftext_start_pos + 5 (小于 100)
        safety_net_seeks = [s for s in archive.seek_calls if s < 100]
        assert len(safety_net_seeks) == 0

    @patch("uasset_read.serializers.graph.read_pin_array", return_value=[])
    @patch("uasset_read.serializers.graph.read_pin_reference", return_value=None)
    @patch("uasset_read.serializers.graph._read_guid", return_value="00000000-0000-0000-0000-000000000000")
    @patch("uasset_read.serializers.graph.peek_valid_pin_array_count", return_value=0)
    @patch("uasset_read.serializers.graph._read_fstring_safe", return_value="")
    @patch("uasset_read.serializers.graph.read_ed_graph_pin_type")
    @patch("uasset_read.serializers.graph._read_ftext_value")
    def test_ftext_safety_net_default_text_value(
        self, mock_ftext, mock_pin_type, mock_fstring,
        mock_probe, mock_guid, mock_pin_ref, mock_pin_array,
    ):
        """验证 DefaultTextValue 的 FText 安全网在消耗超过 10KB 时触发。"""
        friendly_name_consumed = 50
        default_text_consumed = 15000  # 超过 10KB

        archive = _TrackingArchive()
        archive.advance(20)

        # PinFriendlyName 正常, DefaultTextValue 超大
        mock_ftext.side_effect = _make_ftext_side_effect(
            [friendly_name_consumed, default_text_consumed]
        )
        mock_pin_type.return_value = MagicMock()
        name_map, summary, export_map, import_map = _make_pin_args()

        result = read_ue_graph_pin(
            archive, name_map, summary, export_map, import_map,
            trace_mode=False,
        )

        # PinFriendlyName 正常通过
        assert result.pin_friendly_name is not None
        # DefaultTextValue 安全网触发: 设为 None
        assert result.default_text_value is None

    @patch("uasset_read.serializers.graph.read_pin_array", return_value=[])
    @patch("uasset_read.serializers.graph.read_pin_reference", return_value=None)
    @patch("uasset_read.serializers.graph._read_guid", return_value="00000000-0000-0000-0000-000000000000")
    @patch("uasset_read.serializers.graph.peek_valid_pin_array_count", return_value=0)
    @patch("uasset_read.serializers.graph._read_fstring_safe", return_value="")
    @patch("uasset_read.serializers.graph.read_ed_graph_pin_type")
    @patch("uasset_read.serializers.graph._read_ftext_value")
    def test_ftext_exception_seeks_back_to_start(
        self, mock_ftext, mock_pin_type, mock_fstring,
        mock_probe, mock_guid, mock_pin_ref, mock_pin_array,
    ):
        """验证 FText 解析抛异常时 archive seek 回到解析前位置 +5（跳过头部）。"""
        archive = _TrackingArchive()
        archive.advance(20)

        # 第一次调用 (PinFriendlyName) 抛异常
        # 第二次调用 (DefaultTextValue) 正常
        def exception_then_normal(archive, tolerant=True):
            if not hasattr(exception_then_normal, '_called'):
                exception_then_normal._called = True
                raise Exception("FText parse error")
            archive.advance(10)
            return ("DefaultText", 0, -1, 10)

        mock_ftext.side_effect = exception_then_normal
        mock_pin_type.return_value = MagicMock()
        name_map, summary, export_map, import_map = _make_pin_args()

        result = read_ue_graph_pin(
            archive, name_map, summary, export_map, import_map,
            trace_mode=False,
        )

        # 异常处理: PinFriendlyName 应为 None (显式赋值)
        assert result.pin_friendly_name is None
        # 异常分支也调用了 seek，目标为 ftext_start_pos + 5
        assert len(archive.seek_calls) > 0
        # 异常时未消耗任何字节（异常立即抛出），seek 目标应在初始位置之后
        assert archive.seek_calls[0] > 20, (
            f"异常 seek 目标应大于 OwningNode+PinId 起始位置 20, "
            f"实际为 {archive.seek_calls[0]}"
        )

    @patch("uasset_read.serializers.graph.read_pin_array", return_value=[])
    @patch("uasset_read.serializers.graph.read_pin_reference", return_value=None)
    @patch("uasset_read.serializers.graph._read_guid", return_value="00000000-0000-0000-0000-000000000000")
    @patch("uasset_read.serializers.graph.peek_valid_pin_array_count", return_value=0)
    @patch("uasset_read.serializers.graph._read_fstring_safe", return_value="")
    @patch("uasset_read.serializers.graph.read_ed_graph_pin_type")
    @patch("uasset_read.serializers.graph._read_ftext_value")
    def test_ftext_safety_net_trace_mode(
        self, mock_ftext, mock_pin_type, mock_fstring,
        mock_probe, mock_guid, mock_pin_ref, mock_pin_array,
    ):
        """验证安全网触发时 trace_mode=True 正确执行且不崩溃。"""
        large_consumption = 15000
        normal_consumption = 50

        archive = _TrackingArchive()
        archive.advance(20)

        mock_ftext.side_effect = _make_ftext_side_effect(
            [large_consumption, normal_consumption]
        )
        mock_pin_type.return_value = MagicMock()
        name_map, summary, export_map, import_map = _make_pin_args()

        # trace_mode=True 不应导致异常或改变安全网行为
        result = read_ue_graph_pin(
            archive, name_map, summary, export_map, import_map,
            trace_mode=True,
        )

        # 安全网触发: pin_friendly_name 应为 None（与 trace_mode=False 行为一致）
        assert result.pin_friendly_name is None
        # seek 回退仍然发生
        assert len(archive.seek_calls) > 0
