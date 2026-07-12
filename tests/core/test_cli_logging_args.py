"""测试日志相关的 CLI 参数。"""
import subprocess
import sys
import pytest


class TestCLILoggingArgs:
    """验证日志 CLI 参数正确传递。"""

    def test_log_max_total_mb_argument(self):
        """--log-max-total-mb 参数应被接受。"""
        result = subprocess.run(
            [sys.executable, "-m", "uasset_read", "--help"],
            capture_output=True,
            text=True,
        )
        assert "--log-max-total-mb" in result.stdout

    def test_log_keep_latest_argument(self):
        """--log-keep-latest 参数应被接受。"""
        result = subprocess.run(
            [sys.executable, "-m", "uasset_read", "--help"],
            capture_output=True,
            text=True,
        )
        assert "--log-keep-latest" in result.stdout

    def test_log_max_total_mb_help_text(self):
        """--log-max-total-mb 帮助文本应包含描述。"""
        result = subprocess.run(
            [sys.executable, "-m", "uasset_read", "--help"],
            capture_output=True,
            text=True,
        )
        assert "cap total log storage" in result.stdout

    def test_log_keep_latest_help_text(self):
        """--log-keep-latest 帮助文本应包含描述。"""
        result = subprocess.run(
            [sys.executable, "-m", "uasset_read", "--help"],
            capture_output=True,
            text=True,
        )
        assert "keep only the newest" in result.stdout
