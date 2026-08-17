export const meta = {
  name: 'parallel-semantic-extensions',
  description: 'Process issues #555 and #556 in parallel with research, planning, execution, review, and merge',
  phases: [
    { title: 'Research', detail: 'Research existing design docs and current project state' },
    { title: 'Plan', detail: 'Write implementation plans for both issues' },
    { title: 'Execute', detail: 'Execute implementation plans in parallel using worktrees' },
    { title: 'Review', detail: 'Review implementations in main agent' },
    { title: 'Merge', detail: 'Merge completed branches to dev' },
  ],
}

const ISSUES = [
  { id: 555, title: 'Animation Blueprint semantic JSON', branch: 'feature/555-anim-blueprint-semantic-json' },
  { id: 556, title: 'Material semantic JSON', branch: 'feature/556-material-semantic-json' },
]

// Phase 1: Research
phase('Research')
const researchResults = await parallel(ISSUES.map(function(issue) {
  return function() {
    return agent('Research issue #' + issue.id + ' (' + issue.title + '):\n' +
      '1. Read existing design docs in docs/designs/ related to this issue\n' +
      '2. Check current project state - what infrastructure exists from #551 and #554\n' +
      '3. Identify gaps and requirements based on latest codebase\n' +
      '4. Summarize findings: what needs to be implemented, what already exists, key decisions needed\n\n' +
      'Focus on:\n' +
      '- For #555: Animation Blueprint specific concepts (pose nodes, animgraph, animation-specific semantics)\n' +
      '- For #556: Material expressions, data flow, parameters, material properties\n\n' +
      'Return a structured research summary with:\n' +
      '- Existing infrastructure\n' +
      '- Gaps to fill\n' +
      '- Key implementation decisions\n' +
      '- Dependencies on other issues',
      {label: 'research:' + issue.id, phase: 'Research', schema: {
        type: 'object',
        properties: {
          issue_id: {type: 'number'},
          existing_infrastructure: {type: 'array', items: {type: 'string'}},
          gaps: {type: 'array', items: {type: 'string'}},
          key_decisions: {type: 'array', items: {type: 'string'}},
          dependencies: {type: 'array', items: {type: 'string'}},
          recommended_approach: {type: 'string'}
        },
        required: ['issue_id', 'existing_infrastructure', 'gaps', 'key_decisions']
      }})
  }
}))
log('Research complete for ' + researchResults.filter(Boolean).length + ' issues')

// Phase 2: Plan
phase('Plan')
const plans = await parallel(ISSUES.map(function(issue, idx) {
  return function() {
    const research = researchResults[idx]
    if (!research) return null
    return agent('Create detailed implementation plan for issue #' + issue.id + ' (' + issue.title + '):\n\n' +
      'Research Summary:\n' +
      '- Existing infrastructure: ' + research.existing_infrastructure.join(', ') + '\n' +
      '- Gaps: ' + research.gaps.join(', ') + '\n' +
      '- Key decisions: ' + research.key_decisions.join(', ') + '\n' +
      '- Dependencies: ' + research.dependencies.join(', ') + '\n' +
      '- Recommended approach: ' + research.recommended_approach + '\n\n' +
      'Create a step-by-step implementation plan with:\n' +
      '1. File changes needed (which files to create/modify)\n' +
      '2. Task breakdown with dependencies\n' +
      '3. Testing strategy\n' +
      '4. Acceptance criteria mapping\n\n' +
      'Follow the pattern from existing plans like docs/designs/2026-08-15-material-semantic-json-plan.md\n\n' +
      'Return a structured plan with tasks, files, and testing approach.',
      {label: 'plan:' + issue.id, phase: 'Plan', schema: {
        type: 'object',
        properties: {
          issue_id: {type: 'number'},
          tasks: {type: 'array', items: {
            type: 'object',
            properties: {
              name: {type: 'string'},
              description: {type: 'string'},
              files: {type: 'array', items: {type: 'string'}},
              dependencies: {type: 'array', items: {type: 'string'}},
              testing: {type: 'string'}
            },
            required: ['name', 'description', 'files']
          }},
          files_to_modify: {type: 'array', items: {type: 'string'}},
          testing_strategy: {type: 'string'},
          acceptance_criteria: {type: 'array', items: {type: 'string'}}
        },
        required: ['issue_id', 'tasks', 'files_to_modify']
      }})
  }
}))
log('Plans created for ' + plans.filter(Boolean).length + ' issues')

// Phase 3: Execute
phase('Execute')
const executionResults = await parallel(ISSUES.map(function(issue, idx) {
  return function() {
    const plan = plans[idx]
    if (!plan) return null
    return agent('Execute implementation plan for issue #' + issue.id + ' (' + issue.title + ').\n\n' +
      'Plan Summary:\n' +
      '- Tasks: ' + plan.tasks.length + '\n' +
      '- Files to modify: ' + plan.files_to_modify.join(', ') + '\n\n' +
      'Steps:\n' +
      '1. Create feature branch: ' + issue.branch + '\n' +
      '2. Implement each task following the plan\n' +
      '3. Write tests for each component\n' +
      '4. Run tests to verify implementation\n' +
      '5. Commit with descriptive messages\n\n' +
      'Important:\n' +
      '- Follow existing code patterns and style\n' +
      '- Add tests for new functionality\n' +
      '- Ensure all tests pass before completing\n' +
      '- Use conventional commit messages (feat:, fix:, test:, etc.)\n\n' +
      'Execute the implementation and report completion status.',
      {label: 'execute:' + issue.id, phase: 'Execute', isolation: 'worktree'})
  }
}))
log('Execution complete for ' + executionResults.filter(Boolean).length + ' issues')

// Phase 4: Review
phase('Review')
const reviewResults = await parallel(ISSUES.map(function(issue, idx) {
  return function() {
    const execution = executionResults[idx]
    if (!execution) return null
    return agent('Review implementation for issue #' + issue.id + ' (' + issue.title + ').\n\n' +
      'Review Checklist:\n' +
      '1. Code quality and style consistency\n' +
      '2. Test coverage and test quality\n' +
      '3. Documentation completeness\n' +
      '4. Adherence to project constraints (zero runtime dependencies, read-only, etc.)\n' +
      '5. Integration with existing infrastructure\n' +
      '6. No regressions in existing tests\n\n' +
      'Check:\n' +
      '- All new code has corresponding tests\n' +
      '- Tests pass: python -m pytest tests -q\n' +
      '- No hardcoded class names (use class_serialization_strategy pattern)\n' +
      '- Proper error handling and diagnostics\n' +
      '- Follows existing IR/Renderer patterns\n\n' +
      'Provide a review report with:\n' +
      '- Overall status (approve/request changes)\n' +
      '- Specific issues found\n' +
      '- Recommendations for improvement',
      {label: 'review:' + issue.id, phase: 'Review'})
  }
}))
log('Review complete for ' + reviewResults.filter(Boolean).length + ' issues')

// Phase 5: Merge
phase('Merge')
const mergeResults = await parallel(ISSUES.map(function(issue, idx) {
  return function() {
    const review = reviewResults[idx]
    if (!review || review.status === 'request_changes') return {merged: false, reason: 'Review not approved'}
    return agent('Merge issue #' + issue.id + ' branch to dev:\n\n' +
      'Branch: ' + issue.branch + '\n' +
      'Target: dev-0.5.5\n\n' +
      'Steps:\n' +
      '1. Switch to dev-0.5.5 branch\n' +
      '2. Merge feature branch: git merge ' + issue.branch + '\n' +
      '3. Resolve any conflicts\n' +
      '4. Run full test suite: python -m pytest tests -q\n' +
      '5. Push to remote if tests pass\n\n' +
      'Report merge status and any conflicts encountered.',
      {label: 'merge:' + issue.id, phase: 'Merge'})
  }
}))
log('Merge complete for ' + mergeResults.filter(Boolean).length + ' issues')

// Summary
const summary = {
  issues_processed: ISSUES.length,
  research_complete: researchResults.filter(Boolean).length,
  plans_created: plans.filter(Boolean).length,
  executions_complete: executionResults.filter(Boolean).length,
  reviews_complete: reviewResults.filter(Boolean).length,
  merges_complete: mergeResults.filter(function(r) { return r && r.merged; }).length,
  results: ISSUES.map(function(issue, idx) {
    return {
      issue: issue.id,
      title: issue.title,
      research: !!researchResults[idx],
      plan: !!plans[idx],
      execution: !!executionResults[idx],
      review: reviewResults[idx] ? reviewResults[idx].status : 'pending',
      merge: mergeResults[idx] ? mergeResults[idx].merged : false
    }
  })
}

log('\n=== Summary ===')
log('Issues processed: ' + summary.issues_processed)
log('Research complete: ' + summary.research_complete)
log('Plans created: ' + summary.plans_created)
log('Executions complete: ' + summary.executions_complete)
log('Reviews complete: ' + summary.reviews_complete)
log('Merges complete: ' + summary.merges_complete)

return summary