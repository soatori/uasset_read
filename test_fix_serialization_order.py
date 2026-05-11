"""
测试序列化顺序修复方案
"""

import sys
sys.path.insert(0, 'E:/Develop/uasset_read')

from uasset_read.archive import FArchive
from uasset_read.constants import PACKAGE_FILE_TAG
from uasset_read.serializers import (
    PackageFileSummary, ObjectImport, ObjectExport,
    read_package_summary, read_name_table, read_import_map, read_export_map
)

def analyze_node_serialization(file_path: str, node_name: str):
    """
    分析节点的序列化数据，确定正确的 pins_offset
    """
    # 打开文件
    archive = FArchive(file_path)

    # 读取头
    summary = read_package_summary(archive)
    archive.seek(summary.name_offset)
    name_map = read_name_table(archive, summary.name_count)

    # 读取 import/export maps
    archive.seek(summary.import_offset)
    import_map = read_import_map(archive, summary.import_count, name_map)

    archive.seek(summary.export_offset)
    export_map = read_export_map(archive, summary.export_count, name_map, summary)

    # 查找指定节点
    node_export = None
    for export in export_map:
        if export.object_name == node_name:
            node_export = export
            break

    if not node_export:
        print(f"Node {node_name} not found")
        return

    print(f"Node: {node_name}")
    print(f"  serial_offset: {node_export.serial_offset:#x}")
    print(f"  serial_size: {node_export.serial_size}")
    print(f"  script_serial_offset: {node_export.script_serial_offset:#x}")
    print(f"  script_serial_size: {node_export.script_serial_size}")

    # 定位到节点数据开始位置
    start_offset = node_export.serial_offset + node_export.script_serial_offset + node_export.script_serial_size
    end_offset = node_export.serial_offset + node_export.serial_size

    print(f"  Data range: {start_offset:#x} - {end_offset:#x}")

    # 反向查找策略：从数据末尾向前查找 NodeGuid (16 bytes FGuid)
    # NodeGuid 应该是合理的 GUID 值（不是全 0 或全 FF）
    archive.seek(end_offset - 100)  # 从末尾前 100 bytes 开始查找

    # 读取最后 100 bytes 的数据
    data = archive.read_bytes(100)

    print(f"\n  Searching for NodeGuid in last 100 bytes...")

    # 查找可能的 NodeGuid（16 bytes）
    for i in range(0, 100 - 16, 4):  # 每 4 bytes 对齐
        guid_bytes = data[i:i+16]
        # 检查是否是有效的 GUID（不全为 0 或 FF）
        if guid_bytes != b'\x00' * 16 and guid_bytes != b'\xFF' * 16:
            # 检查前 4 bytes 是否可能是 NodePosY（通常在 0-2000 范围）
            if i >= 8:  # 需要有 NodePosY 和 NodePosX
                pos_y_bytes = data[i-4:i]
                pos_x_bytes = data[i-8:i-4]

                # 尝试解析为 int32
                import struct
                pos_y = struct.unpack('<i', pos_y_bytes)[0]
                pos_x = struct.unpack('<i', pos_x_bytes)[0]

                # 检查 NodePos 是否合理（通常在 -1000 到 2000 范围）
                if -1000 <= pos_x <= 2000 and -1000 <= pos_y <= 2000:
                    guid_pos = end_offset - 100 + i
                    pos_y_pos = guid_pos - 4
                    pos_x_pos = guid_pos - 8

                    print(f"  Found possible NodePos/NodeGuid:")
                    print(f"    NodePosX at {pos_x_pos:#x}: {pos_x}")
                    print(f"    NodePosY at {pos_y_pos:#x}: {pos_y}")
                    print(f"    NodeGuid at {guid_pos:#x}: {guid_bytes.hex()}")

                    # NodePos 之后应该是 NodeComment (FString)
                    # FString 格式：int32 length + UTF-16 string + null terminator
                    comment_pos = guid_pos + 16
                    archive.seek(comment_pos)
                    comment_len = archive.read_i32()

                    print(f"    NodeComment at {comment_pos:#x}: length={comment_len}")

                    # NodeComment 之后应该是 Pins 数组
                    if comment_len >= 0:
                        # FString: 4 bytes length + (length * 2) bytes UTF-16 + 2 bytes null terminator
                        comment_size = 4 + (abs(comment_len) * 2 if comment_len != 0 else 0) + (2 if comment_len > 0 else 0)
                        pins_start_pos = comment_pos + comment_size

                        # 但 NodeComment 可能是空字符串（length = 0）
                        # 让我们检查几种可能性

                        # 可能性 1：NodeComment 为空（length = 0，不占用额外空间）
                        archive.seek(guid_pos + 16)
                        test_comment_len_1 = archive.read_i32()

                        # 可能性 2：NodeComment 有内容
                        # 实际上，FString 在 length = 0 时占用 4 bytes（只有 length 字段）

                        print(f"\n  Checking pins_offset candidates:")
                        print(f"    Candidate 1 (after NodeGuid): {guid_pos + 16:#x}")
                        print(f"    Candidate 2 (after NodeGuid+4): {guid_pos + 20:#x}")
                        print(f"    Candidate 3 (after NodeGuid+8): {guid_pos + 24:#x}")

                        # 测试每个候选位置
                        for offset_delta in [16, 20, 24, 28]:
                            test_pos = guid_pos + offset_delta
                            archive.seek(test_pos)
                            test_count = archive.read_i32()

                            if 1 <= test_count <= 20:
                                print(f"    Candidate at {test_pos:#x}: pins_count={test_count} ✓")

                                # 验证后续数据
                                test_null = archive.read_i32()
                                print(f"      bNullPtr: {test_null}")

                                if test_null == 0:
                                    test_owning = archive.read_i32()
                                    print(f"      OwningNode: {test_owning}")

                                    # 这可能就是正确的 pins_offset
                                    pins_offset = test_pos - node_export.serial_offset
                                    print(f"\n  ✓✓ Correct pins_offset: {pins_offset:#x}")
                                    return pins_offset

                    break

    print(f"\n  Could not find valid NodePos/NodeGuid pattern")
    return None

# 测试
if __name__ == '__main__':
    file_path = 'E:/Develop/lib/UnrealEngine/Samples/FirstPerson/Content/FirstPerson/Blueprints/BP_FirstPersonCharacter.uasset'

    # 测试几个 K2Node_CallFunction 节点
    nodes_to_test = ['K2Node_CallFunction_8428', 'K2Node_CallFunction_8429']

    for node_name in nodes_to_test:
        print("=" * 60)
        pins_offset = analyze_node_serialization(file_path, node_name)
        print()