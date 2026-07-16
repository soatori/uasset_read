"""FName 索引越界恢复测试 — 警告级别验证。"""
import logging
import pytest
from unittest.mock import MagicMock, patch
from uasset_read.archive import FArchive


class TestFnameIndexRecoveryLogging:
    """验证 _try_recover_fname 恢复成功/失败时的日志级别。"""

    @patch("uasset_read.archive.logger")
    def test_recovery_success_is_debug(self, mock_logger):
        """恢复成功时应记录 debug 而非 warning。"""
        archive = MagicMock(spec=FArchive)
        archive._name_map = ["ValidName1", "ValidName2"]
        archive._name_count = 2
        archive._source_hint = "test.uasset"
        archive._tolerant = True
        archive._file_size = 100
        archive._recovery_attempts = 0
        archive._recovery_successes = 0
        archive._recovery_failures = 0

        # 模拟 read_u32 返回超阈值索引，然后恢复成功
        original_pos = 10
        archive.tell.return_value = original_pos
        archive.read_u32.side_effect = [1500, 0]  # index=1500 (>1000), number=0

        # 模拟 _try_recover_fname 成功恢复
        archive._try_recover_fname.return_value = "ValidName1"

        # 调用 read_name
        result = FArchive.read_name(archive)

        assert result == "ValidName1"
        # 恢复成功时应记录 debug，不应记录 warning
        mock_logger.debug.assert_called()
        mock_logger.warning.assert_not_called()

    @patch("uasset_read.archive.logger")
    def test_recovery_failure_still_warns(self, mock_logger):
        """恢复失败时应保持 warning。"""
        archive = MagicMock(spec=FArchive)
        archive._name_map = []
        archive._name_count = 0
        archive._source_hint = "test.uasset"
        archive._tolerant = True
        archive._file_size = 100
        archive._recovery_attempts = 0
        archive._recovery_successes = 0
        archive._recovery_failures = 0
        archive._name_warnings_seen = set()  # #411 去重追踪

        # 模拟 read_u32 返回超阈值索引
        original_pos = 10
        archive.tell.return_value = original_pos
        archive.read_u32.side_effect = [1500, 0]  # index=1500, number=0

        # 模拟 _try_recover_fname 恢复失败
        archive._try_recover_fname.return_value = None

        # 恢复失败后 tell 返回原始+8 位置
        archive.tell.return_value = original_pos + 8

        # 调用 read_name
        result = FArchive.read_name(archive)

        assert result == "None"
        # 恢复失败且索引越界时应记录 warning
        mock_logger.warning.assert_called()

    @patch("uasset_read.archive.logger")
    def test_normal_index_no_recovery_no_warning(self, mock_logger):
        """正常索引不应触发恢复，也不应记录 warning。"""
        archive = MagicMock(spec=FArchive)
        archive._name_map = ["Name0", "Name1", "Name2"]
        archive._name_count = 3
        archive._source_hint = "test.uasset"
        archive._tolerant = True
        archive._file_size = 100

        # 模拟 read_u32 返回正常索引
        archive.tell.return_value = 10
        archive.read_u32.side_effect = [1, 0]  # index=1, number=0

        result = FArchive.read_name(archive)

        assert result == "Name1"
        # 正常索引不应触发恢复逻辑
        archive._try_recover_fname.assert_not_called()
        mock_logger.warning.assert_not_called()

    @patch("uasset_read.archive.logger")
    def test_recovery_success_with_number(self, mock_logger):
        """恢复成功且 number > 0 时应返回 Name_number 格式。"""
        archive = MagicMock(spec=FArchive)
        archive._name_map = ["ValidName"]
        archive._name_count = 1
        archive._source_hint = "test.uasset"
        archive._tolerant = True
        archive._file_size = 100
        archive._recovery_attempts = 0
        archive._recovery_successes = 0
        archive._recovery_failures = 0

        original_pos = 10
        archive.tell.return_value = original_pos
        archive.read_u32.side_effect = [2000, 3]  # index=2000, number=3

        # _try_recover_fname 返回带 number 的名称
        archive._try_recover_fname.return_value = "ValidName_3"

        result = FArchive.read_name(archive)

        assert result == "ValidName_3"
        mock_logger.debug.assert_called()
        mock_logger.warning.assert_not_called()
