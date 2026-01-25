# Shipping Gate Lesson: FieldSelectiveEnsemble Incident

**Date**: 2026-01-20
**Project**: VortexV2
**Severity**: Process Failure
**Resolution**: Configuration changes to prevent recurrence

## What Happened

FieldSelectiveEnsemble was built and validated against 32,740 race validation pairs. The validation proved it performed better than the production AdaptiveEnsemble. However:

1. The validation was run successfully
2. The results showed clear improvement
3. **Nobody wired it to production**
4. The inferior model stayed in production
5. The validated improvement sat unused

## Root Cause Analysis

### Primary Cause
No "Definition of Done" that included "validated = deployed"

### Contributing Factors
1. Planning phase didn't ask "What happens after validation passes?"
2. No explicit classification: Research vs Improvement vs Feature
3. No gate enforcement: validation success didn't trigger deployment question
4. Work was implicitly treated as "research" (no deployment expectation)

## Pattern Recognition

When you see these signals, check for shipping-gate risk:
- `*_competition.py` or `*_validation.py` files
- Comparison scripts that output "X is better than Y"
- Validation datasets with thousands of pairs
- Code in `scripts/` that proves something but doesn't deploy

## Recommended Questions

Before starting improvement work:
1. "If this validates successfully, what production code does it replace?"
2. "What's the deployment path from validation to production?"
3. "Who/what triggers the deployment decision?"

After validation completes:
1. "Did validation pass? If yes, execute deployment step."
2. "Is this still marked as 'research'? Reclassify or ship."

## Configuration Changes Made

1. **`/plan` command** - Added Step 0: Definition of Done (required)
2. **`/validate-ship` command** - Created to audit for orphaned validated work
3. **`CLAUDE.md`** - Added rule #6 and anti-pattern
4. **`anti-patterns.md`** - Recorded "Validated but not deployed" pattern

## Future Prevention

1. Planning: Force classification (Research/Improvement/Feature)
2. Improvement work: MUST specify deployment target in plan
3. Validation completion: Trigger deployment step automatically
4. Regular audit: `/validate-ship` in `/briefing` or `/eod`

## Tags

- #anti-pattern
- #shipping
- #validation
- #vortex
- #process-improvement
