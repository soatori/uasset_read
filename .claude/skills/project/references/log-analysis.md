# 日志分析

分析运行日志，识别错误/警告模式，分组归类后提交或合并到 GitHub Issues。

## Step 1: 定位日志

确定日志来源（按优先级）：
1. 用户指定的路径
2. `log/` 目录下最新的 `.log` 文件
3. `temp/` 下的 batch 测试输出
4. `C:\Users\cbsjz\AppData\Local\Temp\claude\` 下的 session 输出

```bash
ls -lt log/ | head -10
ls temp/*report* temp/*log* 2>/dev/null
```

## Step 2: 提取错误与警告

```bash
grep -E "\[(ERR|WARN)\]" <logfile> | head -100
grep -oP '\[ERR\] [^:]+' <logfile> | sort | uniq -c | sort -rn
grep -oP '\[WARN\] [^:]+' <logfile> | sort | uniq -c | sort -rn
```

## Step 3: 分组归类

按以下维度分组：
1. **错误类型**：UTF string 长度异常、outer_index hash 后缀、ExternalActors 路径、UE4 版本兼容、FString 腐坏等
2. **影响范围**：涉及的资产路径、Export 名称
3. **严重程度**：导致 partial/failed 的 vs 仅产生 warning 的
4. **是否已知**：检查 GitHub 已有 issue

## Step 4: 检查已有 Issue

```bash
gh issue list --state open --limit 50
gh issue list --search "<error keyword>"
```

- 已有同类 issue → 记录，不重复提交
- 新类型 → 准备提交

## Step 5: 提交新 Issue

```bash
gh issue create \
  --title "<type>: <简要描述> — <影响范围>" \
  --body "## 错误描述\n\n<详细描述>\n\n## 影响范围\n\n- 日志来源: <logfile>\n- 出现次数: N\n- 示例资产: <path>\n\n## 错误样例\n\n\`\`\`\n<原始错误行>\n\`\`\`\n\n## 建议修复方向\n\n<分析和建议>" \
  --label "bug"
```

## Step 6: 输出报告

报告输出到 `temp/log_analysis_report.md`，格式见共享报告模板。

## 约束

- 只读分析，不修改日志文件
- 新 issue 提交前必须检查重复
- 同类错误合并到已有 issue（在评论中追加数据）
