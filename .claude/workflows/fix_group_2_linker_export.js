export const meta = {
  name: 'fix-group-2-linker-export',
  description: '第 2 组：Linker + Export 加载链修复（6 issues: #55, #42, #67, #68, #69, #70）',
  phases: [
    { title: '#55 SerializationControlExtensions 条件读取' },
    { title: '#42 FPackageIndex 语义解析' },
    { title: '#67 ScriptSerializationStartOffset preload 使用' },
    { title: '#68 循环依赖 defer 机制' },
    { title: '#69 Preload 递归 SuperStruct 链' },
    { title: '#70 BPGC SCS 组件树序列化' },
    { title: '验证' },
  ],
}

// ============================================================
// 常量
// ============================================================
const PROJECT_ROOT = 'E:/Develop/uasset_read'
const SAMPLES_DIR = 'E:/Develop/lib/Samples'

function parseAgentJson(text) {
  if (!text || typeof text !== 'string') return null
  try { return JSON.parse(text) } catch (_) {}
  const codeBlockMatch = text.match(/```(?:json)?\s*([\s\S]*?)```/)
  if (codeBlockMatch) {
    try { return JSON.parse(codeBlockMatch[1].trim()) } catch (_) {}
  }
  const firstBrace = text.indexOf('{')
  const firstBracket = text.indexOf('[')
  let start = -1, endChar = ''
  if (firstBrace !== -1 && (firstBracket === -1 || firstBrace < firstBracket)) {
    start = firstBrace; endChar = '}'
  } else if (firstBracket !== -1) {
    start = firstBracket; endChar = ']'
  }
  if (start !== -1) {
    const end = text.lastIndexOf(endChar)
    if (end > start) {
      try { return JSON.parse(text.substring(start, end + 1)) } catch (_) {}
    }
  }
  return null
}

function extractJson(raw) {
  if (!raw) return null
  if (typeof raw === 'object') return raw
  return parseAgentJson(raw)
}

const RESULT_SCHEMA = {
  type: 'object',
  properties: {
    status: { type: 'string', enum: ['done', 'failed', 'skipped'] },
    issue: { type: 'string' },
    files_modified: { type: 'array', items: { type: 'string' } },
    tests_added: { type: 'boolean' },
    notes: { type: 'string' },
  },
  required: ['status'],
}

// ============================================================
// #55 (P0): SerializationControlExtensions 条件读取
// ============================================================
phase('#55 SerializationControlExtensions 条件读取')

const issue55 = await agent(`
修复 Issue #55：SerializationControlExtensions 只能按 UClass 条件读取。

问题：当前 property_parser.py:365-389 对所有 UE5.11+ export 无条件读取 SerializationControlExtensions 字节，
但 UE 源码 Class.cpp:1624-1628 表明只有 UClass 对象才序列化此 header。

修复步骤：
1. 读取 src/uasset_read/parsers/property_parser.py 的 parse_properties_from_export() 函数
2. 在 D-02 SerializationControlExtensions 处理块中，添加 class 判断条件
3. 只有当 export 的 class 是 UClass/UBlueprintGeneratedClass 等类对象时才读取
4. 参考 UE 源码 Class.cpp:1624 的 bIsUClass 条件
5. 使用 _skip_class_name 或 resolve_class_name() 判断类名
6. 如果类名未知，记录诊断但不消费字节（降级处理）
7. 编写单元测试验证非 UClass export 不读取控制字节
8. 运行测试验证无回归

参考文件：
- UE5 源码：Engine/Source/Runtime/CoreUObject/Private/UObject/Class.cpp:1624-1642
- 项目文件：src/uasset_read/parsers/property_parser.py:365-389
- 常量定义：src/uasset_read/constants.py（UE5_PROPERTY_TAG_EXTENSION）

返回纯文本 JSON：
{"status": "done/failed", "issue": "#55", "files_modified": ["文件列表"], "tests_added": true/false, "notes": "备注"}`,
  {
    label: 'issue55:serialization-control',
    phase: '#55 SerializationControlExtensions 条件读取',
    schema: RESULT_SCHEMA,
  }
)

// ============================================================
// #42 (P0): FPackageIndex 语义解析
// ============================================================
phase('#42 FPackageIndex 语义解析')

const issue42 = await agent(`
修复 Issue #42：FPackageIndex 语义解析 - 区分 Import/Export 引用并提供反向解析。

问题：当前 PackageIndex 输出为原始 int32，未区分 Import vs Export 引用。

修复步骤：
1. 读取 src/uasset_read/serializers/object_resources.py 的 PackageIndex 类
2. 为 PackageIndex 添加语义化输出方法（或修改 to_dict/序列化）
3. 添加 type 字段：\"import\" / \"export\" / \"null\"
4. 添加 resolved_name 字段：根据 type 查表得到目标条目的 object_name
5. Export 的 class_index 解析为具体类名
6. 修改 linker.py 中 resolve_package_index() 的诊断信息
7. 编写单元测试验证 Import/Export/Null 三种情况
8. 运行测试验证无回归

参考文件：
- UE5 源码：Engine/Source/Runtime/CoreUObject/Public/UObject/ObjectResource.h
- 项目文件：src/uasset_read/serializers/object_resources.py:31-143
- Linker：src/uasset_read/link/linker.py:173-211

返回纯文本 JSON：
{"status": "done/failed", "issue": "#42", "files_modified": ["文件列表"], "tests_added": true/false, "notes": "备注"}`,
  {
    label: 'issue42:package-index',
    phase: '#42 FPackageIndex 语义解析',
    schema: RESULT_SCHEMA,
  }
)

// ============================================================
// #67 (P2): ScriptSerializationStartOffset preload 使用
// ============================================================
phase('#67 ScriptSerializationStartOffset preload 使用')

const issue67 = await agent(`
修复 Issue #67：ScriptSerializationStartOffset 未在 preload 中使用。

问题：preload() 始终使用 serial_offset 作为起始位置，未检查 ScriptSerializationStartOffset。
UE 源码 LinkerLoad.cpp:4793-4802 表明当 bDoesSavedClassMatchActualClass 为 false 时，
使用 ScriptSerializationStartOffset 作为 payload 起始位置。

修复步骤：
1. 读取 src/uasset_read/link/linker.py 的 preload() 方法
2. 在 offset validation 之后、seek 之前，添加 ScriptSerializationStartOffset 检查
3. 检查 UE 版本 >= SCRIPT_SERIALIZATION_OFFSET（参考 constants.py）
4. 如果 script_serialization_start_offset > 0，使用 serial_offset + script_serialization_start_offset
5. 设置 serial_size 为 script_serialization_end_offset - script_serialization_start_offset
6. 编写单元测试验证不同偏移场景
7. 运行测试验证无回归

参考文件：
- UE5 源码：LinkerLoad.cpp:4793-4802
- 项目文件：src/uasset_read/link/linker.py:218-359
- 常量：src/uasset_read/constants.py（SCRIPT_SERIALIZATION_OFFSET）

返回纯文本 JSON：
{"status": "done/failed", "issue": "#67", "files_modified": ["文件列表"], "tests_added": true/false, "notes": "备注"}`,
  {
    label: 'issue67:script-serialization-offset',
    phase: '#67 ScriptSerializationStartOffset preload 使用',
    schema: RESULT_SCHEMA,
  }
)

// ============================================================
// #68 (P2): 循环依赖 defer 机制
// ============================================================
phase('#68 循环依赖 defer 机制')

const issue68 = await agent(`
修复 Issue #68：缺少循环依赖 defer 机制（蓝图类/结构体）。

问题：当前 preload() 按 index 顺序执行，无 defer 机制。对于循环引用的蓝图资产可能导致无限递归。

修复步骤：
1. 读取 src/uasset_read/link/linker.py 的 preload() 方法
2. 添加 _preloading_in_progress 集合（正在 preload 的 export index）
3. 在 preload() 开始时检查当前 index 是否已在 _preloading_in_progress 中
4. 如果是，记录循环依赖诊断，设置 parse_status=\"deferred\"，return
5. 将 index 加入 _preloading_in_progress，完成 preload 后移除
6. 在 post_load() 的 _resolve_property_references() 中处理 deferred 引用
7. 编写单元测试验证循环依赖场景
8. 运行测试验证无回归

参考文件：
- UE5 源码：LinkerLoad.cpp:4719-4727（USE_CIRCULAR_DEPENDENCY_LOAD_DEFERRING）
- 项目文件：src/uasset_read/link/linker.py:218-359

返回纯文本 JSON：
{"status": "done/failed", "issue": "#68", "files_modified": ["文件列表"], "tests_added": true/false, "notes": "备注"}`,
  {
    label: 'issue68:circular-dependency',
    phase: '#68 循环依赖 defer 机制',
    schema: RESULT_SCHEMA,
  }
)

// ============================================================
// #69 (P3): Preload 递归 SuperStruct 链
// ============================================================
phase('#69 Preload 递归 SuperStruct 链')

const issue69 = await agent(`
修复 Issue #69：Preload 不递归加载 SuperStruct 链。

问题：preload() 不递归加载 super 链，可能导致属性继承信息不完整。

修复步骤：
1. 读取 src/uasset_read/link/linker.py 的 preload() 方法
2. 在 preload() 开头，检查当前 export 是否为 UStruct（UClass 或 UScriptStruct）
3. 判断依据：class_name 是否在已知 UStruct 类列表中（如 BlueprintGeneratedClass, ScriptStruct 等）
4. 如果有 super_index 且 super 对象未 preload，递归调用 preload(super_export_index)
5. 添加递归深度限制防止无限递归
6. 编写单元测试验证继承链加载
7. 运行测试验证无回归

参考文件：
- UE5 源码：LinkerLoad.cpp:4760-4767
- 项目文件：src/uasset_read/link/linker.py:218-359
- ObjectExport：src/uasset_read/serializers/object_resources.py:174-215

返回纯文本 JSON：
{"status": "done/failed", "issue": "#69", "files_modified": ["文件列表"], "tests_added": true/false, "notes": "备注"}`,
  {
    label: 'issue69:superstruct-recursive',
    phase: '#69 Preload 递归 SuperStruct 链',
    schema: RESULT_SCHEMA,
  }
)

// ============================================================
// #70 (P2): BlueprintGeneratedClass SCS 组件树序列化
// ============================================================
phase('#70 BPGC SCS 组件树序列化')

const issue70 = await agent(`
修复 Issue #70：BlueprintGeneratedClass SCS 组件树序列化完整性。

问题：当前蓝图解析可能遗漏 SCS 组件树的完整序列化。

修复步骤：
1. 读取 src/uasset_read/blueprint/component_extractor.py 了解当前 SCS 处理
2. 检查 BlueprintGeneratedClass handler 是否覆盖 SimpleConstructionScript 序列化
3. 如果未覆盖，添加 SCS 节点链解析：
   - USCS_Node 字段：ComponentClass, ComponentTemplate, AttachToName, AttachToComponent, ChildrenNodes
4. 提取组件类名、模板、附加关系到 IR
5. 编写单元测试验证 SCS 组件树输出
6. 运行测试验证无回归

参考文件：
- UE5 源码：BlueprintGeneratedClass.cpp, SimpleConstructionScript.h
- 项目文件：src/uasset_read/blueprint/component_extractor.py
- 蓝图模块：src/uasset_read/blueprint/

返回纯文本 JSON：
{"status": "done/failed", "issue": "#70", "files_modified": ["文件列表"], "tests_added": true/false, "notes": "备注"}`,
  {
    label: 'issue70:bpgc-scs',
    phase: '#70 BPGC SCS 组件树序列化',
    schema: RESULT_SCHEMA,
  }
)

// ============================================================
// 验证
// ============================================================
phase('验证')

const issues = [
  { id: '#55', result: issue55 },
  { id: '#42', result: issue42 },
  { id: '#67', result: issue67 },
  { id: '#68', result: issue68 },
  { id: '#69', result: issue69 },
  { id: '#70', result: issue70 },
]

const summary = issues.map(i => {
  const json = extractJson(i.result)
  return {
    issue: i.id,
    status: json?.status || 'unknown',
    files_modified: json?.files_modified || [],
    tests_added: json?.tests_added || false,
    notes: json?.notes || '',
  }
})

const passed = summary.filter(s => s.status === 'done').length
const failed = summary.filter(s => s.status === 'failed').length
const skipped = summary.filter(s => s.status === 'skipped').length

log(`第 2 组修复完成: ${passed} done, ${failed} failed, ${skipped} skipped`)

// 运行测试
const verifyResult = await agent(`
验证第 2 组修复：

1. 运行完整测试套件：cd ${PROJECT_ROOT} && python -m pytest tests/ -x --tb=short 2>&1 | tail -30
2. 用实际资产验证：
   - python run.py "${SAMPLES_DIR}/FirstPerson/Content/Characters/Mannequins/Anims/Rifle/AO_Rifle.uasset" 2>&1 | head -30
3. 确认无回归

返回纯文本 JSON：
{"status": "pass/fail", "tests_passed": 数字, "tests_failed": 数字, "total_tests": 数字, "regression": true/false, "notes": "备注"}`,
  {
    label: 'verify:all-tests',
    phase: '验证',
    schema: {
      type: 'object',
      properties: {
        status: { type: 'string', enum: ['pass', 'fail'] },
        tests_passed: { type: 'number' },
        tests_failed: { type: 'number' },
        total_tests: { type: 'number' },
        regression: { type: 'boolean' },
        notes: { type: 'string' },
      },
      required: ['status'],
    },
  }
)

const verifyJson = extractJson(verifyResult)

return {
  group: '第 2 组: Linker + Export 加载链',
  issues: summary,
  passed,
  failed,
  skipped,
  verify: verifyJson,
}
