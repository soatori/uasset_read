export const meta = {
  name: 'comprehensive-random-test-loop',
  description: '多轮随机抽样测试，深度验证输出完整性，识别修复问题，循环至目标通过率',
  phases: [
    { title: '发现资产', detail: '扫描各子项目 .uasset 资产分布' },
    { title: '随机抽样', detail: '按种子随机选取多类型资产' },
    { title: '深度解析', detail: '逐资产运行解析器，获取完整输出' },
    { title: '完整性审查', detail: '审查输出是否包含事件/函数/节点实现逻辑' },
    { title: '问题诊断', detail: '分析失败和缺失，归类根因' },
    { title: '修复执行', detail: '对共性问题执行合并修复' },
    { title: '验证修复', detail: '重新解析验证修复效果' },
    { title: '生成报告', detail: '汇总多轮测试结果和修复记录' },
  ],
}

const BASE = 'E:/Develop/lib/Samples'
const TEMP_DIR = 'E:/Develop/uasset_read/temp'
const PROJECTS = [
  'CiciToonCharacterShaderPa',
  'FirstPerson',
  'FirstPersonC',
  'GameAnimationSample',
  'LevelDesignPrinciples',
  'StarterContent',
  'ThirtPerson',
  'ThirtPersonC',
]

// ---- Phase 1: 发现资产 ----
phase('发现资产')

// 使用 agent 扫描各项目的资产
const scanResults = await parallel([
  ...PROJECTS.map((proj, idx) => () => agent(
    `在目录 ${BASE}/${proj}/Content 中递归查找最多200个 .uasset 文件路径。返回 JSON 数组格式的文件路径列表。使用 PowerShell: Get-ChildItem -Path 'E:\\Develop\\lib\\Samples\\${proj}\\Content' -Recurse -Filter '*.uasset' -File | Select-Object -First 200 -ExpandProperty FullName`,
    { label: `scan:${proj}`, phase: '发现资产' }
  )),
  () => agent(
    `在目录 ${BASE}/Games/LyraStarterGame/Content 中递归查找最多500个 .uasset 文件路径。返回 JSON 数组格式。使用 PowerShell 命令: Get-ChildItem -Path 'E:\\Develop\\lib\\Samples\\Games\\LyraStarterGame\\Content' -Recurse -Filter '*.uasset' -File | Select-Object -First 500 -ExpandProperty FullName`,
    { label: 'scan:Lyra', phase: '发现资产' }
  )
])

log(`[发现] 完成资产扫描，收集各项目的 .uasset 文件列表`)

// 解析扫描结果
const projectAssets = {}
for (let i = 0; i < PROJECTS.length; i++) {
  try {
    const text = scanResults[i] || ''
    const jsonMatch = text.match(/\[[\s\S]*\]/)
    if (jsonMatch) {
      projectAssets[PROJECTS[i]] = JSON.parse(jsonMatch[0])
    } else {
      projectAssets[PROJECTS[i]] = []
    }
  } catch(e) {
    projectAssets[PROJECTS[i]] = []
  }
  log(`[发现] ${PROJECTS[i]}: ${(projectAssets[PROJECTS[i]] || []).length} 个 .uasset`)
}

let lyraAssets = []
try {
  const text = scanResults[PROJECTS.length] || ''
  const jsonMatch = text.match(/\[[\s\S]*\]/)
  if (jsonMatch) lyraAssets = JSON.parse(jsonMatch[0])
} catch(e) {}
log(`[发现] LyraStarterGame: ${lyraAssets.length} 个 .uasset`)

// ---- Phase 2: 随机抽样 ----
function seededShuffle(arr, seed) {
  const shuffled = [...arr]
  let s = seed
  for (let i = shuffled.length - 1; i > 0; i--) {
    s = (s * 1103515245 + 12345) & 0x7fffffff
    const j = s % (i + 1)
    ;[shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]]
  }
  return shuffled
}

function guessAssetType(filepath) {
  const name = filepath.split(/[\\\/]/).pop().toLowerCase()
  if (name.startsWith('bp_') || name.startsWith('wbp_') || name.startsWith('wb_')) return 'Blueprint'
  if (name.startsWith('m_') || name.startsWith('mi_') || name.startsWith('mat_')) return 'Material'
  if (name.startsWith('t_') || name.includes('texture')) return 'Texture'
  if (name.startsWith('sm_')) return 'StaticMesh'
  if (name.startsWith('sk_') || name.includes('skeleton')) return 'SkeletalMesh'
  if (name.includes('animbp') || name.includes('animblueprint')) return 'AnimBlueprint'
  if (name.includes('anim') && !name.includes('widget')) return 'Animation'
  if (name.includes('widget') || name.startsWith('wbp_')) return 'WidgetBlueprint'
  if (name.startsWith('p_') || name.includes('particle') || name.includes('niagara') || name.startsWith('psys')) return 'Particle'
  if (name.includes('datatable') || name.endsWith('_table.uasset')) return 'DataTable'
  if (name.includes('_settings') || name.includes('_config') || name.includes('settings.uasset')) return 'Settings'
  if (name.startsWith('gp_') || name.includes('gameplay')) return 'Gameplay'
  if (name.startsWith('pp_') || name.includes('postprocess')) return 'PostProcess'
  if (name.startsWith('env_')) return 'Environment'
  if (name.startsWith('l_') || name.includes('level') || name.includes('.umap')) return 'Level'
  if (name.startsWith('s_') || name.includes('sound') || name.includes('cue')) return 'Sound'
  if (name.includes('input') || name.startsWith('ia_') || name.startsWith('imc_')) return 'Input'
  if (name.includes('materialinterface')) return 'MaterialInterface'
  return 'Other'
}

// ---- 执行多轮测试循环 ----
const _args = args || {}
const SEED_BASE = _args.seed || 42
const ROUNDS = _args.rounds || 5
const SAMPLES_PER_PROJECT = _args.samples_per_project || 5
const LYRA_SAMPLES = _args.lyra_samples || 10
const TARGET_PASS_RATE = _args.target_pass_rate || 98

const allRoundResults = []
const allFailures = []
const fixHistory = []
const recurringIssues = {}
const typeCoverage = {}
const roundSummaries = []

for (let round = 0; round < ROUNDS; round++) {
  const roundSeed = SEED_BASE + round * 1000

  // ---- Phase 2: 随机抽样 ----
  phase('随机抽样')
  log(`[轮次 ${round + 1}/${ROUNDS}] 开始抽样...`)

  const selected = []
  for (const proj of PROJECTS) {
    const files = projectAssets[proj] || []
    if (files.length === 0) continue
    const shuffled = seededShuffle(files, roundSeed + proj.length)
    const picks = shuffled.slice(0, Math.min(SAMPLES_PER_PROJECT, shuffled.length))
    for (const p of picks) {
      selected.push({ project: proj, path: p })
    }
  }

  const lyraShuffled = seededShuffle(lyraAssets, roundSeed + 999)
  const lyraPicks = lyraShuffled.slice(0, Math.min(LYRA_SAMPLES, lyraShuffled.length))
  for (const p of lyraPicks) {
    selected.push({ project: 'LyraStarterGame', path: p })
  }

  const samplesWithType = selected.map(s => ({
    project: s.project,
    path: s.path,
    type: guessAssetType(s.path),
    filename: s.path.split(/[\\\/]/).pop(),
  }))

  const typeCounts = {}
  for (const s of samplesWithType) {
    typeCounts[s.type] = (typeCounts[s.type] || 0) + 1
    typeCoverage[s.type] = (typeCoverage[s.type] || 0) + 1
  }
  log(`[轮次 ${round + 1}] 抽样: ${samplesWithType.length} 个资产，类型: ${JSON.stringify(typeCounts)}`)

  // ---- Phase 3: 深度解析 ----
  phase('深度解析')
  log(`[轮次 ${round + 1}] 开始深度解析...`)

  // 为每个样本创建解析 agent
  const parseAgents = samplesWithType.map((sample, idx) => () => {
    const escapedPath = sample.path.replace(/\//g, '\\\\')
    const isBlueprint = ['Blueprint', 'WidgetBlueprint', 'AnimBlueprint'].includes(sample.type)
    const commands = [
      `cd /d E:\\\\Develop\\\\uasset_read && python -m uasset_read "${escapedPath}" --summary 2>&1`,
      ...(isBlueprint ? [`cd /d E:\\\\Develop\\\\uasset_read && python -m uasset_read "${escapedPath}" --blueprint-text 2>&1`] : [])
    ]
    return agent(
      `依次执行以下命令并返回完整输出（包含 stdout 和 stderr）：\n${commands.join('\n')}\n\n返回格式: {"summary": "<summary命令的完整输出>", "blueprint": "<blueprint命令的输出或null>"}\n使用 PowerShell 执行，注意转义。`,
      { label: `parse:${sample.filename}`, phase: '深度解析' }
    ).then(output => ({
      sample,
      output: output || '{"summary": "", "blueprint": null}',
    }))
  })

  // 批量执行解析
  const parseResults = []
  const batchSize = 3
  for (let b = 0; b < parseAgents.length; b += batchSize) {
    const batch = parseAgents.slice(b, b + batchSize)
    const results = await parallel(batch.map((fn, fi) => () => fn().catch(e => ({ sample: samplesWithType[b + fi], error: e.message, output: '' }))))
    parseResults.push(...results.filter(Boolean))
    log(`[轮次 ${round + 1}] 解析进度: ${Math.min(b + batchSize, parseAgents.length)}/${parseAgents.length}`)
  }

  // ---- Phase 4: 完整性审查 ----
  phase('完整性审查')
  log(`[轮次 ${round + 1}] 开始完整性审查...`)

  const reviewAgents = parseResults.map((pr, idx) => () => {
    if (!pr || !pr.output) {
      return Promise.resolve({ sample: pr?.sample, result: { pass: false, issues: ['解析 agent 无输出'], severity: 'error', passRate: 0 } })
    }
    const sample = pr.sample
    const isBlueprint = ['Blueprint', 'WidgetBlueprint', 'AnimBlueprint'].includes(sample.type)
    return agent(
      `分析以下 uasset 解析器的输出，进行完整性审查。

资产信息：
- 项目: ${sample.project}
- 文件: ${sample.filename}
- 类型: ${sample.type}
- 路径: ${sample.path}

解析器输出：
${pr.output}

审查要求：
1. 检查 JSON 是否有效
2. 检查 summary、linker、name_map、export_map 是否存在且非空
3. ${isBlueprint ? `蓝图额外检查：
   - blueprint.variables 是否 >= 1
   - 变量是否有 GUID
   - graphs 是否 >= 1
   - 节点是否有 Pin 和连接关系
   - 是否包含事件节点（Event/Receive/BeginPlay）
   - 是否包含函数调用节点
   - 节点是否有自定义属性/元数据/注释等逻辑信息` : '非蓝图资产：仅检查基础结构完整性'}

返回 JSON 格式：
{
  "valid_json": true/false,
  "has_summary": true/false,
  "has_linker": true/false,
  "has_name_map": true/false,
  "has_export_map": true/false,
  ${isBlueprint ? `"has_blueprint_vars": true/false,
  "has_variable_guids": true/false,
  "has_graphs": true/false,
  "has_pins": true/false,
  "has_pin_connections": true/false,
  "has_events": true/false,
  "has_functions": true/false,
  "has_node_logic": true/false,` : ''}
  "errors": ["错误列表"],
  "warnings": ["警告列表"],
  "pass": true/false,
  "passRate": 0-100,
  "outputLength": 数字
}`,
      { label: `review:${sample.filename}`, phase: '完整性审查', schema: { type: 'object', properties: { valid_json: { type: 'boolean' }, has_summary: { type: 'boolean' }, has_linker: { type: 'boolean' }, has_name_map: { type: 'boolean' }, has_export_map: { type: 'boolean' }, has_blueprint_vars: { type: 'boolean' }, has_variable_guids: { type: 'boolean' }, has_graphs: { type: 'boolean' }, has_pins: { type: 'boolean' }, has_pin_connections: { type: 'boolean' }, has_events: { type: 'boolean' }, has_functions: { type: 'boolean' }, has_node_logic: { type: 'boolean' }, errors: { type: 'array', items: { type: 'string' } }, warnings: { type: 'array', items: { type: 'string' } }, pass: { type: 'boolean' }, passRate: { type: 'number' }, outputLength: { type: 'number' } }, required: ['valid_json', 'has_summary', 'pass', 'passRate'] } }
    ).then(review => ({
      sample,
      review,
    }))
  })

  // 批量执行审查
  const reviewResults = []
  for (let b = 0; b < reviewAgents.length; b += batchSize) {
    const batch = reviewAgents.slice(b, b + batchSize)
    const results = await parallel(batch.map((fn, fi) => () => fn().catch(e => ({ sample: samplesWithType[b + fi], review: { pass: false, errors: [e.message], passRate: 0 } }))))
    reviewResults.push(...results.filter(Boolean))
    log(`[轮次 ${round + 1}] 审查进度: ${Math.min(b + batchSize, reviewAgents.length)}/${reviewAgents.length}`)
  }

  // 汇总本轮结果
  const roundPass = reviewResults.filter(r => r.review && r.review.pass).length
  const roundFail = reviewResults.filter(r => !r.review || !r.review.pass).length
  const roundPassRate = ((roundPass / reviewResults.length) * 100).toFixed(1)

  log(`[轮次 ${round + 1}] 结果: 通过 ${roundPass}/${reviewResults.length} (${roundPassRate}%)，失败 ${roundFail} 个`)

  roundSummaries.push({
    round: round + 1,
    total: reviewResults.length,
    pass: roundPass,
    fail: roundFail,
    passRate: roundPassRate,
    typeCounts,
  })

  // 记录失败
  for (const r of reviewResults) {
    if (!r.review || !r.review.pass) {
      const entry = {
        round: round + 1,
        project: r.sample.project,
        filename: r.sample.filename,
        type: r.sample.type,
        path: r.sample.path,
        errors: r.review?.errors || ['unknown'],
        warnings: r.review?.warnings || [],
        passRate: r.review?.passRate || 0,
      }
      allRoundResults.push(entry)
      allFailures.push(entry)

      // 归类重复问题
      for (const err of entry.errors) {
        const key = err.toLowerCase().slice(0, 50)
        if (!recurringIssues[key]) {
          recurringIssues[key] = { count: 0, message: err, types: {}, files: [] }
        }
        recurringIssues[key].count++
        recurringIssues[key].types[r.sample.type] = (recurringIssues[key].types[r.sample.type] || 0) + 1
        if (recurringIssues[key].files.length < 5) {
          recurringIssues[key].files.push(r.sample.filename)
        }
      }
    } else {
      allRoundResults.push({
        round: round + 1,
        project: r.sample.project,
        filename: r.sample.filename,
        type: r.sample.type,
        path: r.sample.path,
        errors: [],
        warnings: r.review?.warnings || [],
        passRate: r.review?.passRate || 100,
      })
    }
  }

  // ---- Phase 5: 问题诊断 ----
  phase('问题诊断')
  if (roundFail > 0) {
    const topIssues = Object.entries(recurringIssues)
      .filter(([, v]) => v.count >= 2)
      .sort((a, b) => b[1].count - a[1].count)
      .slice(0, 5)
      .map(([k, v]) => ({ key: k, count: v.count, message: v.message, types: v.types }))

    if (topIssues.length > 0) {
      log(`[轮次 ${round + 1}] 共性问题 (出现≥2次): ${JSON.stringify(topIssues)}`)
    } else {
      log(`[轮次 ${round + 1}] 无共性问题（均为孤立失败）`)
    }
  }

  // ---- Phase 6: 修复执行 ----
  phase('修复执行')

  // 如果有共性问题且不是最后一轮，尝试修复
  const sharedIssues = Object.entries(recurringIssues)
    .filter(([, v]) => v.count >= 2)
    .sort((a, b) => b[1].count - a[1].count)

  if (sharedIssues.length > 0 && round < ROUNDS - 1) {
    log(`[轮次 ${round + 1}] 发现 ${sharedIssues.length} 个共性问题，执行修复...`)

    // 生成修复指令
    for (const [key, info] of sharedIssues.slice(0, 3)) {
      const fixResult = await agent(
        `分析以下解析器问题并修复：
问题类别: ${key}
出现次数: ${info.count}
描述: ${info.message}
影响的资产类型: ${JSON.stringify(info.types)}
示例文件: ${JSON.stringify(info.files)}

项目根目录: E:\\Develop\\uasset_read
解析器源码: src/uasset_read/
请分析可能的原因，修复相关的 Python 代码。使用 Grep/Glob 找到相关代码，然后修改。
修复后返回: {"fix_applied": true/false, "files_modified": [...], "description": "修复说明"}`,
        { label: `fix:${key.slice(0, 30)}`, phase: '修复执行' }
      )

      fixHistory.push({
        round: round + 1,
        issue: key,
        result: fixResult,
      })
      log(`[轮次 ${round + 1}] 修复 ${key}: ${fixResult}`)
    }
  } else if (roundFail === 0) {
    log(`[轮次 ${round + 1}] ✅ 本轮全部通过！`)
  }

  // ---- Phase 7: 验证修复 ----
  phase('验证修复')
  if (fixHistory.length > 0) {
    const last = fixHistory[fixHistory.length - 1]
    log(`[轮次 ${round + 1}] 最近修复: 第${last.round}轮 - ${last.issue}`)
  }

  // 检查是否达到目标
  if (parseFloat(roundPassRate) >= TARGET_PASS_RATE) {
    log(`[轮次 ${round + 1}] ✅ 已达到目标通过率 ${TARGET_PASS_RATE}%！`)
    break
  }
}

// ---- Phase 8: 生成报告 ----
phase('生成报告')

const totalPass = allRoundResults.filter(r => r.passRate >= 75).length
const totalFail = allRoundResults.filter(r => r.passRate < 75).length
const overallRate = ((totalPass / allRoundResults.length) * 100).toFixed(1)

// 类型统计
const typeStats = {}
for (const r of allRoundResults) {
  if (!typeStats[r.type]) typeStats[r.type] = { total: 0, pass: 0, fail: 0 }
  typeStats[r.type].total++
  if (r.passRate >= 75) typeStats[r.type].pass++
  else typeStats[r.type].fail++
}

const report = {
  title: 'UE 资产随机抽样测试报告',
  date: _args.date || new Date(0).toISOString().slice(0, 10),  // 通过 args.date 传入，避免 argless new Date()
  config: {
    rounds: ROUNDS,
    samplesPerProject: SAMPLES_PER_PROJECT,
    lyraSamples: LYRA_SAMPLES,
    targetPassRate: TARGET_PASS_RATE + '%',
    seedBase: SEED_BASE,
  },
  overall: {
    totalTested: allRoundResults.length,
    pass: totalPass,
    fail: totalFail,
    overallPassRate: overallRate + '%',
    targetMet: parseFloat(overallRate) >= TARGET_PASS_RATE,
  },
  roundSummaries,
  typeCoverage,
  typeStats,
  topFailures: Object.entries(recurringIssues)
    .sort((a, b) => b[1].count - a[1].count)
    .slice(0, 10)
    .map(([k, v]) => ({ category: k, count: v.count, message: v.message, types: v.types, files: v.files })),
  fixHistory,
  recommendations: [],
}

// 生成建议
if (parseFloat(overallRate) < 90) {
  report.recommendations.push(`总体通过率偏低（${overallRate}%），需要优先修复高频问题`)
}
for (const [type, stats] of Object.entries(typeStats)) {
  if (stats.fail > stats.total * 0.3) {
    report.recommendations.push(`${type} 类型失败率较高（${stats.fail}/${stats.total}），建议专项检查`)
  }
}
if (Object.keys(recurringIssues).length === 0) {
  report.recommendations.push('未检测到系统性问题，资产解析整体健康')
}

return report
