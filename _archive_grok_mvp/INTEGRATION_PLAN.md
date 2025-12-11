# Converx Integration Plan - ACTION_PLAN.md Integration

**Date**: January 2025  
**Goal**: Integrate converx with ACTION_PLAN.md to generate actionable recommendations

---

## Current State Analysis

### ✅ What's Working

1. **ACTION_PLAN.md Structure**: Well-structured with Priority A/B/C goals
2. **goal_parser.py**: Successfully parsing 7 goals from ACTION_PLAN.md
3. **recommendation_engine.py**: Generating 3 recommendations from goals
4. **All Required Tools Exist**: ai_intelligence, goal_parser, recommendation_engine, context_intelligence

### ❌ What's Missing

1. **Project Detection Gap**: 
   - ProjectScanner only finds 3 git repos (claude-usage-optimizer, keto-tracker, khoj-research)
   - ACTION_PLAN.md references many more projects (VortexV2, alpha_arena, personal-ai-dataset, etc.)
   - These projects are subdirectories in monorepo, not separate git repos

2. **Recommendation Generation Issue**:
   - Converx shows "No recommendations available"
   - Recommendation engine works but needs project activity data
   - Project activity is empty because projects aren't detected

3. **Project Name Mapping**:
   - goal_parser extracts project names from goal titles (basic pattern matching)
   - No validation that projects exist or are accessible
   - No mapping to actual directory paths

---

## Integration Plan

### Phase 1: Enhance Project Detection (HIGH PRIORITY)

**Problem**: ProjectScanner only detects top-level git repos, misses monorepo subdirectories.

**Solution**: Enhance orchestrator to detect projects from ACTION_PLAN.md goals even if they're not git repos.

**Implementation**:

1. **Add Project Directory Detection**:
   - Scan for directories matching project names from goals
   - Check if directory exists and has project structure (requirements.txt, README.md, etc.)
   - Create ProjectActivity objects for non-git projects

2. **Update orchestrator.py**:
   ```python
   def _detect_projects_from_goals(self, goals: List[Goal]) -> List[ProjectActivity]:
       """Detect projects from goal project names."""
       projects = []
       for goal in goals:
           if goal.project and goal.project not in [p.name for p in projects]:
               project_path = self.root_dir / goal.project
               if project_path.exists() and project_path.is_dir():
                   # Create minimal ProjectActivity
                   project = ProjectActivity(
                       name=goal.project,
                       path=project_path,
                       status="active" if goal.status == "in_progress" else "recent"
                   )
                   projects.append(project)
       return projects
   ```

3. **Merge Git Repos + Goal Projects**:
   - Combine detected git repos with projects from goals
   - Deduplicate by name
   - Prioritize git repos (more accurate activity data)

**Files to Modify**:
- `converx/Grok MVP/orchestrator.py` - Add project detection from goals

**Testing**:
```bash
python converx/Grok\ MVP/run_converx.py next
# Should show recommendations now
```

---

### Phase 2: Enhance Goal Parser Project Extraction (MEDIUM PRIORITY)

**Problem**: Basic pattern matching for project names may miss some projects.

**Solution**: Improve project name extraction from ACTION_PLAN.md.

**Current Extraction** (goal_parser.py lines 192-202):
- Hardcoded patterns: "VortexV2", "Alpha Arena", etc.
- May miss variations or new projects

**Enhancement**:
1. Extract project names from goal titles more intelligently
2. Check for project references in goal descriptions
3. Map common variations (e.g., "VortexV2" vs "Vortex V2")

**Files to Modify**:
- `goal_parser.py` - Enhance `_parse_goal_body` method

**Testing**:
```bash
python -c "from goal_parser import GoalParser; gp = GoalParser(); goals = gp.parse(); [print(f'{g.title} -> {g.project}') for g in goals]"
```

---

### Phase 3: Ensure Recommendations Work Without Full Project Activity (MEDIUM PRIORITY)

**Problem**: Recommendation engine may not generate recommendations if project_activity is empty.

**Solution**: Ensure recommendation engine generates recommendations from goals even without project activity.

**Current Behavior** (recommendation_engine.py):
- `_generate_next_actions()` works without project activity ✅
- `_generate_blocker_recommendations()` requires project activity ❌
- `_generate_strategy_recommendations()` requires project activity ❌

**Enhancement**:
1. Make recommendation generation more resilient
2. Always generate next_action recommendations from goals (already works)
3. Add fallback when project activity is minimal

**Files to Modify**:
- `recommendation_engine.py` - Add null checks and fallbacks

**Testing**:
```bash
python -c "from recommendation_engine import RecommendationEngine; re = RecommendationEngine(); recs = re.generate_recommendations(project_activity=None, limit=5); print(f'Generated {len(recs)} recommendations')"
```

---

### Phase 4: Add Project Validation (LOW PRIORITY)

**Problem**: No validation that projects referenced in goals actually exist.

**Solution**: Add validation and warnings for missing projects.

**Implementation**:
1. Check if project directories exist
2. Warn if project referenced in goal doesn't exist
3. Suggest creating project or updating goal

**Files to Modify**:
- `converx/Grok MVP/orchestrator.py` - Add validation method

---

## Implementation Steps

### Step 1: Quick Fix - Enable Recommendations Without Project Activity

**Time**: 15 minutes  
**Priority**: HIGH

1. Verify recommendation engine works with empty project activity
2. Test converx with current setup
3. Document findings

### Step 2: Enhance Project Detection

**Time**: 1-2 hours  
**Priority**: HIGH

1. Add `_detect_projects_from_goals()` method to orchestrator
2. Merge git repos + goal projects
3. Test with ACTION_PLAN.md projects
4. Verify recommendations appear

### Step 3: Improve Goal Parser Project Extraction

**Time**: 30 minutes  
**Priority**: MEDIUM

1. Enhance project name extraction patterns
2. Test with all goals in ACTION_PLAN.md
3. Verify all projects are detected

### Step 4: Testing & Validation

**Time**: 30 minutes  
**Priority**: HIGH

1. Test all converx commands:
   - `converx next`
   - `converx next --json`
   - `converx next vortexv2`
   - `converx status`
   - `converx next --with-context`

2. Verify recommendations match ACTION_PLAN.md priorities

3. Check that project filtering works

---

## Success Criteria

### Must Have (MVP)

- [ ] `converx next` shows recommendations from ACTION_PLAN.md goals
- [ ] Recommendations match Priority A/B/C structure
- [ ] Project filtering works (`converx next vortexv2`)
- [ ] Status command shows accurate goal counts

### Nice to Have (Enhancements)

- [ ] All ACTION_PLAN.md projects are detected
- [ ] Project activity data enriches recommendations
- [ ] Context predictions work with goals
- [ ] Recommendations include effort estimates from goals

---

## Testing Commands

```bash
# Test goal parsing
python -c "from goal_parser import GoalParser; gp = GoalParser(); goals = gp.parse(); print(f'Found {len(goals)} goals')"

# Test recommendation generation
python -c "from recommendation_engine import RecommendationEngine; re = RecommendationEngine(); recs = re.generate_recommendations(limit=5); [print(f'{r.priority}: {r.title}') for r in recs]"

# Test converx integration
python converx/Grok\ MVP/run_converx.py next
python converx/Grok\ MVP/run_converx.py next --json
python converx/Grok\ MVP/run_converx.py status
python converx/Grok\ MVP/run_converx.py next vortexv2
```

---

## Data Requirements

### From ACTION_PLAN.md

**Required Fields** (already present):
- ✅ Priority levels (A, B, C)
- ✅ Goal status (pending, in_progress, completed)
- ✅ Goal titles
- ✅ Project references (in titles/descriptions)

**Optional Fields** (would enhance recommendations):
- ⭐ Commercial value (⭐⭐⭐⭐⭐)
- ⏱️ Estimated effort (4-6 hours, 2-3 weeks)
- 📋 Actions lists
- ✅ Success criteria

### From Project Detection

**Current**: Only git repos detected  
**Needed**: All projects from ACTION_PLAN.md goals

**Projects in ACTION_PLAN.md**:
- VortexV2 (Priority A)
- alpha_arena (Priority B)
- personal-ai-dataset (Priority B)
- keto-tracker (Priority B)
- financial-aggregator (Priority C)
- ai-project-curator (Priority C)

---

## Next Steps

1. **Immediate**: Implement Phase 1 (Project Detection Enhancement)
2. **Short-term**: Test and validate integration
3. **Medium-term**: Enhance goal parser and add validation
4. **Long-term**: Add project activity enrichment for better recommendations

---

## Questions for User

1. **Project Structure**: Are all ACTION_PLAN.md projects in `/Users/jesse.kemp/Dev` as subdirectories?
2. **Git Repos**: Should we initialize git repos for projects that don't have them, or just detect directories?
3. **Priority**: Which phase should we implement first? (Recommendation: Phase 1)

---

**Status**: Ready for implementation  
**Estimated Time**: 2-3 hours total  
**Risk**: Low (all tools exist, just need integration)

