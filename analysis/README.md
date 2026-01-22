# Cortex Analysis System

Automated codebase analysis and health monitoring using batch AI processing.

---

## Purpose

The analysis system runs comprehensive audits across all Cortex portfolio projects:
- **Security scanning** - Identify vulnerabilities and security issues
- **Test coverage analysis** - Find critical untested paths
- **Code quality** - Detect maintainability issues and tech debt
- **Dependency audits** - Check for vulnerable or outdated dependencies
- **Documentation completeness** - Ensure adequate documentation

**Key Feature:** Results feed back into Cortex's portfolio memory, enabling the system to learn from past analyses and proactively recommend improvements.

---

## Directory Structure

```
cortex/analysis/
├── README.md                    ← This file
├── reports/                     ← Analysis reports (organized by date)
│   ├── 2026-01-19-overnight/    ← Date-stamped analysis runs
│   │   ├── summary.md           ← Executive summary
│   │   ├── security.md          ← Security findings
│   │   ├── test-coverage.md     ← Testing gaps
│   │   ├── code-quality.md      ← Code quality issues
│   │   ├── dependencies.md      ← Dependency vulnerabilities
│   │   └── documentation.md     ← Docs completeness
│   └── archive/                 ← Historical analyses
├── templates/                   ← Prompt templates for analyses
│   ├── security_audit.yaml
│   ├── test_coverage.yaml
│   └── dependency_audit.yaml
└── processors/                  ← Result processors and integrations
    ├── __init__.py
    ├── security_processor.py    ← Parse security findings
    ├── coverage_processor.py    ← Parse test coverage gaps
    └── memory_integrator.py     ← Feed findings to portfolio memory
```

---

## Analysis Types

### 1. Security Audit

**Prompt Template:** `templates/security_audit.yaml`

**Checks:**
- Hardcoded credentials
- SQL injection vulnerabilities
- Path traversal risks
- Insecure file permissions
- Command injection
- Input validation gaps

**Output:** `reports/YYYY-MM-DD-*/security.md`

**Example Finding:**
```markdown
### C-1: Hardcoded Absolute Path Exposes Username
**Severity:** CRITICAL
**File:** cortex/README.md:21

**Fix:**
```yaml
# Bad
root_dir: ~/Dev

# Good
root_dir: ~/Dev
```
```

### 2. Test Coverage Analysis

**Prompt Template:** `templates/test_coverage.yaml`

**Checks:**
- Critical paths without tests
- Edge cases not covered
- Integration test gaps
- Error scenario coverage
- Business logic testing

**Output:** `reports/YYYY-MM-DD-*/test-coverage.md`

### 3. Code Quality Scan

**Prompt Template:** `templates/code_quality.yaml`

**Checks:**
- God classes (>500 lines)
- High complexity functions
- Code duplication
- Tech debt markers (TODO, FIXME)
- Naming conventions

**Output:** `reports/YYYY-MM-DD-*/code-quality.md`

### 4. Dependency Audit

**Prompt Template:** `templates/dependency_audit.yaml`

**Checks:**
- CVE vulnerabilities
- Outdated packages
- Missing version pins
- Unused dependencies
- License compliance

**Output:** `reports/YYYY-MM-DD-*/dependencies.md`

### 5. Documentation Completeness

**Prompt Template:** `templates/docs_completeness.yaml`

**Checks:**
- Missing README sections
- Undocumented public APIs
- Missing setup instructions
- Architecture documentation gaps

**Output:** `reports/YYYY-MM-DD-*/documentation.md`

---

## Running Analyses

### Option 1: Via Batch Queue (Recommended)

Create a queue definition with analysis tasks:

```bash
# Use the overnight analysis queue as template
cp cortex/batch/queues/remediation_queue.json cortex/batch/queues/analysis_queue.json

# Edit to focus on analysis tasks
vim cortex/batch/queues/analysis_queue.json

# Submit to queue
cp cortex/batch/queues/analysis_queue.json ~/.cortex/batches/analysis_queue.json
cortex/batch/queue.sh process
```

### Option 2: Direct Batch Submission

```python
from cortex.batch.batch_api_client import BatchAPIClient, BatchRequest

client = BatchAPIClient()

# Load analysis prompts from templates
security_prompt = Path("cortex/analysis/templates/security_audit.yaml").read_text()

# Create batch request
requests = [
    BatchRequest(
        custom_id="security_scan",
        params={
            "messages": [{"role": "user", "content": security_prompt}],
            "max_tokens": 4000
        }
    )
]

# Submit
batch_id = client.submit_batch(requests, description="Security Audit")
```

### Option 3: CLI (Future)

```bash
# Run all analyses
cortex analyze all

# Run specific analysis
cortex analyze security
cortex analyze coverage

# Schedule nightly analysis
cortex analyze schedule --cron "0 2 * * *"
```

---

## Report Organization

### Naming Convention

Reports are organized by date and type:

```
reports/
└── YYYY-MM-DD-<description>/
    ├── summary.md           # Executive summary with key findings
    ├── security.md          # Full security audit
    ├── test-coverage.md     # Testing gaps analysis
    ├── code-quality.md      # Code quality issues
    ├── dependencies.md      # Dependency vulnerabilities
    └── documentation.md     # Documentation audit
```

### Report Format

Each report follows this structure:

1. **Executive Summary** - Critical findings count, severity breakdown
2. **Critical Issues** - Highest priority items requiring immediate action
3. **High Priority** - Important issues to address soon
4. **Medium/Low Priority** - Nice-to-have improvements
5. **Remediation Plan** - Prioritized action items with timelines
6. **Metrics** - Quantitative assessment (counts, percentages, estimates)

---

## Integration with Portfolio Memory

Analysis results automatically feed into Cortex's learning system:

```python
from cortex.analysis.processors.memory_integrator import integrate_findings

# After analysis completes
findings = load_analysis_report("2026-01-19-overnight/security.md")

# Teach portfolio memory
integrate_findings(findings)

# Now Cortex knows:
# - Common security patterns across projects
# - Recurring testing gaps
# - Frequently vulnerable dependencies
# - Code quality anti-patterns
```

**Benefits:**
- Proactive recommendations: "Based on past analyses, consider adding input validation to this new API"
- Pattern recognition: "This code pattern led to bugs in 3 other projects"
- Learning from fixes: "Security issue X was fixed with approach Y"

---

## Automation

### Nightly Analysis

Use cron or launchd to schedule regular analyses:

```bash
# Add to crontab
0 2 * * * cd ~/Dev && cortex/batch/queue.sh process
```

Or use the queue manager's continuous mode:

```bash
# Runs continuously, checking every 5 minutes
cortex/batch/queue.sh start
```

### Post-Commit Analysis

Trigger analysis after significant changes:

```bash
# .git/hooks/post-commit
#!/bin/bash
if [ $(git diff --stat HEAD~1 | wc -l) -gt 50 ]; then
    echo "Large commit detected, queuing analysis..."
    cortex/batch/queue.sh process
fi
```

---

## Example: Overnight Analysis (Jan 19, 2026)

See `reports/2026-01-19-overnight/` for a complete analysis run:

**Summary:**
- **65+ findings** across 3 projects
- **13 critical** security/dependency issues
- **23 high-priority** test coverage gaps
- **Estimated fix time:** 40-60 hours
- **Risk reduction:** 85% after critical fixes

**Outcome:**
- Created remediation queue with 10 prioritized tasks
- Week 1 (critical fixes) auto-submitted to batch API
- Week 2 (high priority) queued with dependency on Week 1
- All findings documented for future reference

---

## Metrics Tracking

Track analysis trends over time:

```python
from cortex.analysis.processors.metrics_tracker import AnalysisMetrics

metrics = AnalysisMetrics()

# Record findings
metrics.record_analysis(
    date="2026-01-19",
    type="security",
    findings={
        "critical": 2,
        "high": 4,
        "medium": 3,
        "low": 2
    }
)

# View trends
metrics.get_trend("security", days=30)
# → Shows if security issues are increasing/decreasing
```

---

## Best Practices

1. **Run analyses regularly** - Weekly or after major changes
2. **Act on critical findings immediately** - Don't let security issues linger
3. **Track remediation progress** - Use the batch queue system
4. **Learn from patterns** - Let portfolio memory guide future development
5. **Document fixes** - Help Cortex learn what worked
6. **Archive historical reports** - Track improvement over time

---

## Roadmap

### Current Features
- ✅ Batch-based analysis system
- ✅ 5 analysis types (security, coverage, quality, deps, docs)
- ✅ Structured report organization
- ✅ Integration with batch queue

### Planned Features
- [ ] Automated memory integration (learn from findings)
- [ ] CLI commands for analysis
- [ ] Web dashboard for viewing reports
- [ ] Trend analysis and metrics tracking
- [ ] Custom analysis templates
- [ ] Incremental analysis (only changed files)
- [ ] Integration with pre-commit hooks
- [ ] Slack/email notifications for critical findings

---

## Related Documentation

- [Batch System](../batch/README.md)
- [Portfolio Memory](../intelligence/README.md)
- [Queue Management](../batch/README.md#queue-manager)

---

**Last Updated:** 2026-01-20
