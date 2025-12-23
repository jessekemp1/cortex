# Golden Spec: Session Bootstrap Hook - Automatic Intelligence Loading

**Project**: Cortex
**Date**: 2025-12-18
**Status**: Specification
**Type**: Feature Enhancement

---

## 🧠 Portfolio Intelligence Context

**Query**: "shell startup automation hooks bootstrap session context"

**Similar Work Referenced**:
- [**Golden Spec Intelligence Enhancement**](file:///Users/jesse.kemp/Dev/.claude/GOLDEN_SPEC_INTELLIGENCE_ENHANCEMENT_PROPER.md) (similarity: 0.74) - Implemented intelligence system with session context
- [**Integration Guide**](file:///Users/jesse.kemp/Dev/cortex/INTEGRATION_GUIDE.md) (similarity: 0.64) - Integration patterns for Cortex components
- [**Bridge Upgrade Spec**](file:///Users/jesse.kemp/Dev/cortex/features/bridge_upgrade/Spec.md) (similarity: 0.62) - CLI interface patterns

**Patterns Applied**:
- **Shell Hook Pattern**: Similar to how local-orchestrator uses launchd for daemon startup
- **Automatic Context Loading**: Pattern from intelligence system where session context is pre-loaded
- **Python Script Integration**: Following cortex/bridge.py CLI patterns

**Lessons Heeded**:
- Keep shell scripts simple and robust (from local-orchestrator daemon experience)
- Use Python for complex logic, shell for triggering only
- Make it optional/non-blocking - don't slow down shell startup

---

## Phase 1: Deep Research (The "Why")

### Problem Statement

**Current State**: Users must manually run `python bridge.py session-context` when resuming work to get session intelligence.

**Impact**:
- 30-60 seconds of manual context recovery every session
- Inconsistent usage - users forget to run it
- Intelligence system value not realized if not used

### 5 Whys

**Why do users need session context?**
→ To understand recent work, active goals, and current focus when resuming a project

**Why don't they get it automatically?**
→ No shell hook exists to trigger intelligence loading on session start

**Why is that a problem?**
→ Manual steps reduce adoption and create friction

**Why does adoption matter?**
→ The intelligence system only provides 10x value if consistently used

**Why is consistent usage important?**
→ Pattern recognition and mistake prevention require continuous portfolio awareness

**Root Cause**: Missing automation layer between shell startup and intelligence system.

---

## Phase 2: Design the Dream (The "What")

### Outcome Statement

**When** a developer opens a new terminal session in any Cortex-tracked project,
**They** automatically receive session intelligence (recent work, active goals, current focus) displayed in the terminal,
**Resulting in** zero ramp-up time, immediate context awareness, and 10x faster project resumption.

### Success Criteria

| Criterion | Target | Measurement |
|-----------|--------|-------------|
| Startup Overhead | <200ms | `time` command on hook execution |
| Adoption Rate | >90% | % of sessions where intelligence is displayed |
| Context Recovery Time | <10 seconds | Time from shell open → productive work |
| User Satisfaction | 9/10 | Subjective feedback after 1 week |

### Non-Goals

- Complex terminal UI with colors/formatting (keep simple)
- Integration with non-bash shells (zsh/fish support later)
- Remote session support (local only for v1)

---

## Phase 3: The Reality Check

### Feasibility Assessment

**Technical Feasibility**: ✅ HIGH
- Shell hooks via `.bashrc`/`.zshrc` are standard
- Python bridge already has `session-context` command
- Pattern proven by local-orchestrator daemon

**Resource Feasibility**: ✅ HIGH
- 2-3 hours implementation
- No new dependencies
- Uses existing intelligence infrastructure

**Prioritization**: ✅ HIGH VALUE
- Directly increases intelligence system ROI
- Solves real friction point
- Enables "always-on" intelligence vision

### Risk Analysis

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Slows shell startup | Medium | High | Run in background, timeout after 200ms |
| Breaks on error | Low | Medium | Wrap in try-catch, fail silently |
| Annoying for short sessions | Low | Low | Only show if >24h since last session |

---

## Phase 4: Creative Design (The "How")

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Shell Startup (.bashrc / .zshrc)                      │
│  ├─ Detect if in Cortex-tracked project                │
│  ├─ Check if >24h since last session                   │
│  └─ Trigger: ~/.claude/hooks/session_bootstrap.sh      │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│  Session Bootstrap Hook (session_bootstrap.sh)         │
│  ├─ Run: python bridge.py session-context              │
│  ├─ Format output for terminal display                 │
│  └─ Store timestamp in ~/.claude/session/.last_load    │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│  Bridge CLI (bridge.py session-context)                │
│  ├─ Load session context from cache                    │
│  ├─ If stale (>1h), regenerate from git log            │
│  └─ Return JSON: recent_work, active_goals, focus      │
└─────────────────────────────────────────────────────────┘
```

### Component Breakdown

**Component 1: Shell Hook Installer**
- File: `cortex/intelligence/install_session_hook.sh`
- Function: Adds hook trigger to `.bashrc`/`.zshrc`
- Idempotent: Won't add duplicate entries

**Component 2: Session Bootstrap Script**
- File: `~/.claude/hooks/session_bootstrap.sh`
- Function: Queries intelligence and displays formatted output
- Performance: Runs in <200ms with timeout

**Component 3: Enhanced Session Context Command**
- File: Already exists in `bridge.py`
- Enhancement: Add timestamp tracking for "last loaded"

### Implementation Approach

**Step 1**: Create bootstrap script
```bash
#!/bin/bash
# ~/.claude/hooks/session_bootstrap.sh

# Check if in Cortex-tracked project
if [ ! -f "PLAN.md" ] && [ ! -f ".cortex" ]; then
    exit 0
fi

# Check last load time (skip if <24h)
LAST_LOAD=~/.claude/session/.last_load
if [ -f "$LAST_LOAD" ]; then
    HOURS_AGO=$(( ($(date +%s) - $(stat -f%m "$LAST_LOAD")) / 3600 ))
    if [ $HOURS_AGO -lt 24 ]; then
        exit 0
    fi
fi

# Load session intelligence (with timeout)
timeout 0.2s python ~/Dev/cortex/bridge.py session-context --format=terminal 2>/dev/null || exit 0

# Update timestamp
touch "$LAST_LOAD"
```

**Step 2**: Add to shell RC file
```bash
# In ~/.bashrc or ~/.zshrc
if [ -f ~/.claude/hooks/session_bootstrap.sh ]; then
    source ~/.claude/hooks/session_bootstrap.sh
fi
```

**Step 3**: Add terminal format to bridge.py
```python
# In bridge.py session-context command
if args.format == 'terminal':
    print(f"\n🧠 Cortex Session Intelligence\n")
    print(f"📂 Project: {ctx.project}")
    print(f"🎯 Focus: {ctx.current_focus}")
    if ctx.active_goals:
        print(f"✅ Goals: {', '.join(ctx.active_goals[:3])}")
    print()
```

---

## Phase 5: Connecting the Dots

### Traceability Matrix

| Phase 2 Success Criterion | Phase 4 Component | How It's Achieved |
|---------------------------|-------------------|-------------------|
| Startup overhead <200ms | timeout in bootstrap script | Hard timeout kills slow queries |
| Adoption rate >90% | Auto-install in setup | Default enabled, user must opt-out |
| Context recovery <10s | Cached session context | Pre-computed, just display |
| User satisfaction 9/10 | Non-intrusive display | Only shows when valuable (>24h gap) |

### Validation

**Unit Tests**:
- Hook script runs in <200ms on cold start
- Handles missing session context gracefully
- Doesn't display if <24h since last load

**Integration Tests**:
- End-to-end: Open terminal → see intelligence → verify accuracy
- Works across different projects
- Doesn't break shell on errors

---

## Phase 6: Building the Plan

### Implementation Steps

1. **Create bootstrap script** (30 min)
   - File: [`~/.claude/hooks/session_bootstrap.sh`](file:///Users/jesse.kemp/.claude/hooks/session_bootstrap.sh)
   - Logic: Check conditions → query intelligence → display → timestamp

2. **Create installer script** (20 min)
   - File: [`cortex/intelligence/install_session_hook.sh`](file:///Users/jesse.kemp/Dev/cortex/intelligence/install_session_hook.sh)
   - Function: Add hook to `.bashrc`/`.zshrc` idempotently

3. **Add terminal format to bridge.py** (15 min)
   - Add `--format=terminal` flag
   - Format output for terminal display

4. **Test across scenarios** (15 min)
   - Fresh session after 24h
   - Fresh session within 24h
   - Non-Cortex project
   - Error conditions

5. **Update documentation** (10 min)
   - Add to [`CORTEX_USER_GUIDE.md`](file:///Users/jesse.kemp/Dev/.claude/CORTEX_USER_GUIDE.md)
   - Add to [`CORTEX_QUICK_REFERENCE.md`](file:///Users/jesse.kemp/Dev/.claude/CORTEX_QUICK_REFERENCE.md)

**Total Time**: 90 minutes

### Dependencies

- ✅ Session context system (already built)
- ✅ Bridge CLI (already functional)
- ✅ Portfolio intelligence (operational)
- ⚠️ Session Manager module (needs recreation - already noted)

---

## Phase 7: Testing & Learning

### Test Plan

**Scenario 1**: First session in >24h
- Expected: Display full intelligence
- Verify: Timestamp updated, output shown

**Scenario 2**: Second session within 24h
- Expected: Silent (no display)
- Verify: Hook exits early

**Scenario 3**: Non-Cortex project
- Expected: Silent (no display)
- Verify: Hook exits immediately

**Scenario 4**: Slow intelligence query
- Expected: Timeout after 200ms
- Verify: Shell not blocked

### Success Metrics (After 1 Week)

| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| Sessions with intelligence | >90% | TBD | ⏳ |
| Average display time | <200ms | TBD | ⏳ |
| User complaints | 0 | TBD | ⏳ |
| Context recovery time | <10s | TBD | ⏳ |

### Lessons to Capture

After implementation, document:
- What worked well (hook pattern, timing strategy)
- What didn't work (terminal formatting issues?)
- What surprised us (adoption rate, performance)
- What to do differently next time

---

## Appendix: Alternative Approaches Considered

### Alternative 1: MCP Server Auto-Start
**Pros**: Integrated with Claude Code
**Cons**: Only works in Claude Code, not terminal
**Decision**: Not chosen - need terminal support

### Alternative 2: Cron Job
**Pros**: Runs periodically without shell hook
**Cons**: Not triggered by actual session start
**Decision**: Not chosen - want real-time on session open

### Alternative 3: Fish/Zsh Plugin
**Pros**: Native shell integration
**Cons**: Shell-specific, harder to maintain
**Decision**: Not chosen - keep it simple with bash script

---

**Status**: Ready for Implementation
**Next Step**: Create [`install_session_hook.sh`](file:///Users/jesse.kemp/Dev/cortex/intelligence/install_session_hook.sh) and test
