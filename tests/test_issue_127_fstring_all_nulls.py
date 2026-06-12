"""
Issue #127: FString 全空字节诊断增强

测试 FString 全空字节情况的诊断输出。

问题背景：
- NS_Trangle.uasset 出现 FString 数据异常：全空字节
- 原诊断只有 pos/length，缺少结构化诊断码
- 需要区分"资产数据损坏"和"解析器 offset 漂移"

修复内容：
- 在 FString all-null 诊断中添加 diagnostic_code=CORRUPTED_FSTRING_ALL_NULLS
- 添加 likely_cause 字段提示可能原因
"""

import pytest
import json
import logging
from io import StringIO

from uasset_read.core import parse_single
from uasset_read.archive import FArchive


NS_TRANGLE = "E:/Develop/lib/UnrealEngine/Samples/CiciToonCharacterShaderPa/Content/CiciToonCharacterShaderPak/FX/NS_Trangle.uasset"


@pytest.mark.skipif(
    not __import__('pathlib').Path(NS_TRANGLE).exists(),
    reason="NS_Trangle.uasset not available"
)
class TestIssue127FStringAllNulls:
    """Issue #127: FString 全空字节诊断"""

    def test_ns_trangle_no_crash(self):
        """NS_Trangle 解析不崩溃"""
        result = parse_single(NS_TRANGLE, format="json", tolerant=True)
        data = json.loads(result)

        # 应该成功解析（可能是 partial 但不应该是 failed）
        status = data.get("status", {})
        assert status.get("status") != "failed", \
            f"NS_Trangle should not fail: {status.get('message')}"

    def test_fstring_corruption_diagnostic_has_code(self):
        """FString all-null 诊断应包含 diagnostic_code"""
        log_stream = StringIO()
        handler = logging.StreamHandler(log_stream)
        handler.setLevel(logging.ERROR)
        logger = logging.getLogger("uasset_read.archive")
        logger.addHandler(handler)
        logger.setLevel(logging.ERROR)

        try:
            parse_single(NS_TRANGLE, format="json", tolerant=True)
            log_content = log_stream.getvalue()

            # 如果触发了 all-null 诊断，应该包含 diagnostic_code
            if "all nulls" in log_content:
                assert "diagnostic_code=CORRUPTED_FSTRING_ALL_NULLS" in log_content, \
                    "FString all-null diagnostic should include diagnostic_code"
                assert "likely_cause=" in log_content, \
                    "FString all-null diagnostic should include likely_cause"
        finally:
            logger.removeHandler(handler)


class TestFStringArchiveDiagnostic:
    """FArchive FString 诊断测试"""

    def test_archive_fstring_all_nulls_returns_empty(self):
        """FArchive 读取全空 FString 应返回空字符串"""
        import tempfile
        import os

        # 创建一个包含全空 FString 的临时文件
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, mode='wb') as f:
                # 写入 FString: length=10, 然后 10 个空字节
                f.write(b'\x0a\x00\x00\x00')  # length = 10
                f.write(b'\x00' * 10)  # 10 null bytes
                temp_path = f.name

            archive = FArchive(temp_path)
            result = archive.read_fstring()

            # 应该返回空字符串（all-null FString 无法恢复）
            assert result == "", "All-null FString should return empty string"
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except PermissionError:
                    pass
