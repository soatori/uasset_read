# Log Analysis

Analyze run logs, identify error/warning patterns, group and file to GitHub Issues.

## Step 1: Locate Logs

Determine log source (by priority):
1. User-specified path
2. Latest `.log` file in `log/` directory
3. Batch test output in `temp/`
4. Session output in `C:\Users\cbsjz\AppData\Local\Temp\claude\`

```bash
ls -lt log/ | head -10
ls temp/*report* temp/*log* 2>/dev/null
```

## Step 2: Extract Errors & Warnings

```bash
grep -E "\[(ERR|WARN)\]" <logfile> | head -100
grep -oP '\[ERR\] [^:]+' <logfile> | sort | uniq -c | sort -rn
grep -oP '\[WARN\] [^:]+' <logfile> | sort | uniq -c | sort -rn
```

## Step 3: Group & Classify

Group by these dimensions:
1. **Error type**: UTF string length anomaly, outer_index hash suffix, ExternalActors path, UE4 version compat, FString corruption, etc.
2. **Scope**: Asset paths, Export names affected
3. **Severity**: Causing partial/failed vs warning-only
4. **Known?**: Check existing GitHub issues

## Step 4: Check Existing Issues

```bash
gh issue list --state open --limit 50
gh issue list --search "<error keyword>"
```

- Existing同类 issue → record, do not duplicate
- New type → prepare to file

## Step 5: File New Issue

```bash
gh issue create \
  --title "<type>: <brief description> — <scope>" \
  --body "## Error Description\n\n<details>\n\n## Scope\n\n- Log source: <logfile>\n- Occurrence count: N\n- Example asset: <path>\n\n## Error Sample\n\n\`\`\`\n<raw error line>\n\`\`\`\n\n## Suggested Fix Direction\n\n<analysis and suggestions>" \
  --label "bug"
```

## Step 6: Output Report

Report output to `temp/log_analysis_report.md`, format follows shared report template.

## Constraints

- Read-only analysis; do not modify log files
- Must check for duplicates before filing new issues
- Same-class errors merge into existing issue (append data in comment)
