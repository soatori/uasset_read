#!/usr/bin/env python3
"""测试文件组织和分类工具"""

import os
import re
from pathlib import Path
from typing import Dict, List, Set


# 测试分类规则（13 模块）
TEST_CATEGORIES = {
    "blueprint": {
        "description": "蓝图元数据、节点清理、变量提取、Pin 恢复",
        "patterns": [
            r"test_blueprint_metadata_keys\.py",
            r"test_blueprint_node_cleaner\.py",
            r"test_bp_firstpersoncharacter_validation\.py",
            r"test_constructor_metadata\.py",
            r"test_variable_extractor\.py",
            r"test_ue_mcp_blueprint_comparison\.py",
            r"test_pin_guid_filtering\.py",
            r"test_pin_recovery\.py",
        ],
    },
    "serialization": {
        "description": "类注册、属性解析、fallback、tagged 结构体",
        "patterns": [
            r"test_class_registry\.py",
            r"test_class_serialization_strategy\.py",
            r"test_binary_or_native_handlers\.py",
            r"test_property_parser_error_handling\.py",
            r"test_unknown_property_fallback\.py",
            r"test_fallback_models\.py",
            r"test_export_error_context\.py",
            r"test_soft_object_path_index\.py",
            r"test_struct_lwc\.py",
            r"test_struct_scalar_param\.py",
            r"test_struct_blend_sample\.py",
            r"test_struct_editor_element\.py",
            r"test_framerate_animnotify\.py",
        ],
    },
    "renderer": {
        "description": "JSON/诊断输出、宏展开数据",
        "patterns": [
            r"test_renderers\.py",
            r"test_json_completeness\.py",
            r"test_diagnostic_output\.py",
            r"renderers[/\\]test_json_macro_output\.py",
        ],
    },
    "ir_builder": {
        "description": "IR 构建、状态模型、safe_int",
        "patterns": [
            r"test_ir_builder\.py",
            r"test_ir_structures\.py",
            r"test_status_model\.py",
            r"test_status_model_unified\.py",
            r"test_safe_int\.py",
        ],
    },
    "kismet": {
        "description": "反编译、函数解析、控制流、goto/跳转分析",
        "patterns": [
            r"test_kismet_decompilation\.py",
            r"test_kismet_deprecated_tokens\.py",
            r"test_function_resolver\.py",
            r"test_function_resolver_enhanced\.py",
            r"test_bytecode_scanner_fix\.py",
            r"test_empty_function_enrichment\.py",
            r"test_event_execution_fix\.py",
            r"test_goto_label_emission\.py",
            r"test_jump_analyzer\.py",
            r"test_control_flow_enhanced\.py",
            r"kismet[/\\]test_semantic_multi_call\.py",
        ],
    },
    "graph": {
        "description": "执行链、宏展开、Latent 检测",
        "patterns": [
            r"graph[/\\]test_.*\.py",
        ],
    },
    "cpp": {
        "description": "C++ 类作用域、include 去重、标识符清理",
        "patterns": [
            r"test_cpp_.*\.py",
        ],
    },
    "linker": {
        "description": "生命周期、偏移检查、DependsMap、payload",
        "patterns": [
            r"test_linker_lifecycle\.py",
            r"test_linker_offset_check\.py",
            r"test_lifecycle_preload\.py",
            r"test_depends_map_package_index\.py",
            r"test_depends_map_resolution\.py",
            r"test_payload_offset_strategy\.py",
        ],
    },
    "asset_parsing": {
        "description": "核心 API、版本兼容、截断诊断",
        "patterns": [
            r"test_acceptance\.py",
            r"test_core_api\.py",
            r"test_parse_package_core\.py",
            r"test_package_archive_read\.py",
            r"test_package_bundle\.py",
            r"test_package_summary_fields\.py",
            r"test_version_compatibility\.py",
            r"test_truncated_file\.py",
            r"test_api_cleanup\.py",
            r"test_flow_builder_deprecation\.py",
            r"test_real_asset_e2e\.py",
            r"test_sample_assets_representative\.py",
            r"test_ue_fidelity_integration\.py",
        ],
    },
    "pak": {
        "description": "解压缩、结构体、处理",
        "patterns": [
            r"test_pak_.*\.py",
        ],
    },
    "iostore": {
        "description": "IoStore Reader 分区读取",
        "patterns": [
            r"test_iostore_partition_validation\.py",
        ],
    },
    "archive": {
        "description": "偏移诊断、数组越界、FString、容错",
        "patterns": [
            r"test_archive_diagnostic\.py",
            r"test_array_count_check\.py",
            r"test_fstring_corruption\.py",
            r"test_error_recovery\.py",
            r"test_tolerant_class_specific\.py",
            r"test_tolerant_early_parse_diagnostics\.py",
        ],
    },
    "misc": {
        "description": "动画数据、音效衰减、Raw 读取",
        "patterns": [
            r"test_anim_data_model\.py",
            r"test_sound_attenuation\.py",
            r"test_raw_readers\.py",
            r"test_offset_range_diagnostic\.py",
            r"test_cue4parse_gap_completion\.py",
        ],
    },
}

# 测试标记
TEST_MARKERS = {
    "integration": "需要外部样本资产或较慢路径的集成测试",
    "quality": "C++ 输出质量门禁测试",
    "regression": "真实资产回归测试",
    "slow": "需要大量时间或全量资产扫描的慢速测试",
    "auxiliary": "辅助/历史回归测试，默认单元层不包含",
    "acceptance": "最终验收测试，证明产品目标达成",
}


def categorize_test(test_file: Path) -> str:
    """根据文件名将测试分类"""
    test_name = test_file.name
    rel_path = str(test_file.relative_to(Path(__file__).parent.parent / "tests"))

    for category, config in TEST_CATEGORIES.items():
        for pattern in config["patterns"]:
            if re.search(pattern, rel_path):
                return category
    return "other"


def get_test_markers(test_file: Path) -> Set[str]:
    """提取测试文件中的标记"""
    markers = set()
    try:
        content = test_file.read_text(encoding="utf-8")
        # 查找 @pytest.mark.xxx
        for match in re.finditer(r"@pytest\.mark\.(\w+)", content):
            markers.add(match.group(1))
        # 查找 pytestmark
        for match in re.finditer(r"pytestmark\s*=\s*pytest\.mark\.(\w+)", content):
            markers.add(match.group(1))
    except Exception:
        pass
    return markers


def analyze_tests(tests_dir: Path) -> Dict[str, List[Dict]]:
    """分析测试目录并分类"""
    result = {cat: [] for cat in TEST_CATEGORIES}
    result["other"] = []

    for test_file in sorted(tests_dir.rglob("test_*.py")):
        if "__pycache__" in str(test_file):
            continue

        category = categorize_test(test_file)
        markers = get_test_markers(test_file)

        test_info = {
            "file": test_file.name,
            "path": str(test_file.relative_to(tests_dir.parent)),
            "category": category,
            "markers": markers,
        }
        result[category].append(test_info)

    return result


def print_analysis(result: Dict[str, List[Dict]]) -> None:
    """打印分析结果"""
    print("=" * 60)
    print("测试文件分类分析")
    print("=" * 60)

    total = 0
    for category, tests in result.items():
        if tests:
            print(f"\n{category.upper()} ({len(tests)} 个文件)")
            print("-" * 40)
            for test in tests:
                markers_str = ", ".join(test["markers"]) if test["markers"] else "无标记"
                print(f"  {test['file']}")
                print(f"    标记: {markers_str}")
            total += len(tests)

    print(f"\n{'=' * 60}")
    print(f"总计: {total} 个测试文件")
    print(f"{'=' * 60}")


def generate_test_matrix(result: Dict[str, List[Dict]]) -> str:
    """生成测试矩阵"""
    lines = []
    lines.append("# 测试矩阵")
    lines.append("")
    lines.append("| 模块 | 文件数 | 标记 | 说明 |")
    lines.append("|------|--------|------|------|")

    for category, tests in result.items():
        if tests:
            markers = set()
            for test in tests:
                markers.update(test["markers"])
            markers_str = ", ".join(sorted(markers)) if markers else "-"
            desc = TEST_CATEGORIES.get(category, {}).get("description", "其他")
            lines.append(f"| {category} | {len(tests)} | {markers_str} | {desc} |")

    return "\n".join(lines)


def main():
    """主函数"""
    tests_dir = Path(__file__).parent.parent / "tests"
    result = analyze_tests(tests_dir)
    print_analysis(result)

    # 生成测试矩阵
    matrix = generate_test_matrix(result)
    print("\n" + matrix)


if __name__ == "__main__":
    main()
