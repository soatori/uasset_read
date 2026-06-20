// ============================================================
// Workflow 统一模板
// 复制此文件作为新 workflow 的起点
// ============================================================

export const meta = {
  name: 'workflow-name',                // 短横线命名，唯一标识
  description: '一句话描述 workflow 做什么',
  phases: [
    { title: '准备', detail: '环境检查、参数验证' },
    { title: '执行', detail: '核心逻辑' },
    { title: '验证', detail: '结果校验' },
    { title: '报告', detail: '汇总输出' },
  ],
}

// ============================================================
// 常量定义
// ============================================================

// 路径统一使用正斜杠（Windows Python/PowerShell/Node.js 均支持）
const PROJECT_ROOT = 'E:/Develop/uasset_read'
const SAMPLES_DIR = 'E:/Develop/lib/Samples'

// ============================================================
// 共享工具函数
// ============================================================

/**
 * 解析 agent 返回的文本，提取 JSON
 * agent 返回格式不稳定（~20% 需要 fallback），统一处理
 *
 * 优先级：直接解析 > 代码块提取 > 花括号提取
 */
function parseAgentJson(text) {
  if (!text || typeof text !== 'string') return null

  // 1. 直接 JSON.parse
  try {
    return JSON.parse(text)
  } catch (_) {}

  // 2. 从 ```json ... ``` 代码块提取
  const codeBlockMatch = text.match(/```(?:json)?\s*([\s\S]*?)```/)
  if (codeBlockMatch) {
    try {
      return JSON.parse(codeBlockMatch[1].trim())
    } catch (_) {}
  }

  // 3. 从第一个 { 或 [ 到最后一个匹配的 } 或 ] 提取
  const firstBrace = text.indexOf('{')
  const firstBracket = text.indexOf('[')
  let start = -1
  let endChar = ''
  if (firstBrace !== -1 && (firstBracket === -1 || firstBrace < firstBracket)) {
    start = firstBrace
    endChar = '}'
  } else if (firstBracket !== -1) {
    start = firstBracket
    endChar = ']'
  }
  if (start !== -1) {
    const end = text.lastIndexOf(endChar)
    if (end > start) {
      try {
        return JSON.parse(text.substring(start, end + 1))
      } catch (_) {}
    }
  }

  return null
}

/**
 * 安全地从 agent 结果中提取 JSON
 * 处理 null / string / object 三种情况
 */
function extractJson(raw) {
  if (!raw) return null
  if (typeof raw === 'object') return raw
  return parseAgentJson(raw)
}

// ============================================================
// Phase 1: 准备
// ============================================================
phase('准备')

// 参数从 args 获取，支持 workflow 调用时传入
const config = {
  // 示例参数，按需修改
  batchSize: args.batch_size || 5,
  maxRounds: args.max_rounds || 10,
}

log(`配置: ${JSON.stringify(config)}`)

// ============================================================
// Phase 2: 执行
// ============================================================
phase('执行')

// --- agent 调用规范 ---
// 1. 始终使用 schema 约束返回格式（不要依赖 prompt 要求"纯 JSON"）
// 2. 始终提供 label 和 phase
// 3. 并发用 parallel()，不用 Promise.all()

const EXAMPLE_SCHEMA = {
  type: 'object',
  properties: {
    status: { type: 'string', enum: ['done', 'failed', 'skipped'] },
    data: { type: 'object' },
    notes: { type: 'string' },
  },
  required: ['status'],
}

// 单个 agent 调用示例
const singleResult = await agent(
  `执行某个任务并返回结构化结果。

步骤：
1. 做某事
2. 做另一件事
3. 返回结果

注意：直接返回 JSON，不要用代码块包裹。`,
  {
    label: 'task:descriptive-name',   // 唯一标识，用于日志
    phase: '执行',                     // 对应 meta.phases 中的 title
    schema: EXAMPLE_SCHEMA,            // 强制结构化输出
  }
)

// 并发调用示例（使用 parallel，不用 Promise.all）
const items = ['a', 'b', 'c']
const batchResults = await parallel(
  items.map(item => () =>
    agent(
      `处理 ${item}，返回 JSON 结果`,
      {
        label: `process:${item}`,
        phase: '执行',
        schema: EXAMPLE_SCHEMA,
      }
    )
  )
)

// ============================================================
// Phase 3: 验证
// ============================================================
phase('验证')

// budget 检查（长循环中使用）
if (budget.total && budget.remaining() < 50_000) {
  log(`预算不足（剩余 ${Math.round(budget.remaining() / 1000)}k），提前结束`)
}

// 结果验证示例
const validResults = batchResults
  .map(r => extractJson(r))
  .filter(Boolean)

log(`有效结果: ${validResults.length}/${batchResults.length}`)

// ============================================================
// Phase 4: 报告
// ============================================================
phase('报告')

// 返回最终结果（workflow 的返回值）
return {
  config,
  results: validResults,
  summary: `处理了 ${validResults.length} 个项目`,
}
