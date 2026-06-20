export const meta = {
  name: 'random-sample-test-loop',
  description: '持续多轮随机抽取测试文件，覆盖多种资产类型，排除版本问题，生成汇总报告',
  phases: [
    { title: '执行解析' },
    { title: '分析结果' },
    { title: '生成报告' },
  ],
};

const SAMPLE_ROOT = 'E:/Develop/lib/Samples';
const BATCH_SIZE = 5;
const MAX_ROUNDS = 10;

// 资产列表（按类型分布，覆盖 UE 命名规范前缀）
const ALL_ASSETS = [
  // === Blueprint (BP_) ===
  { label: 'BP_FirstPersonCharacter', category: 'Blueprint', path: 'FirstPerson/Content/FirstPerson/Blueprints/BP_FirstPersonCharacter.uasset' },
  { label: 'BP_FirstPersonGameMode', category: 'Blueprint', path: 'FirstPerson/Content/FirstPerson/Blueprints/BP_FirstPersonGameMode.uasset' },
  { label: 'BP_ThirdPersonCharacter', category: 'Blueprint', path: 'ThirtPerson/Content/ThirdPerson/Blueprints/BP_ThirdPersonCharacter.uasset' },
  { label: 'BP_CombatCharacter', category: 'Blueprint', path: 'ThirtPerson/Content/Variant_Combat/Blueprints/BP_CombatCharacter.uasset' },
  { label: 'BP_HorrorCharacter', category: 'Blueprint', path: 'FirstPerson/Content/Variant_Horror/Blueprints/BP_HorrorCharacter.uasset' },
  { label: 'BP_ShooterAIController', category: 'Blueprint', path: 'FirstPerson/Content/Variant_Shooter/Blueprints/AI/BP_ShooterAIController.uasset' },
  { label: 'BP_ShooterNPC', category: 'Blueprint', path: 'FirstPerson/Content/Variant_Shooter/Blueprints/AI/BP_ShooterNPC.uasset' },
  { label: 'BP_ShooterNPCSpawner', category: 'Blueprint', path: 'FirstPerson/Content/Variant_Shooter/Blueprints/AI/BP_ShooterNPCSpawner.uasset' },
  { label: 'BP_HorrorLight', category: 'Blueprint', path: 'FirstPerson/Content/Variant_Horror/Blueprints/Light/BP_HorrorLight.uasset' },

  // === BlueprintInterface (BPI_) ===
  { label: 'BPI_Shooter', category: 'BlueprintInterface', path: 'FirstPerson/Content/Variant_Shooter/Blueprints/BPI_Shooter.uasset' },

  // === AnimBlueprint (ABP_) ===
  { label: 'ABP_Manny_Combat', category: 'AnimBlueprint', path: 'ThirtPerson/Content/Variant_Combat/Anims/ABP_Manny_Combat.uasset' },
  { label: 'ABP_Unarmed', category: 'AnimBlueprint', path: 'FirstPerson/Content/Characters/Mannequins/Anims/Unarmed/ABP_Unarmed.uasset' },

  // === AnimSequence (MM_/MF_) ===
  { label: 'MM_Pistol_Fire', category: 'AnimSequence', path: 'FirstPerson/Content/Characters/Mannequins/Anims/Pistol/MM_Pistol_Fire.uasset' },
  { label: 'MM_Pistol_Reload', category: 'AnimSequence', path: 'FirstPerson/Content/Characters/Mannequins/Anims/Pistol/MM_Pistol_Reload.uasset' },
  { label: 'MM_Pistol_Equip', category: 'AnimSequence', path: 'FirstPerson/Content/Characters/Mannequins/Anims/Pistol/MM_Pistol_Equip.uasset' },
  { label: 'MM_Pistol_DryFire', category: 'AnimSequence', path: 'FirstPerson/Content/Characters/Mannequins/Anims/Pistol/MM_Pistol_DryFire.uasset' },
  { label: 'MM_Rifle_Fire', category: 'AnimSequence', path: 'FirstPerson/Content/Characters/Mannequins/Anims/Rifle/MM_Rifle_Fire.uasset' },
  { label: 'MM_Rifle_Reload', category: 'AnimSequence', path: 'FirstPerson/Content/Characters/Mannequins/Anims/Rifle/MM_Rifle_Reload.uasset' },
  { label: 'MF_Pistol_Idle_ADS', category: 'AnimSequence', path: 'FirstPerson/Content/Characters/Mannequins/Anims/Pistol/MF_Pistol_Idle_ADS.uasset' },
  { label: 'MF_Rifle_Idle_ADS', category: 'AnimSequence', path: 'FirstPerson/Content/Characters/Mannequins/Anims/Rifle/MF_Rifle_Idle_ADS.uasset' },
  { label: 'MM_Pistol_Jump_Start', category: 'AnimSequence', path: 'FirstPerson/Content/Characters/Mannequins/Anims/Pistol/Jump/MM_Pistol_Jump_Start.uasset' },
  { label: 'MM_Rifle_Jump_Start', category: 'AnimSequence', path: 'FirstPerson/Content/Characters/Mannequins/Anims/Rifle/Jump/MM_Rifle_Jump_Start.uasset' },

  // === SkeletalMesh (SKM_) ===
  { label: 'SKM_GrenadeLauncher', category: 'SkeletalMesh', path: 'FirstPerson/Content/Weapons/GrenadeLauncher/Meshes/SKM_GrenadeLauncher.uasset' },
  { label: 'SKM_Manny_Simple', category: 'SkeletalMesh', path: 'FirstPerson/Content/Characters/Mannequins/Meshes/SKM_Manny_Simple.uasset' },

  // === StaticMesh (SM_) ===
  { label: 'SM_Cube', category: 'StaticMesh', path: 'FirstPerson/Content/LevelPrototyping/Meshes/SM_Cube.uasset' },
  { label: 'SM_Chair', category: 'StaticMesh', path: 'StarterContent/Content/StarterContent/Props/SM_Chair.uasset' },

  // === Material (M_) ===
  { label: 'M_Mannequin', category: 'Material', path: 'FirstPerson/Content/Characters/Mannequins/Materials/M_Mannequin.uasset' },
  { label: 'M_Brick_Clay_New', category: 'Material', path: 'StarterContent/Content/StarterContent/Materials/M_Brick_Clay_New.uasset' },
  { label: 'M_Light', category: 'Material', path: 'FirstPerson/Content/Variant_Horror/Blueprints/Light/Assets/Materials/M_Light.uasset' },
  { label: 'M_DustMote', category: 'Material', path: 'FirstPerson/Content/Variant_Horror/Blueprints/Light/Assets/Materials/M_DustMote.uasset' },

  // === MaterialInstance (MI_) ===
  { label: 'MI_Manny_01_New', category: 'MaterialInstance', path: 'FirstPerson/Content/Characters/Mannequins/Materials/Manny/MI_Manny_01_New.uasset' },
  { label: 'MI_FlickeringLight', category: 'MaterialInstance', path: 'FirstPerson/Content/Variant_Horror/Blueprints/Light/Assets/Materials/MI_FlickeringLight.uasset' },

  // === Texture2D (T_) ===
  { label: 'T_GridChecker_A', category: 'Texture2D', path: 'FirstPerson/Content/LevelPrototyping/Textures/T_GridChecker_A.uasset' },
  { label: 'T_Brick_Clay_New_D', category: 'Texture2D', path: 'StarterContent/Content/StarterContent/Textures/T_Brick_Clay_New_D.uasset' },

  // === InputAction (IA_) ===
  { label: 'IA_Jump', category: 'InputAction', path: 'ThirtPerson/Content/Input/Actions/IA_Jump.uasset' },

  // === InputMappingContext (IMC_) ===
  { label: 'IMC_Default', category: 'InputMappingContext', path: 'ThirtPerson/Content/Input/IMC_Default.uasset' },

  // === Niagara (NS_) ===
  { label: 'NS_Jump_Trail', category: 'Niagara', path: 'ThirtPerson/Content/Variant_Platforming/VFX/NS_Jump_Trail.uasset' },
  { label: 'NS_DustMote', category: 'Niagara', path: 'FirstPerson/Content/Variant_Horror/Blueprints/Light/Assets/NS_DustMote.uasset' },

  // === ParticleSystem (P_) ===
  { label: 'P_Fire', category: 'ParticleSystem', path: 'StarterContent/Content/StarterContent/Particles/P_Fire.uasset' },

  // === StateTree/AI ===
  { label: 'ST_Shooter', category: 'StateTree', path: 'FirstPerson/Content/Variant_Shooter/Blueprints/AI/ST_Shooter.uasset' },
  { label: 'StateTreeTask_FaceActor', category: 'StateTreeTask', path: 'FirstPerson/Content/Variant_Shooter/Blueprints/AI/StateTree/StateTreeTask_FaceActor.uasset' },
  { label: 'EnvQueryContext_Target', category: 'EnvQueryContext', path: 'FirstPerson/Content/Variant_Shooter/Blueprints/AI/EQS/EnvQueryContext_Target.uasset' },

  // === AnimationMontage (AM_) ===
  { label: 'MM_Pistol_Fire_Montage', category: 'AnimMontage', path: 'FirstPerson/Content/Characters/Mannequins/Anims/Pistol/MM_Pistol_Fire_Montage.uasset' },
  { label: 'MM_ChargedAttack', category: 'AnimMontage', path: 'FirstPerson/Content/Characters/Mannequins/Anims/Unarmed/Attack/MM_ChargedAttack.uasset' },

  // === AimOffset (AO_) ===
  { label: 'AO_Pistol', category: 'AimOffset', path: 'FirstPerson/Content/Characters/Mannequins/Anims/Pistol/Aim/AO_Pistol.uasset' },
  { label: 'AO_Rifle', category: 'AimOffset', path: 'FirstPerson/Content/Characters/Mannequins/Anims/Rifle/AIM/AO_Rifle.uasset' },

  // === BlendSpace (BS_) ===
  { label: 'BS_Idle_Walk_Run', category: 'BlendSpace', path: 'FirstPerson/Content/Characters/Mannequins/Anims/Unarmed/BS_Idle_Walk_Run.uasset' },
];

// Fisher-Yates 洗牌 + LCG 确定性随机（与 comprehensive-random-test-loop.js 一致）
function seededShuffle(arr, seed) {
  const shuffled = [...arr];
  let s = seed;
  for (let i = shuffled.length - 1; i > 0; i--) {
    s = (s * 1103515245 + 12345) & 0x7fffffff;
    const j = s % (i + 1);
    [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
  }
  return shuffled;
}

// 解析 agent 返回的文本，提取 JSON（与模板 _template.js 一致）
function parseAgentJson(text) {
  if (!text || typeof text !== 'string') return null;
  try { return JSON.parse(text); } catch (_) {}
  const codeBlockMatch = text.match(/```(?:json)?\s*([\s\S]*?)```/);
  if (codeBlockMatch) {
    try { return JSON.parse(codeBlockMatch[1].trim()); } catch (_) {}
  }
  const firstBrace = text.indexOf('{');
  const firstBracket = text.indexOf('[');
  let start = -1, endChar = '';
  if (firstBrace !== -1 && (firstBracket === -1 || firstBrace < firstBracket)) {
    start = firstBrace; endChar = '}';
  } else if (firstBracket !== -1) {
    start = firstBracket; endChar = ']';
  }
  if (start !== -1) {
    const end = text.lastIndexOf(endChar);
    if (end > start) {
      try { return JSON.parse(text.substring(start, end + 1)); } catch (_) {}
    }
  }
  return null;
}

phase('执行解析');

const results = [];
const testedPaths = new Set();

for (let round = 0; round < MAX_ROUNDS; round++) {
  if (budget.total && budget.remaining() < 50_000) {
    log(`预算不足（剩余 ${Math.round(budget.remaining()/1000)}k），停止测试（已完成 ${round} 轮，${results.length} 个资产）`);
    break;
  }

  const shuffled = seededShuffle(ALL_ASSETS, round * 777);
  const untested = shuffled.filter(a => !testedPaths.has(a.path.toLowerCase()));

  if (untested.length === 0) {
    log(`所有 ${ALL_ASSETS.length} 个资产已测试完毕，共 ${results.length} 个结果`);
    break;
  }

  const batch = untested.slice(0, BATCH_SIZE);
  log(`第 ${round + 1}/${MAX_ROUNDS} 轮：[${batch.map(a => `${a.category}:${a.label}`).join(', ')}]`);

  const batchResults = await parallel(
    batch.map(asset => () =>
      agent(`
解析测试UE资产文件，返回纯文本JSON（不要用 \\\`\\\`\\\`json 包裹，不要用 <function=StructuredOutput>，直接输出 JSON 对象）：
- 样本根目录: ${SAMPLE_ROOT}
- 相对路径: ${asset.path}
- 资产类型: ${asset.category}
- 标签: ${asset.label}

步骤：
1. 构建完整路径
2. 检查文件是否存在
3. 运行：uasset-read "<完整路径>"
4. 运行：uasset-read "<完整路径>" --tolerant
5. 直接返回以下格式的 JSON（纯文本，不要任何包裹）：
{"label": "${asset.label}", "category": "${asset.category}", "path": "${asset.path}", "exists": true/false, "strict_success": true/false, "tolerant_success": true/false, "strict_error": "错误信息或null", "tolerant_error": "错误信息或null", "is_version_issue": true/false, "warnings": ["警告信息"], "ue_version": "UE版本号或null", "notes": "备注"}

版本问题判断标准：
- legacy_file_version 不在 {-9, -8} 范围内（如 UE4 的 -3）
- UE5 早期版本(如1004)的序列化格式差异
- 其他解析错误标记为非版本问题

重要：直接返回 JSON 对象文本，不要用代码块包裹，不要用任何 XML 标签。
`, {
        label: `test:${asset.label}`,
        phase: '执行解析',
      })
    )
  );

  const valid = [];
  for (let i = 0; i < batchResults.length; i++) {
    const raw = batchResults[i];
    const asset = batch[i];
    if (!raw) {
      valid.push({
        label: asset.label, category: asset.category, path: asset.path,
        exists: false, strict_success: false, tolerant_success: false,
        strict_error: 'Agent 返回空结果', tolerant_error: null,
        is_version_issue: false, warnings: [], ue_version: null, notes: 'Agent 未返回结果',
      });
      testedPaths.add(asset.path.toLowerCase());
      continue;
    }
    const parsed = typeof raw === 'string' ? parseAgentJson(raw) : raw;
    if (parsed && parsed.label) {
      valid.push(parsed);
      testedPaths.add(parsed.path.toLowerCase());
    } else {
      valid.push({
        label: asset.label, category: asset.category, path: asset.path,
        exists: false, strict_success: false, tolerant_success: false,
        strict_error: 'Agent 返回格式错误', tolerant_error: null,
        is_version_issue: false, warnings: [], ue_version: null, notes: 'JSON 解析失败',
      });
      testedPaths.add(asset.path.toLowerCase());
    }
  }
  results.push(...valid);
}

phase('分析结果');

const summaryRaw = await agent(`
分析以下测试结果 JSON 数组，返回纯文本 JSON（不要用代码块包裹，直接输出 JSON 对象）：

${JSON.stringify(results, null, 2)}

返回格式：
{"total_tested": 数字, "found_count": 数字, "strict_success_count": 数字, "tolerant_success_count": 数字, "strict_success_rate": "百分比字符串", "tolerant_success_rate": "百分比字符串", "version_issue_count": 数字, "non_version_failures": [{"label": "名称", "category": "类型", "path": "路径", "error": "错误信息"}], "by_category": {"类型": {"total": 数字, "strict_pass": 数字, "tolerant_pass": 数字}}, "common_warnings": [{"type": "类型", "count": 数字, "description": "描述"}]}

重要：直接返回 JSON 对象文本，不要用代码块包裹，不要用任何 XML 标签。
`, {
    label: 'analyze-results',
    phase: '分析结果',
  });

const summary = typeof summaryRaw === 'string' ? parseAgentJson(summaryRaw) : summaryRaw;

phase('生成报告');

const report = await agent(`
生成完整的Markdown测试报告（纯文本，不要用代码块包裹）：

摘要: ${JSON.stringify(summary, null, 2)}
详情: ${JSON.stringify(results, null, 2)}

要求：
1. 标题：UE资产解析器多轮随机测试报告
2. 测试时间、轮次、覆盖类型数
3. 总体统计表格
4. 按资产类型分类表格
5. 常见警告分析
6. 版本问题说明（哪些版本不支持）
7. 非版本失败详细分析
8. 详细结果表格（名称、类型、UE版本、严格、tolerant、备注）
9. 结论和建议（基于codegraph发现的项目结构）
`, {
    label: 'generate-report',
    phase: '生成报告',
  });

return { report, summary, results };
