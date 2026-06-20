export const meta = {
  name: 'fix-plan-execution',
  description: '执行 v0.4.4 警告消除修复计划（P0-P4）',
  phases: [
    { title: 'P0: 结构体解析器' },
    { title: 'P2: EExprToken 扩展' },
    { title: 'P1: Texture2D 适配' },
    { title: 'P4: 诊断增强' },
    { title: '验证' },
  ],
};

// 统一结果 schema（模板规范要求）
const RESULT_SCHEMA = {
  type: 'object',
  properties: {
    status: { type: 'string', enum: ['done', 'failed', 'skipped'] },
    struct_name: { type: 'string' },
    fields_added: { type: 'array', items: { type: 'string' } },
    tests_added: { type: 'boolean' },
    token_0xff: { type: 'string' },
    token_0xf9: { type: 'string' },
    expr_class_added: { type: 'boolean' },
    ue5_format_analyzed: { type: 'boolean' },
    new_fields_detected: { type: 'array', items: { type: 'string' } },
    size_anomaly_resolved: { type: 'boolean' },
    fstring_enhanced: { type: 'boolean' },
    package_index_enhanced: { type: 'boolean' },
    already_existed: { type: 'boolean' },
    notes: { type: 'string' },
  },
  required: ['status'],
};
phase('P0: 结构体解析器');

const p0Tasks = [
  {
    name: 'BlendSample',
    prompt: `在 UE5 源码中查找 FBlendSample 结构体定义，然后在 uasset_read 项目中实现解析器。

步骤：
1. 搜索 UE5 源码中 FBlendSample 的定义（Engine/Classes/Animation/BlendSpace.h 或类似位置）
2. 确认字段：SampleValue(FVector), Time(float), Rate(int32), bIsValid(bool) 等
3. 在 src/uasset_read/parsers/property_types.py 的 _TAGGED_FALLBACK_STRUCTS 和 _TAGGED_FALLBACK_STRUCT_SCHEMAS 中添加 BlendSample
4. 添加对应的 tagged fallback schema：[("SampleValue", "StructProperty"), ("Time", "FloatProperty"), ("Rate", "IntProperty"), ("bIsValid", "BoolProperty")]
5. 编写单元测试 tests/test_struct_blend_sample.py
6. 运行测试验证

返回纯文本 JSON：
{"status": "done/failed", "struct_name": "BlendSample", "fields_added": ["字段列表"], "tests_added": true/false, "notes": "备注"}`,
    schema: RESULT_SCHEMA,
  },
  {
    name: 'EditorElement',
    prompt: `在 UE5 源码中查找 FEditorElement 或类似结构体定义，然后在 uasset_read 项目中实现解析器。

步骤：
1. 搜索 UE5 源码中 EditorElement 的定义（可能在 Editor/ 目录下）
2. 确认字段（DisplayName, Value, bIsDefault 等）
3. 在 src/uasset_read/parsers/property_types.py 的 _TAGGED_FALLBACK_STRUCTS 和 _TAGGED_FALLBACK_STRUCT_SCHEMAS 中添加 EditorElement
4. 添加对应的 tagged fallback schema
5. 编写单元测试 tests/test_struct_editor_element.py
6. 运行测试验证

返回纯文本 JSON：
{"status": "done/failed", "struct_name": "EditorElement", "fields_added": ["字段列表"], "tests_added": true/false, "notes": "备注"}`,
    schema: RESULT_SCHEMA,
  },
  {
    name: 'ScalarParameterValues',
    prompt: `检查 uasset_read 项目中 FScalarParameterValue 结构体是否已有 tagged fallback 处理。如果没有，在 property_types.py 中添加。

步骤：
1. 检查 src/uasset_read/parsers/property_types.py 中 _TAGGED_FALLBACK_STRUCTS 是否包含 ScalarParameterValue 或 FScalarParameterValue
2. 如果没有，搜索 UE5 源码确认字段：ParameterInfo(FMaterialParameterInfo), ParameterValue(float), bOverride(bool)
3. 在 _TAGGED_FALLBACK_STRUCTS 和 _TAGGED_FALLBACK_STRUCT_SCHEMAS 中添加
4. 编写单元测试 tests/test_struct_scalar_param.py
5. 运行测试验证

返回纯文本 JSON：
{"status": "done/failed/skipped", "struct_name": "ScalarParameterValue", "already_existed": true/false, "fields_added": ["字段列表"], "tests_added": true/false, "notes": "备注"}`,
    schema: RESULT_SCHEMA,
  },
];

const p0Results = await parallel(
  p0Tasks.map(task => () =>
    agent(task.prompt, {
      label: `p0:${task.name}`,
      phase: 'P0: 结构体解析器',
      schema: task.schema,
    })
  )
);

// ============================================================
// Phase 2: P2 — EExprToken 0xFF 扩展
// ============================================================
phase('P2: EExprToken 扩展');

const p2Result = await agent(`
扩展 uasset_read 项目中 EExprToken 的 0xFF 处理，使其在 strict 模式下不再抛出异常。

步骤：
1. 读取 src/uasset_read/kismet/tokens.py，确认当前 EExprToken 枚举定义
2. 确认 0xFF 当前是否为 EX_Max = 0xFF（如果是，改为 EX_Unknown_FF = 0xFF 或保留 EX_Max 并添加单独的 0xFF 处理）
3. 读取 src/uasset_read/kismet/expressions.py，确认 EXPR_CLASS_MAP 的注册方式
4. 创建 EX_UnknownFF 表达式类（读取 1 字节 token 后的固定长度数据，具体长度需参考 UE5 蓝图 VM）
5. 在 EXPR_CLASS_MAP 中注册 EExprToken(0xFF) -> EX_UnknownFF
6. 确认 0xF9 是否也需要类似处理（当前已定义为 EX_F9）
7. 编写单元测试 tests/test_exprtoken_0xff.py
8. 运行测试验证

参考：UE5 源码 Engine/Classes/EdGraph/EdGraphNode.h 或蓝图虚拟机实现中对 0xFF 的定义。

返回纯文本 JSON：
{"status": "done/failed", "token_0xff": "处理方式", "token_0xf9": "处理方式", "expr_class_added": true/false, "tests_added": true/false, "notes": "备注"}`,
  {
    label: 'p2:token-expansion',
    phase: 'P2: EExprToken 扩展',
    schema: RESULT_SCHEMA,
  }
);

// ============================================================
// Phase 3: P1 — Texture2D Size 异常适配
// ============================================================
phase('P1: Texture2D 适配');

const p1Result = await agent(`
分析并修复 uasset_read 项目中 Texture2D 的 Size 异常问题。

背景：T_GridChecker_A 在 UE5 下 ImportedSize 之后出现 magic size 值（134217728 / 151987457），推测与 UE5 FTexturePlatformData 序列化格式变更有关。PayloadTocOffset=-1 已被记录。

步骤：
1. 读取 src/uasset_read/parsers/asset_types/texture2d.py 的完整代码
2. 读取 src/uasset_read/objects/exports/texture.py 的完整代码
3. 搜索 UE5 源码中 FTexturePlatformData::Serialize 的实现（Engine/Source/Runtime/Engine/Private/TextureResource.cpp）
4. 分析 UE5.4+ 中 TexturePlatformData 是否新增了 PayloadTocOffset 或其他字段
5. 修改 parse_texture2d 函数，在 ImportedSize 之后增加 UE5.4+ 格式检测
6. 确保异常 size 时记录诊断但不中断解析
7. 用实际资产 T_GridChecker_A 运行测试验证
8. 编写单元测试 tests/test_texture2d_size_anomaly.py

返回纯文本 JSON：
{"status": "done/failed", "ue5_format_analyzed": true/false, "new_fields_detected": ["字段列表"], "size_anomaly_resolved": true/false, "tests_added": true/false, "notes": "备注"}`,
  {
    label: 'p1:texture2d',
    phase: 'P1: Texture2D 适配',
    schema: RESULT_SCHEMA,
  }
);

// ============================================================
// Phase 4: P4 — 诊断增强
// ============================================================
phase('P4: 诊断增强');

const p4Result = await agent(`
增强 uasset_read 项目中 FString 腐败和 PackageIndex 越界的诊断信息。

步骤：
1. 读取 src/uasset_read/archive.py 中 read_fstring 方法（约行 398-480）
2. 在全空腐败检测中增加前后文位置信息（当前偏移、前后各 32 字节的 hex dump）
3. 读取 src/uasset_read/link/linker.py 中 resolve_package_index 方法（约行 169-207）
4. 在越界诊断中记录实际的 export/import 数量和请求的索引值
5. 确保新增诊断信息不影响现有测试
6. 运行现有测试验证无回归

返回纯文本 JSON：
{"status": "done/failed", "fstring_enhanced": true/false, "package_index_enhanced": true/false, "notes": "备注"}`,
  {
    label: 'p4:diagnostics',
    phase: 'P4: 诊断增强',
    schema: RESULT_SCHEMA,
  }
);

// ============================================================
// Phase 5: 验证
// ============================================================
phase('验证');

const verifyResult = await agent(`
验证所有修复是否正确：

1. 运行项目完整测试套件：python -m pytest tests/ -x --tb=short 2>&1 | tail -20
2. 检查是否有新增的测试失败
3. 用几个实际资产验证解析结果：
   - python run.py "E:\Develop\lib\Samples\FirstPerson\Content\Characters\Mannequins\Anims\Rifle\AO_Rifle.uasset" 2>&1 | head -50
   - python run.py "E:\Develop\lib\Samples\FirstPerson\Content\Characters\Mannequins\Materials\Manny\MI_Manny_01_New.uasset" 2>&1 | head -50
4. 确认测试通过率

返回纯文本 JSON：
{"status": "pass/fail", "tests_passed": 数字, "tests_failed": 数字, "total_tests": 数字, "regression": true/false, "notes": "备注"}`,
  {
    label: 'verify-all',
    phase: '验证',
  }
);

return {
  p0_results: p0Results,
  p2_result: p2Result,
  p1_result: p1Result,
  p4_result: p4Result,
  verify_result: verifyResult,
};
