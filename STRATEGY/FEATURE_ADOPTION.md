# Converx Feature Adoption Roadmap

**Version**: 1.0  
**Date**: January 2025

---

## Overview

This document guides you through adopting Converx features in the optimal order. Each feature includes prerequisites, learning curve, common mistakes, and pro tips.

**Key Principle**: Adopt features as they provide value, not because they exist. Start simple, add complexity only when proven useful.

---

## Phase 0 Features (MVP) - Available Now

### Feature: `converx next`

**What It Does**: Returns your top strategic recommendation with rationale

**Prerequisites**: None (works out of the box)

**Learning Curve**: 5 minutes
- Run the command
- Read the output
- Understand the recommendation

**When to Use**:
- Morning check-in (daily)
- Starting new work session
- Feeling overwhelmed (decision paralysis)
- Need strategic focus

**Common Mistakes**:
- ❌ Expecting perfect recommendations immediately (system needs time to learn)
- ❌ Ignoring recommendations (can't learn if you don't follow)
- ❌ Treating as task list (it's strategic, not tactical)

**Pro Tips**:
- Use daily for 1 week to establish habit
- Track which recommendations you follow and why
- Note when recommendations are accurate vs inaccurate
- Adjust expectations based on your patterns

---

### Feature: `converx status`

**What It Does**: Shows current state summary (projects, goals, blockers)

**Prerequisites**: None

**Learning Curve**: 2 minutes
- Run the command
- Understand the metrics
- Interpret the state

**When to Use**:
- Evening reflection (daily)
- Quick state check (midday)
- Weekly review
- Before making major decisions

**Common Mistakes**:
- ❌ Not updating ACTION_PLAN.md (stale goals = irrelevant recommendations)
- ❌ Ignoring blockers (they accumulate)
- ❌ Not tracking changes over time

**Pro Tips**:
- Use for evening reflection routine
- Track how state changes day to day
- Identify patterns in blockers
- Use before major decisions for context

---

### Feature: `converx next PROJECT`

**What It Does**: Filters recommendations to specific project

**Prerequisites**: Understanding of `converx next`

**Learning Curve**: 1 minute
- Add project name argument
- See filtered recommendations

**When to Use**:
- Deep work on specific project
- Project-specific planning
- Context switching between projects
- Project review

**Common Mistakes**:
- ❌ Using when you should see global view
- ❌ Not knowing project names (use `converx status` to see active projects)

**Pro Tips**:
- Use for focused project work
- Combine with `--with-context` for new projects
- Track which projects get most recommendations
- Use to balance project focus

---

### Feature: `converx next --with-context`

**What It Does**: Includes context predictions (files, docs, knowledge)

**Prerequisites**: `context_intelligence.py` available

**Learning Curve**: 2 minutes
- Understand context predictions
- Use context for new work

**When to Use**:
- Starting new work
- Context switching
- Learning new codebase
- Research phase

**Common Mistakes**:
- ❌ Using when context is obvious (adds overhead)
- ❌ Not trusting context predictions (they improve over time)

**Pro Tips**:
- Use when starting new work or projects
- Track context prediction accuracy
- Use to reduce context switching overhead
- Combine with project filtering for focused context

---

### Feature: `converx next --json`

**What It Does**: Outputs structured JSON for programmatic use

**Prerequisites**: Understanding of JSON, programming knowledge

**Learning Curve**: 10 minutes
- Understand JSON structure
- Parse JSON in your scripts
- Integrate with your tools

**When to Use**:
- Automation scripts
- Tool integration
- Custom workflows
- Data analysis

**Common Mistakes**:
- ❌ Using when human-readable is better
- ❌ Not handling missing fields

**Pro Tips**:
- Use for automation and integration
- Create custom scripts that parse JSON
- Integrate with your existing tools
- Build custom workflows

---

## Phase 1 Features (Weather + Scenarios) - Coming Soon

### Feature: `converx weather`

**What It Does**: Shows Life Weather Map for Work/Code domain

**Prerequisites**: Understanding of weather metaphor, Phase 0 features

**Learning Curve**: 10 minutes
- Understand weather states (calm, moderate, high pressure, storm)
- Interpret pressure scores
- Use for decision-making

**When to Use**:
- Morning check-in (replaces or supplements `converx next`)
- Before making major decisions
- Weekly review
- When feeling overwhelmed

**Common Mistakes**:
- ❌ Treating as absolute truth (it's a metaphor, not precision)
- ❌ Not acting on weather signals (high pressure = take action)

**Pro Tips**:
- Use weather to frame your state
- Track weather patterns over time
- Use weather to guide decisions (storm = reduce scope)
- Combine with scenario bands for full picture

---

### Feature: Scenario Bands (`converx next --scenarios`)

**What It Does**: Shows optimistic/likely/conservative scenarios for recommendations

**Prerequisites**: Understanding of uncertainty, Phase 0 features

**Learning Curve**: 15 minutes
- Understand scenario bands
- Interpret confidence levels
- Use for decision-making

**When to Use**:
- Major decisions
- Planning timelines
- Evaluating options
- Risk assessment

**Common Mistakes**:
- ❌ Only looking at optimistic (unrealistic planning)
- ❌ Only looking at conservative (overly cautious)
- ❌ Not tracking which scenario actually happens

**Pro Tips**:
- Use all three scenarios for full picture
- Track which scenario you're actually on
- Use scenarios to evaluate trade-offs
- Adjust plans based on scenario tracking

---

### Feature: `converx complete WAYPOINT_ID`

**What It Does**: Marks waypoint as complete, tracks progress

**Prerequisites**: Understanding of waypoints, routes

**Learning Curve**: 5 minutes
- Understand waypoint concept
- Mark waypoints complete
- Track progress

**When to Use**:
- After completing recommended actions
- Tracking route progress
- Updating state

**Common Mistakes**:
- ❌ Not marking waypoints complete (breaks progress tracking)
- ❌ Marking incomplete waypoints (breaks accuracy)

**Pro Tips**:
- Mark waypoints immediately after completion
- Use progress tracking for motivation
- Review progress weekly
- Adjust routes based on progress

---

## Phase 2 Features (Routes + Multi-Domain) - Future

### Feature: `converx route "GOAL"`

**What It Does**: Creates or views route to goal completion

**Prerequisites**: Understanding of routes, waypoints, goals

**Learning Curve**: 20 minutes
- Understand route concept
- Create routes from goals
- Navigate routes
- Track progress

**When to Use**:
- Major goals (weeks/months)
- Complex projects
- Strategic initiatives
- Multi-step objectives

**Common Mistakes**:
- ❌ Creating routes for simple tasks (overkill)
- ❌ Not updating routes as goals change
- ❌ Ignoring route progress

**Pro Tips**:
- Use routes for goals >1 week
- Review routes weekly
- Adjust routes based on progress
- Use routes to break down complex goals

---

### Feature: `converx forecast ROUTE_ID`

**What It Does**: Shows scenario bands for route completion

**Prerequisites**: Understanding of routes, scenario bands

**Learning Curve**: 10 minutes
- Understand route forecasting
- Interpret scenario bands for routes
- Use for planning

**When to Use**:
- Planning major initiatives
- Evaluating route options
- Risk assessment
- Timeline planning

**Common Mistakes**:
- ❌ Not updating forecasts as progress changes
- ❌ Ignoring conservative scenario (unrealistic planning)

**Pro Tips**:
- Update forecasts weekly
- Track which scenario you're on
- Use forecasts to adjust routes
- Share forecasts with stakeholders

---

### Feature: `converx domains`

**What It Does**: Shows weather for all domains (Work, Health, Finance, etc.)

**Prerequisites**: Understanding of weather map, multi-domain concept

**Learning Curve**: 15 minutes
- Understand multi-domain concept
- Interpret domain weather
- Use for holistic planning

**When to Use**:
- Weekly review
- Major decisions
- Life planning
- Cross-domain optimization

**Common Mistakes**:
- ❌ Optimizing domains in silos (ignoring cross-domain impacts)
- ❌ Not acting on domain weather signals

**Pro Tips**:
- Review domains weekly
- Track cross-domain impacts
- Use domains for holistic planning
- Balance domains, don't optimize in silos

---

## Phase 3 Features (Integrations) - Future

### Feature: Connectors

**What It Does**: Connects to external data sources (GitHub, Google Fit, etc.)

**Prerequisites**: Understanding of data sources, API setup

**Learning Curve**: 30-60 minutes per connector
- Set up API credentials
- Configure connector
- Understand data flow
- Use in recommendations

**When to Use**:
- When you have data sources available
- When you want richer insights
- When you want cross-domain awareness

**Common Mistakes**:
- ❌ Setting up all connectors at once (overwhelming)
- ❌ Not maintaining credentials (connectors break)
- ❌ Expecting perfect data (some sources are noisy)

**Pro Tips**:
- Start with one connector (personal-ai-dataset is easiest)
- Add connectors incrementally
- Verify data quality
- Use connectors that provide most value

**Priority Order**:
1. **personal-ai-dataset**: Knowledge base (high value, low friction)
2. **GitHub**: Repo status (if using GitHub)
3. **Google Fit**: Health metrics (if available)
4. **Alpha Arena**: Financial data (if using)
5. **Custom**: Your specific tools

---

### Feature: `converx search "QUERY"`

**What It Does**: Searches across all connected data sources

**Prerequisites**: At least one connector enabled

**Learning Curve**: 5 minutes
- Understand search interface
- Use search for context
- Interpret results

**When to Use**:
- Research phase
- Context gathering
- Knowledge retrieval
- Cross-source synthesis

**Common Mistakes**:
- ❌ Expecting perfect results (search is probabilistic)
- ❌ Not using search when needed (manual context gathering)

**Pro Tips**:
- Use search for research and context
- Combine search with recommendations
- Track search result quality
- Improve search with better queries

---

## Phase 4 Features (Playbooks) - Future

### Feature: `converx playbooks`

**What It Does**: Lists available playbooks for execution

**Prerequisites**: Understanding of playbooks, policy engine

**Learning Curve**: 30 minutes
- Understand playbook concept
- Review available playbooks
- Understand approval levels
- Execute playbooks safely

**When to Use**:
- Routine tasks (tests, analysis)
- Repetitive workflows
- Automated actions
- Bounded execution

**Common Mistakes**:
- ❌ Executing playbooks without understanding (risky)
- ❌ Not reviewing playbook steps (unexpected actions)
- ❌ Ignoring approval requirements (safety)

**Pro Tips**:
- Start with read-only playbooks (analyze, test)
- Review playbook steps before execution
- Use dry-run mode first
- Gradually increase autonomy as trust builds

**Safe Playbooks to Start With**:
- `analyze_repo`: Read-only analysis
- `run_tests`: Test execution
- `health_review`: Data aggregation

---

### Feature: `converx run PLAYBOOK_ID`

**What It Does**: Executes a playbook with policy enforcement

**Prerequisites**: Understanding of playbooks, policies

**Learning Curve**: 20 minutes
- Understand execution flow
- Handle approvals
- Interpret results
- Debug failures

**When to Use**:
- Routine tasks
- Automated workflows
- Bounded execution
- Time-saving operations

**Common Mistakes**:
- ❌ Not reviewing playbook before execution
- ❌ Ignoring approval prompts
- ❌ Not checking results

**Pro Tips**:
- Always review playbook before first execution
- Use dry-run mode to preview
- Start with low-risk playbooks
- Gradually increase autonomy

---

## Phase 5 Features (Virtual Twin) - Future

### Feature: `converx simulate ROUTE_ID`

**What It Does**: Simulates route outcomes using virtual twin

**Prerequisites**: Understanding of routes, virtual twin, simulation

**Learning Curve**: 30 minutes
- Understand simulation concept
- Interpret simulation results
- Use for decision-making
- Calibrate twin accuracy

**When to Use**:
- Major decisions
- Route evaluation
- Risk assessment
- Outcome prediction

**Common Mistakes**:
- ❌ Treating simulations as truth (they're probabilistic)
- ❌ Not calibrating twin (accuracy degrades)
- ❌ Ignoring simulation warnings (burnout risk, etc.)

**Pro Tips**:
- Use simulations for major decisions
- Track simulation accuracy
- Calibrate twin regularly
- Use simulations to evaluate trade-offs

---

### Feature: `converx twin`

**What It Does**: Shows current virtual twin state

**Prerequisites**: Understanding of virtual twin, state model

**Learning Curve**: 20 minutes
- Understand state variables
- Interpret state values
- Use for planning
- Track state over time

**When to Use**:
- State review
- Planning decisions
- Energy management
- Capacity planning

**Common Mistakes**:
- ❌ Not updating twin with actuals (accuracy degrades)
- ❌ Ignoring state warnings (burnout risk, etc.)

**Pro Tips**:
- Review twin state weekly
- Update twin with actuals
- Use state for planning
- Track state trends

---

### Feature: `converx reflect`

**What It Does**: Analyzes prediction accuracy and learns from outcomes

**Prerequisites**: Historical data (30+ days), predictions recorded

**Learning Curve**: 15 minutes
- Understand reflection process
- Interpret accuracy metrics
- Use for calibration
- Improve predictions

**When to Use**:
- Weekly review
- Monthly analysis
- Calibration check
- Model improvement

**Common Mistakes**:
- ❌ Not recording predictions (can't reflect)
- ❌ Not recording actuals (can't compare)
- ❌ Ignoring reflection insights (missed learning)

**Pro Tips**:
- Record predictions regularly
- Record actuals when available
- Review reflections weekly
- Use insights to improve

---

## Adoption Strategy

### Week 1: Foundation
- Use `converx next` daily
- Use `converx status` for reflection
- Establish habits

### Week 2-4: Integration
- Add `--with-context` for new work
- Use project filtering for focused work
- Track patterns

### Month 2-3: Optimization
- Begin tracking prediction accuracy
- Identify personal patterns
- Calibrate expectations

### Month 4-6: Advanced
- Adopt Phase 1 features (weather, scenarios)
- Use routes for major goals
- Enable connectors for richer data

### Month 6+: Mastery
- Use playbooks for automation
- Leverage virtual twin for simulation
- Continuous optimization

---

## Common Adoption Mistakes

### Mistake 1: Trying Everything at Once

**Problem**: Overwhelming, no value proven

**Solution**: Start with Phase 0, add features incrementally

### Mistake 2: Not Using Features That Exist

**Problem**: Missing value from available features

**Solution**: Review feature list, adopt as they provide value

### Mistake 3: Adopting Features Before Prerequisites

**Problem**: Confusion, frustration, no value

**Solution**: Follow prerequisite order, master basics first

### Mistake 4: Not Tracking Value

**Problem**: Can't tell if features are helping

**Solution**: Track metrics, measure impact, adjust adoption

---

*"Feature adoption is not about using every feature. It's about using the right features at the right time to maximize value. Start simple. Add complexity only when proven useful."*
