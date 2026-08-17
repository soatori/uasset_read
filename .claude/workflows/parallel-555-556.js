export const meta = {
  name: 'parallel-555-556',
  description: 'Process Animation Blueprint and Material semantic JSON extensions in parallel',
  phases: [
    { title: 'Research', detail: 'Research existing design docs' },
    { title: 'Plan', detail: 'Write implementation plans' },
    { title: 'Execute', detail: 'Execute implementations in parallel' },
    { title: 'Review', detail: 'Review implementations' },
    { title: 'Merge', detail: 'Merge to dev' },
  ],
}

// Phase 1: Research both issues in parallel
phase('Research')
const research555 = await agent('Research issue #555 (Animation Blueprint semantic JSON). Read docs/designs/ for animation-related docs. Check what infrastructure exists from #551. Identify gaps for AnimBlueprint/AnimBlueprintGeneratedClass semantic JSON. Focus on pose nodes, animgraph, animation-specific semantics. Return research summary.', {
  label: 'research:555',
  phase: 'Research'
})
const research556 = await agent('Research issue #556 (Material semantic JSON). Read docs/designs/2026-08-15-material-semantic-json-design.md and plan. Check what infrastructure exists from #551. Identify gaps for Material/MaterialInstance semantic JSON. Focus on material expressions, data flow, parameters. Return research summary.', {
  label: 'research:556',
  phase: 'Research'
})
log('Research complete')

// Phase 2: Create implementation plans
phase('Plan')
const plan555 = await agent('Create implementation plan for issue #555 (Animation Blueprint). Based on research, create step-by-step plan with file changes, task breakdown, testing strategy. Follow pattern from existing plans. Return structured plan.', {
  label: 'plan:555',
  phase: 'Plan'
})
const plan556 = await agent('Create implementation plan for issue #556 (Material). Use existing design doc as base. Create step-by-step plan with file changes, task breakdown, testing strategy. Return structured plan.', {
  label: 'plan:556',
  phase: 'Plan'
})
log('Plans created')

// Phase 3: Execute implementations in parallel using worktrees
phase('Execute')
const exec555 = await agent('Execute implementation for issue #555 (Animation Blueprint). Create branch feature/555-anim-blueprint-semantic-json. Implement according to plan. Write tests. Run tests. Commit with conventional messages. Report completion status.', {
  label: 'execute:555',
  phase: 'Execute',
  isolation: 'worktree'
})
const exec556 = await agent('Execute implementation for issue #556 (Material). Create branch feature/556-material-semantic-json. Implement according to plan. Write tests. Run tests. Commit with conventional messages. Report completion status.', {
  label: 'execute:556',
  phase: 'Execute',
  isolation: 'worktree'
})
log('Executions complete')

// Phase 4: Review implementations
phase('Review')
const review555 = await agent('Review implementation for issue #555. Check code quality, test coverage, documentation, constraints adherence, integration. Provide review report with status and issues.', {
  label: 'review:555',
  phase: 'Review'
})
const review556 = await agent('Review implementation for issue #556. Check code quality, test coverage, documentation, constraints adherence, integration. Provide review report with status and issues.', {
  label: 'review:556',
  phase: 'Review'
})
log('Reviews complete')

// Phase 5: Merge to dev
phase('Merge')
const merge555 = await agent('Merge issue #555 branch to dev-0.5.5. Switch to dev-0.5.5, merge feature/555-anim-blueprint-semantic-json, resolve conflicts, run tests, push. Report merge status.', {
  label: 'merge:555',
  phase: 'Merge'
})
const merge556 = await agent('Merge issue #556 branch to dev-0.5.5. Switch to dev-0.5.5, merge feature/556-material-semantic-json, resolve conflicts, run tests, push. Report merge status.', {
  label: 'merge:556',
  phase: 'Merge'
})
log('Merges complete')

// Summary
log('\n=== Summary ===')
log('Issues processed: 2')
log('Research complete: 2')
log('Plans created: 2')
log('Executions complete: 2')
log('Reviews complete: 2')
log('Merges complete: 2')

return {
  issues: [555, 556],
  research: 2,
  plans: 2,
  executions: 2,
  reviews: 2,
  merges: 2
}