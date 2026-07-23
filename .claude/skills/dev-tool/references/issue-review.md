# Issue Status Review

Review GitHub Issues status, check if fixed, update or close.

## Parameters

User may specify issue number (e.g. `#435`); default reviews all open issues.

## Step 1: Fetch Issue List

```bash
gh issue view <number> --json number,title,state,labels,createdAt,body
# Or all open issues
gh issue list --state open --json number,title,state,labels,createdAt --limit 50
```

## Step 2: Check Fix Status

For each issue:
1. Read description, understand the problem
2. Check code changes: `git log --oneline --all --grep="#<number>"`
3. Run related tests (if applicable)
4. Verify fix

## Step 3: Classify

| Status | Action |
|--------|--------|
| Fixed | Add `fixed` label, close issue, comment with fix commit |
| Partially fixed | Comment current status, keep open |
| Not fixed | Keep open, comment current status |
| Cannot reproduce | Comment explanation, suggest closing |
| Duplicate | Mark as duplicate, point to original issue |

## Step 4: Execute Actions

```bash
gh issue close <number> --comment "Fixed: <commit_hash> <description>"
gh issue edit <number> --add-label "fixed"
gh issue comment <number> --body "## Review Status (YYYY-MM-DD)\n\n- **Code review**: <findings>\n- **Test results**: <pass/fail>\n- **Conclusion**: <fixed/partially fixed/not fixed>"
```

## Step 5: Output Summary

Report output to `temp/issue_status_report.md`.

## Constraints

- Read-only checks + standard gh operations; do not modify code
- Must confirm fix (commit exists or tests pass) before closing
