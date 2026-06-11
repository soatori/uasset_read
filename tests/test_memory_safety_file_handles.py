"""文件句柄安全测试 — 验证 context manager 和 close() 行为"""
import pytest
from pathlib import Path


class TestFileHandleCleanup:
    """文件句柄清理测试"""

    def test_farchive_context_manager(self, tmp_path):
        """FArchive 支持 context manager"""
        from uasset_read.archive import FArchive

        test_file = tmp_path / "test.uasset"
        test_file.write_bytes(b"\xc1\x9a\x2b\x2a" + b"\x00" * 100)

        with FArchive(str(test_file)) as archive:
            archive.read_u32()

        # 退出 context 后应可删除（Windows 上未关闭的文件无法删除）
        try:
            test_file.unlink()
        except PermissionError:
            pytest.fail("文件句柄未关闭")

    def test_farchive_close_method(self, tmp_path):
        """FArchive.close() 关闭文件句柄"""
        from uasset_read.archive import FArchive

        test_file = tmp_path / "test.uasset"
        test_file.write_bytes(b"\x00" * 100)

        archive = FArchive(str(test_file))
        archive.close()

        # 关闭后应可删除
        try:
            test_file.unlink()
        except PermissionError:
            pytest.fail("close() 未关闭文件句柄")

    def test_farchive_double_close(self, tmp_path):
        """FArchive.close() 多次调用不抛异常"""
        from uasset_read.archive import FArchive

        test_file = tmp_path / "test.uasset"
        test_file.write_bytes(b"\x00" * 100)

        archive = FArchive(str(test_file))
        archive.close()
        archive.close()  # 第二次关闭不应抛异常

    def test_farchive_del_after_close(self, tmp_path):
        """FArchive.__del__ 在 close() 后安全调用"""
        from uasset_read.archive import FArchive

        test_file = tmp_path / "test.uasset"
        test_file.write_bytes(b"\x00" * 100)

        archive = FArchive(str(test_file))
        archive.close()
        del archive  # __del__ 不应抛异常

    def test_farchive_context_manager_exception(self, tmp_path):
        """FArchive context manager 在异常时仍关闭文件"""
        from uasset_read.archive import FArchive

        test_file = tmp_path / "test.uasset"
        test_file.write_bytes(b"\x00" * 100)

        with pytest.raises(ValueError):
            with FArchive(str(test_file)) as archive:
                archive.read_u32()
                raise ValueError("模拟异常")

        # 异常后文件应已关闭
        try:
            test_file.unlink()
        except PermissionError:
            pytest.fail("异常后文件句柄未关闭")

    def test_pak_reader_context_manager(self, tmp_path):
        """PakFileReader 支持 context manager"""
        from uasset_read.pak.reader import PakFileReader

        pak_file = tmp_path / "test.pak"
        pak_file.write_bytes(b"\x00" * 1000)

        try:
            with PakFileReader(str(pak_file)) as reader:
                pass
        except Exception:
            pass  # 读取失败没关系，只测试 context manager

        try:
            pak_file.unlink()
        except PermissionError:
            pytest.fail("PakFileReader context manager 未关闭文件")

    def test_pak_reader_close_method(self, tmp_path):
        """PakFileReader.close() 关闭文件句柄"""
        from uasset_read.pak.reader import PakFileReader

        pak_file = tmp_path / "test.pak"
        pak_file.write_bytes(b"\x00" * 1000)

        reader = PakFileReader(str(pak_file))
        reader.close()

        try:
            pak_file.unlink()
        except PermissionError:
            pytest.fail("PakFileReader.close() 未关闭文件句柄")

    def test_pak_reader_double_close(self, tmp_path):
        """PakFileReader.close() 多次调用不抛异常"""
        from uasset_read.pak.reader import PakFileReader

        pak_file = tmp_path / "test.pak"
        pak_file.write_bytes(b"\x00" * 1000)

        reader = PakFileReader(str(pak_file))
        reader.close()
        reader.close()  # 第二次关闭不应抛异常

    def test_iostore_reader_context_manager(self, tmp_path):
        """IoStoreReader 支持 context manager"""
        from uasset_read.iostore.reader import IoStoreReader

        # 创建假 utoc 文件
        utoc_file = tmp_path / "test.utoc"
        utoc_file.write_bytes(b"\x00" * 1000)

        try:
            with IoStoreReader(str(utoc_file)) as reader:
                pass
        except Exception:
            pass  # 读取失败没关系

        try:
            utoc_file.unlink()
        except PermissionError:
            pytest.fail("IoStoreReader context manager 未关闭文件")

    def test_iostore_reader_close_method(self, tmp_path):
        """IoStoreReader.close() 关闭文件句柄"""
        from uasset_read.iostore.reader import IoStoreReader

        utoc_file = tmp_path / "test.utoc"
        utoc_file.write_bytes(b"\x00" * 1000)

        reader = IoStoreReader(str(utoc_file))
        reader.close()

        try:
            utoc_file.unlink()
        except PermissionError:
            pytest.fail("IoStoreReader.close() 未关闭文件句柄")

    def test_iostore_reader_double_close(self, tmp_path):
        """IoStoreReader.close() 多次调用不抛异常"""
        from uasset_read.iostore.reader import IoStoreReader

        utoc_file = tmp_path / "test.utoc"
        utoc_file.write_bytes(b"\x00" * 1000)

        reader = IoStoreReader(str(utoc_file))
        reader.close()
        reader.close()  # 第二次关闭不应抛异常
