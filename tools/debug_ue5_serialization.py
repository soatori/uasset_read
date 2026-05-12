"""UE5 序列化调试工具 — 记录每个 PropertyTag 的读取过程。

Phase 33a-03: 节点序列化偏移校验。

用法:
    python tools/debug_ue5_serialization.py <file.uasset>

输出:
    debug_output_v2.json — 包含所有 PropertyTag 的详细信息
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from uasset_read.archive import FArchive
from uasset_read.serializers.package_summary import read_package_summary, read_name_table
from uasset_read.serializers.object_resources import read_import_map, read_export_map
from uasset_read.serializers.property_tags import read_property_tag
from uasset_read.constants import PROPERTY_TAG_COMPLETE_TYPE_NAME


def debug_uasset_serialization(asset_path: str) -> dict:
    """调试 .uasset 文件的序列化过程。

    记录每个 PropertyTag 的：
    - 开始/结束偏移
    - 名称、类型、大小
    - 实际读取字节数
    - 差异（delta = read_bytes - size）
    """
    archive = FArchive(asset_path, tolerant=True)
    summary = read_package_summary(archive)
    name_map = read_name_table(archive, summary)
    import_map = read_import_map(archive, summary, name_map)
    export_map = read_export_map(archive, summary, name_map)

    results = {
        "file": asset_path,
        "file_size": archive.total_size(),
        "legacy_version": summary.legacy_file_version,
        "ue5_version": summary.file_version_ue5,
        "exports": [],
        "errors": [],
    }

    for export_idx, export in enumerate(export_map):
        if export.serial_size <= 0:
            continue

        export_info = {
            "index": export_idx,
            "name": export.object_name,
            "class": export.class_index.index,
            "serial_offset": export.serial_offset,
            "serial_size": export.serial_size,
            "script_serial_offset": export.script_serial_offset,
            "script_serial_size": export.script_serial_size,
            "property_tags": [],
        }

        if export.script_serial_size <= 0:
            results["exports"].append(export_info)
            continue

        script_start = export.serial_offset + export.script_serial_offset
        script_end = script_start + export.script_serial_size
        archive.seek(script_start)

        # UE5 >= 1011: SerializationControlExtensions
        if summary.file_version_ue5 >= 1011:
            ctrl = archive.read_u8()
            if ctrl & 0x02:
                archive.read_u8()

        while archive.tell() < script_end:
            tag_start = archive.tell()

            try:
                tag = read_property_tag(
                    archive, name_map, summary.legacy_file_version,
                    summary.file_version_ue5, tolerant=True,
                )
            except Exception as e:
                results["errors"].append(f"Export {export_idx} ({export.object_name}): {e}")
                break

            if tag.name == "None":
                break

            tag_info = {
                "name": tag.name,
                "type": tag.type,
                "size": tag.size,
                "start_offset": tag_start,
                "after_header_offset": archive.tell(),
            }

            # 读取属性值（根据大小跳过）
            if tag.size > 0:
                value_start = archive.tell()
                try:
                    archive.seek(value_start + tag.size)
                    actual_read = archive.tell() - value_start
                    tag_info["end_offset"] = archive.tell()
                    tag_info["actual_read_bytes"] = actual_read
                    tag_info["delta"] = actual_read - tag.size
                except Exception as e:
                    tag_info["end_offset"] = archive.tell()
                    tag_info["actual_read_bytes"] = archive.tell() - value_start
                    tag_info["delta"] = "error"
                    tag_info["error"] = str(e)
            else:
                tag_info["end_offset"] = archive.tell()
                tag_info["actual_read_bytes"] = 0
                tag_info["delta"] = 0

            export_info["property_tags"].append(tag_info)

        results["exports"].append(export_info)

    archive.close()
    return results


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <file.uasset>")
        sys.exit(1)

    asset_path = sys.argv[1]
    if not Path(asset_path).exists():
        print(f"Error: File not found: {asset_path}")
        sys.exit(1)

    print(f"Debugging: {asset_path}")
    results = debug_uasset_serialization(asset_path)

    output_file = "debug_output_v2.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # 打印统计摘要
    total_tags = sum(len(e["property_tags"]) for e in results["exports"])
    total_exports = len(results["exports"])
    deltas = []
    for export in results["exports"]:
        for tag in export["property_tags"]:
            if isinstance(tag.get("delta"), (int, float)):
                deltas.append(tag["delta"])

    non_zero_deltas = [d for d in deltas if d != 0]

    print(f"Exports analyzed: {total_exports}")
    print(f"PropertyTags parsed: {total_tags}")
    print(f"Non-zero deltas: {len(non_zero_deltas)}")
    if non_zero_deltas:
        print(f"Delta range: {min(non_zero_deltas)} to {max(non_zero_deltas)}")
    print(f"Errors: {len(results['errors'])}")
    print(f"Output: {output_file}")


if __name__ == "__main__":
    main()
