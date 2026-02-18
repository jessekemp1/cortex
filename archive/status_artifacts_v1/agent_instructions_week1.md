# Week 1 Agent Instructions

## Agent Team Alpha: Core Modules (Parallel)

### Agent 1: Portfolio Memory
**File**: ~/Dev/cortex/portfolio_memory.py
**Source**: ~/Dev/PARALLEL_CONVERGENCE_MANIFESTO.md Appendix A.1
**Tasks**:
1. Implement PortfolioMemory class
2. Methods: register_project, add_pattern, add_lesson, record_recommendation, record_outcome
3. JSON persistence to ~/.claude/portfolio/
4. Unit tests in tests/unit/test_portfolio_memory.py

**Success Criteria**:
- All CRUD operations working
- Data persists across sessions
- <100ms for stats queries

---

### Agent 2: Session Manager
**File**: ~/Dev/cortex/session_manager.py
**Source**: ~/Dev/PARALLEL_CONVERGENCE_MANIFESTO.md Appendix A.2
**Tasks**:
1. Implement SessionManager class
2. Git context extraction (branch, commits, status)
3. Project detection (walk up directory tree)
4. Goal inference from commit messages
5. Unit tests in tests/unit/test_session_manager.py

**Success Criteria**:
- Context generated in <300ms
- Works in any git repo
- Formatted output matches spec

---

### Agent 3: Spec Knowledge Base
**File**: ~/Dev/cortex/spec_knowledge_base.py
**Source**: ~/Dev/PARALLEL_CONVERGENCE_MANIFESTO.md Appendix A.3
**Tasks**:
1. Implement SpecKnowledgeBase class
2. Spec indexing (index_spec, index_project)
3. Hash-based semantic search
4. Metadata extraction
5. Unit tests in tests/unit/test_spec_knowledge_base.py

**Success Criteria**:
- Can index existing 73 specs
- Search returns relevant results
- <5s for full project indexing
