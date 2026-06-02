"""Pin 连接关系恢复机制测试。"""
import struct
import pytest
from unittest.mock import MagicMock, patch, PropertyMock, call
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


class TestFTextSafetyNet:
    """FText 解析安全网测试。"""

    @patch("uasset_read.serializers.graph.read_pin_array", return_value=[])
    @patch("uasset_read.serializers.graph.read_pin_reference", return_value=None)
    @patch("uasset_read.serializers.graph._read_guid", return_value="00000000-0000-0000-0000-000000000000")
    @patch("uasset_read.serializers.graph.peek_valid_pin_array_count", return_value=0)
    @patch("uasset_read.serializers.graph._read_fstring_safe", return_value="")
    @patch("uasset_read.serializers.graph.read_ed_graph_pin_type")
    @patch("uasset_read.serializers.graph._read_ftext_value")
    def test_ftext_consumption_limit(
        self, mock_ftext, mock_pin_type, mock_fstring,
        mock_probe, mock_guid, mock_pin_ref, mock_pin_array,
    ):
        """验证 PinFriendlyName FText 消耗超过 10KB 时触发安全网，值被设为 None。"""
        FTEXT_MAX_CONSUMPTION = 10240
        friendly_name_consumed = 15000  # 超过 10KB

        archive = _TrackingArchive()
        archive.advance(20)  # OwningNode(4) + PinId(16)

        # 模拟两次 FText 调用都消耗 15000 字节
        mock_ftext.side_effect = _make_ftext_side_effect(
            [friendly_name_consumed, friendly_name_consumed]
        )
        mock_pin_type.return_value = MagicMock()
        name_map, summary, export_map, import_map = _make_pin_args()

        # 记录调用前的位置，用于验证 seek 回退
        pos_before = archive.tell()

        result = read_ue_graph_pin(
            archive, name_map, summary, export_map, import_map,
            trace_mode=False,
        )

        # 安全网应将 pin_friendly_name 设为 None
        assert result.pin_friendly_name is None
        # 安全网触发后，seek 目标位置应小于消耗后的当前位置
        # 即 seek 回退到 FText 解析前的位置
        assert len(archive.seek_calls) > 0
        # 第一个 seek 应回退到 pos_before 之后的某位置 (OwningNode+PinId+PinName之后)
        first_safety_seek = archive.seek_calls[0]
        assert first_safety_seek > pos_before  # 在推进之后的某个位置

    @patch("uasset_read.serializers.graph.read_pin_array", return_value=[])
    @patch("uasset_read.serializers.graph.read_pin_reference", return_value=None)
    @patch("uasset_read.serializers.graph._read_guid", return_value="00000000-0000-0000-0000-000000000000")
    @patch("uasset_read.serializers.graph.peek_valid_pin_array_count", return_value=0)
    @patch("uasset_read.serializers.graph._read_fstring_safe", return_value="")
    @patch("uasset_read.serializers.graph.read_ed_graph_pin_type")
    @patch("uasset_read.serializers.graph._read_ftext_value")
    def test_ftext_seek_fallback_on_corruption(
        self, mock_ftext, mock_pin_type, mock_fstring,
        mock_probe, mock_guid, mock_pin_ref, mock_pin_array,
    ):
        """验证 FText 超大消耗时 archive seek 回到解析前位置（seek 回退）。"""
        friendly_name_consumed = 15000

        archive = _TrackingArchive()
        archive.advance(20)

        mock_ftext.side_effect = _make_ftext_side_effect(
            [friendly_name_consumed, friendly_name_consumed]
        )
        mock_pin_type.return_value = MagicMock()
        name_map, summary, export_map, import_map = _make_pin_args()

        result = read_ue_graph_pin(
            archive, name_map, summary, export_map, import_map,
            trace_mode=False,
        )

        # 安全网触发后 pin_friendly_name 应为 None
        assert result.pin_friendly_name is None
        # 验证 seek 被调用（安全网 seek 回退）
        assert len(archive.seek_calls) > 0
        # seek 目标应远小于消耗后的位置（消耗 15000 字节后位置应很大）
        # seek 回退位置应在 100 以内（OwningNode+PinId+PinName 之后）
        assert archive.seek_calls[0] < 100

    @patch("uasset_read.serializers.graph.read_pin_array", return_value=[])
    @patch("uasset_read.serializers.graph.read_pin_reference", return_value=None)
    @patch("uasset_read.serializers.graph._read_guid", return_value="00000000-0000-0000-0000-000000000000")
    @patch("uasset_read.serializers.graph.peek_valid_pin_array_count", return_value=0)
    @patch("uasset_read.serializers.graph._read_fstring_safe", return_value="")
    @patch("uasset_read.serializers.graph.read_ed_graph_pin_type")
    @patch("uasset_read.serializers.graph._read_ftext_value")
    def test_ftext_safety_net_triggers_on_large_consumption(
        self, mock_ftext, mock_pin_type, mock_fstring,
        mock_probe, mock_guid, mock_pin_ref, mock_pin_array,
    ):
        """验证 FText 安全网在 PinFriendlyName 消耗超过 10KB 时触发，值被设为 None。"""
        FTEXT_MAX_CONSUMPTION = 10240
        large_consumption = 15000
        assert large_consumption > FTEXT_MAX_CONSUMPTION

        archive = _TrackingArchive()
        archive.advance(20)

        mock_ftext.side_effect = _make_ftext_side_effect(
            [large_consumption, large_consumption]
        )
        mock_pin_type.return_value = MagicMock()
        name_map, summary, export_map, import_map = _make_pin_args()

        result = read_ue_graph_pin(
            archive, name_map, summary, export_map, import_map,
            trace_mode=False,
        )

        # 安全网触发: pin_friendly_name 应为 None
        assert result.pin_friendly_name is None

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
        """验证 FText 解析抛异常时 archive seek 回到解析前位置。"""
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

        # 异常处理: PinFriendlyName 应为 None (异常分支不设值, 保持初始 None)
        assert result.pin_friendly_name is None
        # 验证异常分支也调用了 seek（异常恢复 seek）
        assert len(archive.seek_calls) > 0
        # seek 回退位置应小于消耗后的位置
        assert archive.seek_calls[0] < 100
