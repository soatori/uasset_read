"""Pin 连接关系恢复机制测试。"""
import struct
import pytest
from unittest.mock import MagicMock, patch, PropertyMock, call
from uasset_read.constants import MAX_FTEXT_CONSUMPTION
from uasset_read.serializers.graph import (
    read_ue_graph_pin,
    read_pin_reference,
    _recover_pin_array_count,
    _try_recover_to_subpins,
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


class TestPinReferenceGUID:
    """PinReference GUID 格式统一测试。"""

    @pytest.mark.parametrize("raw_guid,expected", [
        ("a1b2c3d4-e5f6-7890-abcd-ef1234567890", "A1B2C3D4E5F67890ABCDEF1234567890"),
        ("01020304-0506-0708-090a-0b0c0d0e0f10", "0102030405060708090A0B0C0D0E0F10"),
        ("00000000-0000-0000-0000-000000000000", "0" * 32),
    ], ids=["dashed-upper", "dashed-lower", "zero-guid"])
    def test_read_pin_reference_normalizes_guid(self, raw_guid, expected):
        """验证 read_pin_reference 将各种 GUID 格式归一化为 32 字符大写 hex。"""
        fake_archive = MagicMock()
        fake_archive.read_i32.side_effect = [0, 1]

        export_map = [MagicMock(object_name="TestNode")]
        import_map = []

        with patch("uasset_read.serializers.graph._read_guid", return_value=raw_guid):
            result = read_pin_reference(fake_archive, [], export_map, import_map)

        assert result is not None
        assert result["pin_guid"] == expected
        assert len(result["pin_guid"]) == 32
        assert "-" not in result["pin_guid"]

    def test_read_pin_reference_null_pointer_returns_none(self):
        """验证 b_null_ptr != 0 时返回 None（仅消耗 4 字节）。"""
        fake_archive = MagicMock()
        fake_archive.read_i32.side_effect = [1]  # b_null_ptr = 1 (非零)

        result = read_pin_reference(fake_archive, [], [], [])

        assert result is None
        # 仅调用一次 read_i32（读 b_null_ptr），不应再读更多
        assert fake_archive.read_i32.call_count == 1

    def test_read_pin_reference_negative_owning_node_uses_import_map(self):
        """验证 owning_node_index 为负数时从 import_map 解析节点名。"""
        fake_archive = MagicMock()
        # b_null=0, owning_node=-1（负索引 → import_map[0]）
        fake_archive.read_i32.side_effect = [0, -1]

        export_map = []
        import_map = [MagicMock(object_name="ImportedClass")]

        with patch("uasset_read.serializers.graph._read_guid",
                    return_value="a1b2c3d4-e5f6-7890-abcd-ef1234567890"):
            result = read_pin_reference(fake_archive, [], export_map, import_map)

        assert result is not None
        assert result["owning_node"] == "ImportedClass"

    def test_read_pin_reference_out_of_bounds_export_index(self):
        """验证 owning_node_index 超出 export_map 范围时 owning_node 为 None。"""
        fake_archive = MagicMock()
        # b_null=0, owning_node=10（远超 export_map 长度 1）
        fake_archive.read_i32.side_effect = [0, 10]

        export_map = [MagicMock(object_name="OnlyNode")]
        import_map = []

        with patch("uasset_read.serializers.graph._read_guid",
                    return_value="a1b2c3d4-e5f6-7890-abcd-ef1234567890"):
            result = read_pin_reference(fake_archive, [], export_map, import_map)

        assert result is not None
        assert result["owning_node"] is None

    def test_read_pin_reference_out_of_bounds_import_index(self):
        """验证负索引超出 import_map 范围时 owning_node 为 None。"""
        fake_archive = MagicMock()
        # b_null=0, owning_node=-10（远超 import_map 长度 1）
        fake_archive.read_i32.side_effect = [0, -10]

        export_map = []
        import_map = [MagicMock(object_name="OnlyImport")]

        with patch("uasset_read.serializers.graph._read_guid",
                    return_value="a1b2c3d4-e5f6-7890-abcd-ef1234567890"):
            result = read_pin_reference(fake_archive, [], export_map, import_map)

        assert result is not None
        assert result["owning_node"] is None

    def test_read_pin_reference_zero_owning_node(self):
        """验证 owning_node_index 为 0 时 owning_node 为 None（既非正也非负）。"""
        fake_archive = MagicMock()
        fake_archive.read_i32.side_effect = [0, 0]

        export_map = [MagicMock(object_name="Node")]
        import_map = [MagicMock(object_name="Import")]

        with patch("uasset_read.serializers.graph._read_guid",
                    return_value="a1b2c3d4-e5f6-7890-abcd-ef1234567890"):
            result = read_pin_reference(fake_archive, [], export_map, import_map)

        assert result is not None
        assert result["owning_node"] is None


class TestLinkedToRecovery:
    """LinkedTo 恢复机制测试。"""

    @patch("uasset_read.serializers.graph.read_pin_array")
    @patch("uasset_read.serializers.graph.read_pin_reference", return_value=None)
    @patch("uasset_read.serializers.graph._read_guid", return_value="00000000-0000-0000-0000-000000000000")
    @patch("uasset_read.serializers.graph.peek_valid_pin_array_count", return_value=0)
    @patch("uasset_read.serializers.graph._read_fstring_safe", return_value="")
    @patch("uasset_read.serializers.graph.read_ed_graph_pin_type")
    @patch("uasset_read.serializers.graph._read_ftext_value")
    @patch("uasset_read.serializers.graph._try_recover_to_subpins")
    @patch("uasset_read.serializers.graph.logger")
    def test_recover_to_subpins_result_is_used(
        self, mock_logger, mock_recover, mock_ftext, mock_pin_type, mock_fstring,
        mock_probe, mock_guid, mock_pin_ref, mock_pin_array,
    ):
        """验证 _try_recover_to_subpins 返回值被正确使用。"""
        mock_pin_array.side_effect = Exception("LinkedTo parse error")
        mock_recover.return_value = {
            "recovered_pos": 100,
            "count": 2,
            "recovery_type": "subpins_resync",
            "reason": "b_null!=0 null reference",
        }

        archive = _TrackingArchive()
        archive.advance(20)  # OwningNode(4) + PinId(16)

        mock_ftext.side_effect = _make_ftext_side_effect([50, 50])
        mock_pin_type.return_value = MagicMock()
        name_map, summary, export_map, import_map = _make_pin_args()

        result = read_ue_graph_pin(
            archive, name_map, summary, export_map, import_map,
            trace_mode=False,
        )

        # _try_recover_to_subpins 应被调用一次
        mock_recover.assert_called_once()
        # 验证返回值被正确获取（info 日志应包含 recovery 信息）
        recovery_result = mock_recover.return_value
        assert recovery_result is not None
        assert recovery_result["recovery_type"] == "subpins_resync"
        assert recovery_result["recovered_pos"] == 100
        # 验证 logger.info 被调用且包含恢复信息
        mock_logger.info.assert_called_once()
        info_args = mock_logger.info.call_args[0]
        assert "SubPins resynced" in info_args[0]
        assert info_args[1] == 100  # recovered_pos
        assert info_args[2] == "subpins_resync"  # recovery_type

    @patch("uasset_read.serializers.graph.read_pin_array")
    @patch("uasset_read.serializers.graph.read_pin_reference", return_value=None)
    @patch("uasset_read.serializers.graph._read_guid", return_value="00000000-0000-0000-0000-000000000000")
    @patch("uasset_read.serializers.graph.peek_valid_pin_array_count", return_value=0)
    @patch("uasset_read.serializers.graph._read_fstring_safe", return_value="")
    @patch("uasset_read.serializers.graph.read_ed_graph_pin_type")
    @patch("uasset_read.serializers.graph._read_ftext_value")
    @patch("uasset_read.serializers.graph._try_recover_to_subpins")
    @patch("uasset_read.serializers.graph.logger")
    def test_linkedto_failure_log_dedup_with_pin_name(
        self, mock_logger, mock_recover, mock_ftext, mock_pin_type, mock_fstring,
        mock_probe, mock_guid, mock_pin_ref, mock_pin_array,
    ):
        """验证失败日志去重包含 pin_name。"""
        mock_pin_array.side_effect = Exception("test error")
        mock_recover.return_value = None

        archive = _TrackingArchive()
        archive.advance(20)

        mock_ftext.side_effect = _make_ftext_side_effect([50, 50])
        mock_pin_type.return_value = MagicMock()
        name_map, summary, export_map, import_map = _make_pin_args()

        # 使用 patch 清除线程局部状态
        with patch("uasset_read.serializers.graph._get_thread_local") as mock_tls:
            tls_obj = MagicMock()
            tls_obj.linkedto_failure_seen = set()
            mock_tls.return_value = tls_obj

            # 第一次调用：pin_name="TestPin" — 应添加到 seen 集合
            read_ue_graph_pin(
                archive, name_map, summary, export_map, import_map,
                trace_mode=False,
            )
            # 验证三元组 key 被添加（包含 pin_name）
            assert len(tls_obj.linkedto_failure_seen) == 1
            added_key = next(iter(tls_obj.linkedto_failure_seen))
            assert len(added_key) == 3, "failure_key 应为三元组 (offset, exc_type, pin_name)"
            assert added_key[2] == "TestPin", f"第三元素应为 pin_name，实际为 {added_key[2]}"
            # 验证第一次调用时 logger.error 被调用（非去重路径）
            mock_logger.error.assert_called_once()
            error_args = mock_logger.error.call_args[0]
            assert "LinkedTo read failed at pos" in error_args[0]

    @patch("uasset_read.serializers.graph.read_pin_array")
    @patch("uasset_read.serializers.graph.read_pin_reference", return_value=None)
    @patch("uasset_read.serializers.graph._read_guid", return_value="00000000-0000-0000-0000-000000000000")
    @patch("uasset_read.serializers.graph.peek_valid_pin_array_count", return_value=0)
    @patch("uasset_read.serializers.graph._read_fstring_safe", return_value="")
    @patch("uasset_read.serializers.graph.read_ed_graph_pin_type")
    @patch("uasset_read.serializers.graph._read_ftext_value")
    @patch("uasset_read.serializers.graph._try_recover_to_subpins")
    @patch("uasset_read.serializers.graph._get_thread_local")
    @patch("uasset_read.serializers.graph.logger")
    def test_recovery_result_none_skips_info_log(
        self, mock_logger, mock_tls, mock_recover, mock_ftext, mock_pin_type, mock_fstring,
        mock_probe, mock_guid, mock_pin_ref, mock_pin_array,
    ):
        """验证 _try_recover_to_subpins 返回 None 时不输出 info 日志。"""
        mock_pin_array.side_effect = Exception("LinkedTo parse error")
        mock_recover.return_value = None  # 恢复失败

        # 提供干净的线程局部状态，确保 logger.error 不被去重跳过
        tls_obj = MagicMock()
        tls_obj.linkedto_failure_seen = set()
        mock_tls.return_value = tls_obj

        archive = _TrackingArchive()
        archive.advance(20)

        mock_ftext.side_effect = _make_ftext_side_effect([50, 50])
        mock_pin_type.return_value = MagicMock()
        name_map, summary, export_map, import_map = _make_pin_args()

        result = read_ue_graph_pin(
            archive, name_map, summary, export_map, import_map,
            trace_mode=False,
        )

        # _try_recover_to_subpins 仍应被调用
        mock_recover.assert_called_once()
        # recovery_result 为 None 时不应调用 logger.info
        mock_logger.info.assert_not_called()
        # logger.error 应被调用（异常路径，首次未去重）
        mock_logger.error.assert_called_once()


class _ByteArchive:
    """基于字节缓冲区的 mock archive，支持真实数据读取。"""

    def __init__(self, data: bytes):
        self._data = data
        self._pos = 0
        self._file_size = len(data)
        self._byte_swapping = False

    def tell(self):
        return self._pos

    def seek(self, pos, *args, **kwargs):
        self._pos = pos

    def read(self, n=None):
        if n is None:
            n = 1
        start = self._pos
        end = min(start + n, len(self._data))
        self._pos = end
        return self._data[start:end]


class TestSlidingRecovery:
    """滑动恢复机制测试。"""

    def test_dynamic_scan_window_based_on_bad_count(self):
        """验证 scan_window 根据 bad_count 动态调整。

        策略：在 error_pos - 30 处放置一个合法 count=1，
        - bad_count=5 (窗口 16): 搜索范围 [184, 216], target@170 不在范围内 -> None
        - bad_count=150 (窗口 64): 搜索范围 [136, 264], target@170 在范围内 -> 找到

        缓冲区填充 0xFF 以避免误匹配（0xFF 解析为 -1，超出 0..20 范围）。
        """
        error_pos = 200
        # 在 error_pos - 30 处放置 count=1 (little-endian)
        target_offset = error_pos - 30  # 170
        buf_size = 512
        buf = bytearray(b'\xff' * buf_size)
        struct.pack_into('<i', buf, target_offset, 1)

        archive = _ByteArchive(bytes(buf))
        export_map = []

        # bad_count=5 -> scan_window stays 16, range [184, 216], target@170 不在范围内
        archive.seek(error_pos)
        result_small = _recover_pin_array_count(
            archive, error_pos, bad_count=5,
            export_map=export_map, scan_window=16,
        )
        assert result_small is None, (
            f"bad_count=5 时窗口应为 16，不应找到 offset={target_offset} 处的 count"
        )

        # bad_count=150 -> scan_window becomes 64, range [136, 264], target@170 在范围内
        archive.seek(error_pos)
        result_large = _recover_pin_array_count(
            archive, error_pos, bad_count=150,
            export_map=export_map, scan_window=16,
        )
        assert result_large is not None, (
            f"bad_count=150 时窗口应为 64，应能找到 offset={target_offset} 处的 count"
        )
        assert result_large["count"] == 1

    def test_dynamic_scan_window_medium_bad_count(self):
        """验证 bad_count 在 (20, 100] 范围时窗口为 32。

        在 error_pos - 25 处放置 count=1，
        - bad_count=5 (窗口 16): range [184, 216], target@175 不在范围内 -> None
        - bad_count=30 (窗口 32): range [168, 232], target@175 在范围内 -> 找到
        """
        error_pos = 200
        target_offset = error_pos - 25  # 175
        buf_size = 512
        buf = bytearray(b'\xff' * buf_size)
        struct.pack_into('<i', buf, target_offset, 1)

        archive = _ByteArchive(bytes(buf))
        export_map = []

        # bad_count=5 -> window=16, range [184, 216], target@175 不在范围内
        archive.seek(error_pos)
        result_none = _recover_pin_array_count(
            archive, error_pos, bad_count=5,
            export_map=export_map, scan_window=16,
        )
        assert result_none is None, (
            f"bad_count=5 时窗口应为 16，不应找到 offset={target_offset} 处的 count"
        )

        # bad_count=30 -> scan_window becomes 32, range [168, 232], target@175 在范围内
        archive.seek(error_pos)
        result = _recover_pin_array_count(
            archive, error_pos, bad_count=30,
            export_map=export_map, scan_window=16,
        )
        assert result is not None, (
            f"bad_count=30 时窗口应为 32，应能找到 offset={target_offset} 处的 count"
        )
        assert result["count"] == 1

    def test_high_confidence_recovery_validated(self):
        """验证高置信度恢复的所有 ref 都通过验证。

        在 error_pos 处放置合法 count=2 + 两个合法 PinReference 结构，
        使用 scan_window=64 确保窗口足够覆盖所有数据。
        """
        error_pos = 100
        buf_size = 300
        buf = bytearray(b'\xff' * buf_size)

        # 在 error_pos 处放置 count=2
        struct.pack_into('<i', buf, error_pos, 2)

        export_map = [MagicMock(object_name="Node0")]

        # PinRef 1: b_null=0, owning_node=0, guid=non-zero
        ref1_offset = error_pos + 4  # 104
        struct.pack_into('<i', buf, ref1_offset, 0)      # b_null = 0
        struct.pack_into('<i', buf, ref1_offset + 4, 0)  # owning_node = 0
        for i in range(16):
            buf[ref1_offset + 8 + i] = 0x01

        # PinRef 2: b_null=0, owning_node=0, guid=non-zero
        ref2_offset = ref1_offset + 24  # 128
        struct.pack_into('<i', buf, ref2_offset, 0)      # b_null = 0
        struct.pack_into('<i', buf, ref2_offset + 4, 0)  # owning_node = 0
        for i in range(16):
            buf[ref2_offset + 8 + i] = 0x02

        archive = _ByteArchive(bytes(buf))

        # 使用 scan_window=64 确保窗口覆盖 count + 2 个 PinRef (52 字节)
        archive.seek(error_pos)
        result = _recover_pin_array_count(
            archive, error_pos, bad_count=5,
            export_map=export_map, scan_window=64,
        )

        assert result is not None, "恢复应成功"
        assert result["confidence"] == "high", (
            f"两个 ref 都验证通过时置信度应为 high，实际为 {result['confidence']}"
        )
        assert result["count"] == 2

    def test_low_confidence_count_zero_without_structure(self):
        """验证 count=0 且后续无结构时置信度为 low。"""
        error_pos = 100
        buf_size = 200
        buf = bytearray(b'\xff' * buf_size)

        # 在 error_pos 处放置 count=0，后面不放合法结构（0xFF 作为垃圾数据）
        struct.pack_into('<i', buf, error_pos, 0)

        archive = _ByteArchive(bytes(buf))
        export_map = []

        archive.seek(error_pos)
        result = _recover_pin_array_count(
            archive, error_pos, bad_count=5,
            export_map=export_map, scan_window=16,
        )

        assert result is not None, "恢复应成功（兜底）"
        assert result["confidence"] == "low", (
            f"count=0 且无后续结构时置信度应为 low，实际为 {result['confidence']}"
        )
        assert result["count"] == 0
