# 文档状态标记规范（S3）

status: current

> 本文是规范本体，自发布起对**新建**设计文档立即生效。既有文档的批量补标在合并后另行执行，本文不改动任何现有文件。

## 1. 状态行

每份设计文档（`docs/designs/**/*.md`，含 `archive/`）在 H1 标题后的第一个非空行写且只写一行：

```markdown
status: current | target | historical | superseded
```

- 纯文本一行，无 blockquote、无粗体、无日期后缀——方便 `grep '^status:'` 机读。
- 日期与出处放正文或链接，不进状态行。

### 取值定义

| 值 | 含义 | 判定标准 |
|---|---|---|
| `current` | 描述已实现行为 | 断言可由 `src/` + `tests/` 复核（规范文档自身也可 `current`） |
| `target` | 目标设计，未（完全）实现 | 含"本轮不做"、"待 fixture"的契约/设计文档 |
| `historical` | 记录当时发生了什么，不再指导决策 | 完成报告、阶段记录；可留在原位 |
| `superseded` | 被其他文档取代 | 仓库级文档必须物理移入 `docs/designs/archive/` 并保留 banner（`docs/designs/README.md` 规则 4） |

与 `docs/designs/README.md:21` 规则 3（"新设计须在顶部附近声明 Target/Current-state/…"）的关系：本规范是其严格化落地，一行状态机读格式取代散文式声明；README 索引规则本身不动。

## 2. README Features 分区

`README.md` 的 Features 类章节（现 `## Features` README.md:33、`### Advanced Features` README.md:79）在下一轮 README 修订时拆为：

- **Available Now** —— 每条有 `src/` 实现 + 测试/fixture 证据；缺证据不得列。
- **In Development** —— 只允许指向 `status: target` 设计的链接，条目句式为"设计中/未实现"，禁止完成时态动词。

canonical design §Repository Size and Documentation Policy（"README 同时展示 current stable 与 target refactor，禁止把后者写进 Features"）继续有效，本节是其分区形式。

## 3. Agent 指令优先级

对消费本仓库文档的 agent / 人，冲突裁决顺序固定：

```
源码 (src/) > 测试 (tests/) > status: current 文档 > status: target 文档 > README/wiki/issue 摘要
```

- 任何"已实现 X"的宣称必须由前两级证据支撑；`target` 文档只回答"将要做成什么样"。
- 文档引用现状时必须带 `file:line`，且引用前在基线核实——无行号的现状断言视同 `target` 宣称。
- 不得从 issue 关闭或设计批准推断实现状态（`.claude/rules/constraints.md` §Documentation Constraints 既有规则，此处收录进裁决顺序）。

## 4. 执行边界

- 本轮交付：规范本体（本文件）。
- 合并后另行执行：既有 `docs/designs/` 文档批量补 `status:` 行；README Features 分区改写；`wiki/` 页首页加"以源码为准"指针。
- 新建设计文档的 PR 审查项：状态行存在、取值正确、现状断言带核实过的 `file:line`。
