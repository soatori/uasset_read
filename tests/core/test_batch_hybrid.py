"""批量解析混合模式测试。"""
import logging
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path


class TestHybridIsolation:
    """#346: 智能混合模式测试。"""

    def test_small_files_not_isolated(self):
        """小文件（< 20MB）应走非隔离路径。"""
        from uasset_read.memory_safety import should_isolate, FileSizeTier

        # 10MB 文件
        result = should_isolate(10 * 1024 * 1024, FileSizeTier.SMALL)
        assert result is False

    def test_large_files_isolated(self):
        """大文件（> 100MB）应走隔离路径。"""
        from uasset_read.memory_safety import should_isolate, FileSizeTier

        result = should_isolate(200 * 1024 * 1024, FileSizeTier.LARGE)
        assert result is True

    def test_file_size_tier_auto_selection(self):
        """FileSizeTier.from_size 应根据文件大小返回正确分级。"""
        from uasset_read.memory_safety import FileSizeTier

        assert FileSizeTier.from_size(10 * 1024 * 1024) == FileSizeTier.SMALL  # 10MB
        assert FileSizeTier.from_size(50 * 1024 * 1024) == FileSizeTier.MEDIUM  # 50MB
        assert FileSizeTier.from_size(150 * 1024 * 1024) == FileSizeTier.LARGE  # 150MB

    def test_medium_file_below_threshold_not_isolated(self):
        """中等文件（< 50MB）不应隔离。"""
        from uasset_read.memory_safety import should_isolate, FileSizeTier

        result = should_isolate(30 * 1024 * 1024, FileSizeTier.MEDIUM)  # 30MB
        assert result is False

    def test_medium_file_above_threshold_isolated(self):
        """中等文件（>= 50MB）应隔离。"""
        from uasset_read.memory_safety import should_isolate, FileSizeTier

        result = should_isolate(60 * 1024 * 1024, FileSizeTier.MEDIUM)  # 60MB
        assert result is True

    def test_auto_mode_integration(self):
        """parse_batch auto 模式应调用 should_isolate 决定隔离策略。"""
        import logging
        from uasset_read.core import parse_batch
        from pathlib import Path, PurePosixPath

        # 保存 uasset_read logger 的日志配置状态
        ua_logger = logging.getLogger("uasset_read")
        old_handlers = ua_logger.handlers[:]
        old_propagate = ua_logger.propagate
        old_level = ua_logger.level

        fake_file = PurePosixPath('/tmp/fake/test.uasset')
        try:
            with patch.object(Path, 'is_dir', return_value=True):
                with patch.object(Path, 'rglob', side_effect=[
                    [fake_file],  # *.uasset
                    [],           # *.umap
                ]):
                    with patch('uasset_read.memory_safety.get_memory_stats') as mock_stats:
                        mock_stats.return_value = MagicMock(usage_percent=0.1)
                        with patch('uasset_read.memory_safety.check_file_size', return_value=10 * 1024 * 1024):
                            with patch('uasset_read.memory_safety.FileSizeTier') as mock_tier:
                                mock_tier.from_size.return_value = 'SMALL'
                                with patch('uasset_read.memory_safety.should_isolate', return_value=False) as mock_should:
                                    with patch('uasset_read.core.parse_single') as mock_parse:
                                        mock_parse.return_value = MagicMock()
                                        mock_parse.return_value.status = 'success'
                                        parse_batch(
                                            '/tmp/fake',
                                            isolate_assets="auto",
                                        )
                                        mock_should.assert_called()
        finally:
            # 恢复 uasset_read logger 的日志配置状态，避免污染其他测试
            ua_logger.handlers = old_handlers
            ua_logger.propagate = old_propagate
            ua_logger.level = old_level


def test_auto_mode_integration_does_not_configure_logging():
    """test_auto_mode_integration 不应触发全局日志配置。"""
    ua_logger = logging.getLogger("uasset_read")
    old_handlers = ua_logger.handlers[:]
    old_propagate = ua_logger.propagate
    old_level = ua_logger.level

    from uasset_read.core import parse_batch
    from pathlib import PurePosixPath

    fake_file = PurePosixPath('/tmp/fake/test.uasset')
    try:
        with patch.object(Path, 'is_dir', return_value=True):
            with patch.object(Path, 'rglob', side_effect=[
                [fake_file],  # *.uasset
                [],           # *.umap
            ]):
                with patch('uasset_read.memory_safety.get_memory_stats') as mock_stats:
                    mock_stats.return_value = MagicMock(usage_percent=0.1)
                    with patch('uasset_read.memory_safety.check_file_size', return_value=10 * 1024 * 1024):
                        with patch('uasset_read.memory_safety.FileSizeTier') as mock_tier:
                            mock_tier.from_size.return_value = 'SMALL'
                            with patch('uasset_read.memory_safety.should_isolate', return_value=False):
                                with patch('uasset_read.core.parse_single') as mock_parse:
                                    mock_parse.return_value = MagicMock()
                                    mock_parse.return_value.status = 'success'
                                    parse_batch(
                                        '/tmp/fake',
                                        isolate_assets="auto",
                                    )
    finally:
        # 恢复 uasset_read logger 的日志配置状态，避免污染其他测试
        ua_logger.handlers = old_handlers
        ua_logger.propagate = old_propagate
        ua_logger.level = old_level

    # 验证 uasset_read logger 的 propagate 未被修改
    assert ua_logger.handlers == old_handlers
    assert ua_logger.propagate == old_propagate
    assert ua_logger.level == old_level


def test_parse_batch_invalid_isolate_assets():
    """parse_batch 应拒绝无效的 isolate_assets 值。"""
    from uasset_read.core import parse_batch
    from pathlib import Path

    with patch.object(Path, 'is_dir', return_value=True):
        with patch.object(Path, 'rglob', side_effect=[[], []]):
            with pytest.raises(ValueError, match="isolate_assets must be"):
                parse_batch(
                    '/tmp/fake',
                    isolate_assets="invalid_value",
                )
