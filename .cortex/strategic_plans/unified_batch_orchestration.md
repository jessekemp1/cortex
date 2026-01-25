# Unified Batch Orchestration Architecture
**Date:** 2026-01-21
**Status:** Design
**Problem:** Two batch systems don't communicate; jobs routed to wrong queues
**Solution:** Unified orchestrator that routes intelligently

---

## Design Principles

1. **Preserve Both Systems** - Don't break existing functionality
2. **Intelligent Routing** - Jobs go to correct system automatically
3. **Unified Interface** - Single CLI for all batch operations
4. **Backward Compatible** - Existing code keeps working
5. **Type Safety** - Clear distinction between local and API jobs

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│              BatchOrchestrator (NEW)                    │
│                                                         │
│  - Analyzes job type (local cmd vs API prompt)         │
│  - Routes to appropriate backend                       │
│  - Unified status/monitoring                           │
│  - Job type detection logic                            │
└─────────────────────────────────────────────────────────┘
                    │
        ┌───────────┴───────────┐
        ▼                       ▼
┌──────────────────┐   ┌──────────────────┐
│ LocalExecutor    │   │ APIBatchClient   │
│ (ProcessMonitor) │   │ (QueueManager)   │
│                  │   │                  │
│ - Shell commands │   │ - LLM prompts    │
│ - Local files    │   │ - Analysis       │
│ - Tests/builds   │   │ - Research       │
└──────────────────┘   └──────────────────┘
```

---

## Component Design

### 1. BatchOrchestrator (New - `batch/orchestrator.py`)

**Responsibilities:**
- Accept job submissions
- Detect job type (local vs API)
- Route to correct backend
- Provide unified status view
- Handle cross-system dependencies

**API:**
```python
class BatchOrchestrator:
    def submit_job(
        self,
        job: Union[LocalJob, APIJob],
        auto_detect: bool = True
    ) -> str:
        """
        Submit a job to appropriate backend.

        Args:
            job: Job definition (LocalJob or APIJob)
            auto_detect: Auto-detect backend from job type

        Returns:
            job_id (with prefix: local_* or api_*)
        """

    def get_status(self, job_id: str) -> JobStatus:
        """Get status from either backend."""

    def list_jobs(
        self,
        backend: Optional[Literal["local", "api", "both"]] = "both"
    ) -> List[JobStatus]:
        """List jobs from one or both backends."""
```

**Detection Logic:**
```python
def detect_job_type(job: Dict) -> Literal["local", "api"]:
    """
    Detect whether job is local execution or API batch.

    Local indicators:
    - Has "command" field with shell command
    - Has "task_type" in [test, build, deploy, lint]
    - Command starts with known tools: pytest, npm, python, bash

    API indicators:
    - Has "prompt" or "tasks" field
    - Has "description" but no "command"
    - Priority in [high, normal, low] (not immediate)
    - Has "estimated_tokens" field
    - Source in [security, docs, research, pattern, goal]

    Returns:
        "local" or "api"
    """
```

---

### 2. Unified Job Format

**Base Job (Common Fields):**
```python
@dataclass
class BaseJob:
    id: str
    description: str
    priority: Literal["immediate", "high", "normal", "low"]
    created_at: datetime
    metadata: Dict[str, Any]
```

**LocalJob (Extends BaseJob):**
```python
@dataclass
class LocalJob(BaseJob):
    command: str  # Shell command to execute
    task_type: str  # test, build, deploy, lint, etc.
    working_dir: Optional[Path] = None
    timeout_seconds: int = 3600
    dependencies: List[str] = field(default_factory=list)
```

**APIJob (Extends BaseJob):**
```python
@dataclass
class APIJob(BaseJob):
    tasks: List[APITask]  # List of prompts for batch
    estimated_total_tokens: int
    source: str  # security, docs, research, pattern, goal
    project: Optional[str] = None

@dataclass
class APITask:
    task_id: str
    title: str
    prompt: str
    context: str
    files_affected: List[str]
    estimated_tokens: int
```

---

### 3. Unified CLI Interface

**New Commands:**
```bash
# Unified interface (auto-routing)
cortex batch submit <job_definition.json>    # Auto-detects type
cortex batch list [--type local|api|all]     # List all jobs
cortex batch status <job_id>                 # Any job ID
cortex batch cancel <job_id>                 # Any job ID

# Explicit backend (override auto-detection)
cortex batch:local add "pytest tests/" --type test
cortex batch:api submit security_audit.json

# Legacy commands (backward compatible)
cortex batch add "pytest tests/"  # Still works, routes to local
```

**Implementation:**
```python
# cli.py additions

def cmd_batch_submit(args):
    """Unified batch submission with auto-routing."""
    from batch.orchestrator import BatchOrchestrator

    orchestrator = BatchOrchestrator()

    # Load job definition
    if args.job_file:
        with open(args.job_file) as f:
            job_data = json.load(f)
    else:
        # Build from CLI args
        job_data = {
            "description": args.description,
            "priority": args.priority,
            "command": args.command if args.command else None,
            "prompt": args.prompt if hasattr(args, 'prompt') else None,
        }

    # Submit with auto-detection
    job_id = orchestrator.submit_job(job_data, auto_detect=True)

    # Print result with backend indicator
    backend = "local" if job_id.startswith("local_") else "api"
    print(f"✅ Job submitted to {backend} backend")
    print(f"Job ID: {job_id}")

def cmd_batch_list(args):
    """List jobs from both backends."""
    from batch.orchestrator import BatchOrchestrator

    orchestrator = BatchOrchestrator()
    jobs = orchestrator.list_jobs(backend=args.type or "both")

    # Group by backend
    local_jobs = [j for j in jobs if j.backend == "local"]
    api_jobs = [j for j in jobs if j.backend == "api"]

    if local_jobs:
        print("LOCAL EXECUTION QUEUE")
        print("=" * 60)
        for job in local_jobs:
            print(f"  {job.status_icon} [{job.priority}] {job.description}")
            print(f"     ID: {job.id} | State: {job.state}")

    if api_jobs:
        print("\nAPI BATCH QUEUE")
        print("=" * 60)
        for job in api_jobs:
            print(f"  {job.status_icon} [{job.priority}] {job.description}")
            print(f"     ID: {job.id} | State: {job.state}")
```

---

### 4. Fix intelligent_orchestrator.py

**Current (Broken):**
```python
# Submits to wrong queue
result = subprocess.run([
    "python", "cli.py", "batch", "add",
    job.description, "--priority", job.priority
])
```

**Fixed (Option A - Direct Queue Write):**
```python
def submit_to_api_queue(self, job: BatchWorkItem) -> str:
    """Submit job directly to API batch queue."""
    queue_file = Path.home() / ".cortex" / "batches" / "remediation_queue.json"

    # Load existing queue
    with open(queue_file) as f:
        queue_data = json.load(f)

    # Convert BatchWorkItem to queue format
    job_definition = {
        "id": job.id,
        "priority": job.priority.upper(),
        "status": "queued",
        "description": job.description,
        "tasks": [{
            "task_id": f"{job.id}_task_1",
            "title": job.title,
            "prompt": job.prompt,
            "context": "",
            "files_affected": job.files,
            "estimated_tokens": job.estimated_input_tokens
        }],
        "estimated_total_tokens": job.total_tokens,
        "request_count": 1,
        "depends_on": []
    }

    # Append to queue
    queue_data["priority_jobs"].append(job_definition)

    # Save queue
    with open(queue_file, "w") as f:
        json.dump(queue_data, f, indent=2)

    return job.id
```

**Fixed (Option B - Use Orchestrator):**
```python
def submit_via_orchestrator(self, job: BatchWorkItem) -> str:
    """Submit job via BatchOrchestrator (better!)."""
    from batch.orchestrator import BatchOrchestrator

    orchestrator = BatchOrchestrator()

    # Convert to APIJob format
    api_job = {
        "description": job.description,
        "priority": job.priority,
        "tasks": [{
            "task_id": f"{job.id}_task_1",
            "title": job.title,
            "prompt": job.prompt,
            "context": "",
            "files_affected": job.files,
            "estimated_tokens": job.estimated_input_tokens
        }],
        "estimated_total_tokens": job.total_tokens,
        "source": job.source,
        "project": job.project
    }

    # Orchestrator detects this as API job and routes correctly
    job_id = orchestrator.submit_job(api_job, auto_detect=True)

    return job_id
```

---

### 5. Integration with queue_manager Daemon

**Current State:**
- queue_manager.py runs as standalone daemon
- Checks remediation_queue.json every 5 minutes
- No changes needed! It will automatically pick up jobs

**Enhancement (Optional):**
```python
# batch/orchestrator.py

def submit_job(self, job, auto_detect=True):
    """Submit job and optionally notify daemon."""
    job_id = self._route_and_submit(job, auto_detect)

    # If API job, send wake-up signal to daemon
    if job_id.startswith("api_"):
        self._notify_queue_manager()

    return job_id

def _notify_queue_manager(self):
    """Send SIGUSR1 to queue_manager to check queue immediately."""
    pid_file = Path.home() / ".cortex" / "batches" / "queue_manager.pid"
    if pid_file.exists():
        pid = int(pid_file.read_text().strip())
        try:
            os.kill(pid, signal.SIGUSR1)  # Wake up daemon
        except ProcessLookupError:
            pass  # Daemon not running, that's ok
```

---

## Migration Plan

### Phase 1: Add Orchestrator (Non-Breaking)
1. Create `batch/orchestrator.py` with BatchOrchestrator class
2. Add unified job formats (BaseJob, LocalJob, APIJob)
3. Implement routing logic
4. Add comprehensive tests

**Risk:** Low - Nothing breaks, new code only

### Phase 2: Add Unified CLI (Backward Compatible)
1. Add new commands: `cortex batch submit`, `cortex batch list`
2. Keep old commands working: `cortex batch add` routes to local
3. Update help text to guide users to new commands

**Risk:** Low - Old commands still work

### Phase 3: Fix intelligent_orchestrator
1. Update to use BatchOrchestrator.submit_job()
2. Remove subprocess calls to CLI
3. Add proper error handling
4. Test with dry-run first

**Risk:** Medium - Changes existing behavior, but fixable

### Phase 4: Documentation & Rollout
1. Update QUICK_START.md with unified interface
2. Add examples for both job types
3. Create batch_jobs_guide.md
4. Announce in commit message

**Risk:** Low - Documentation only

---

## Testing Strategy

### Unit Tests
```python
# tests/test_batch_orchestrator.py

def test_detect_local_job():
    job = {"command": "pytest tests/", "task_type": "test"}
    assert BatchOrchestrator().detect_job_type(job) == "local"

def test_detect_api_job():
    job = {
        "description": "Analyze code quality",
        "tasks": [{"prompt": "...", "estimated_tokens": 2000}]
    }
    assert BatchOrchestrator().detect_job_type(job) == "api"

def test_route_to_local_backend():
    orchestrator = BatchOrchestrator()
    job_id = orchestrator.submit_job({
        "command": "pytest tests/",
        "description": "Run tests"
    })
    assert job_id.startswith("local_")

def test_route_to_api_backend():
    orchestrator = BatchOrchestrator()
    job_id = orchestrator.submit_job({
        "description": "Security audit",
        "tasks": [{"prompt": "...", "estimated_tokens": 2000}]
    })
    assert job_id.startswith("api_")
```

### Integration Tests
```python
# tests/integration/test_batch_end_to_end.py

def test_intelligent_orchestrator_to_api():
    """Test that orchestrator jobs reach API queue."""
    orchestrator = IntelligentBatchOrchestrator()

    # Generate jobs
    queue = orchestrator.fill_overnight_queue(max_jobs=1)

    # Submit via new system
    batch_orch = BatchOrchestrator()
    job_id = batch_orch.submit_job(queue[0].to_dict())

    # Verify in API queue (not ProcessMonitor queue)
    assert job_id.startswith("api_")

    # Check remediation_queue.json
    queue_file = Path.home() / ".cortex" / "batches" / "remediation_queue.json"
    with open(queue_file) as f:
        data = json.load(f)

    assert len(data["priority_jobs"]) > 0

def test_local_command_to_process_monitor():
    """Test that local commands reach ProcessMonitor."""
    orchestrator = BatchOrchestrator()

    job_id = orchestrator.submit_job({
        "command": "echo 'test'",
        "description": "Test command",
        "task_type": "test"
    })

    assert job_id.startswith("local_")

    # Check in ProcessMonitor queue
    from intelligence.process_monitor import ProcessMonitor
    monitor = ProcessMonitor()
    task = monitor.batch_queue.get_task(job_id.replace("local_", ""))
    assert task is not None
```

---

## Success Metrics

### Immediate (Week 1)
- ✅ intelligent_orchestrator jobs reach API queue
- ✅ queue_manager processes overnight jobs
- ✅ No jobs in wrong queue (0 failed ProcessMonitor API jobs)
- ✅ Overnight capacity utilization > 30%

### Short-term (Week 2-4)
- ✅ All batch submissions use unified interface
- ✅ 90%+ correct routing (local vs API)
- ✅ Zero manual intervention for overnight batches
- ✅ Cost savings visible (50% on overnight API work)

### Long-term (Month 2+)
- ✅ Unified monitoring dashboard
- ✅ Cross-system dependency support (API job → local job)
- ✅ Automatic job type detection 99%+ accurate
- ✅ Full integration with Cortex intelligence layer

---

## Open Questions

1. **Job ID Format:** Use prefixes (local_*, api_*) or namespace (local:123, api:456)?
   - **Decision:** Prefixes - simpler parsing, no escaping needed

2. **Cross-System Dependencies:** Should API job be able to depend on local job?
   - **Decision:** Phase 2 feature - not MVP

3. **Migration of Existing Jobs:** What happens to jobs currently in ProcessMonitor queue?
   - **Decision:** Leave them - they'll complete or fail naturally

4. **Daemon Coordination:** Should orchestrator start queue_manager if not running?
   - **Decision:** No - keep separation, but add warning if daemon down

5. **Status Polling:** How to efficiently poll both systems?
   - **Decision:** Cache with 30s TTL, unified status endpoint

---

## Implementation Checklist

### Phase 1: Core Orchestrator
- [ ] Create `batch/orchestrator.py`
- [ ] Define BaseJob, LocalJob, APIJob dataclasses
- [ ] Implement `detect_job_type()` logic
- [ ] Implement `submit_job()` with routing
- [ ] Implement `get_status()` cross-system lookup
- [ ] Implement `list_jobs()` unified view
- [ ] Add unit tests (>90% coverage)

### Phase 2: CLI Integration
- [ ] Add `cmd_batch_submit()` to cli.py
- [ ] Add `cmd_batch_list()` with backend filter
- [ ] Add `cmd_batch_status()` unified status
- [ ] Update help text
- [ ] Add CLI integration tests

### Phase 3: Fix intelligent_orchestrator
- [ ] Update `submit_batch_queue()` to use BatchOrchestrator
- [ ] Remove subprocess CLI calls
- [ ] Add error handling
- [ ] Test with dry-run
- [ ] Test with actual submission
- [ ] Verify jobs reach remediation_queue.json

### Phase 4: Documentation
- [ ] Update QUICK_START.md
- [ ] Create batch_jobs_guide.md
- [ ] Add examples directory with job templates
- [ ] Update README with new commands
- [ ] Add architecture diagram

### Phase 5: Validation
- [ ] Run end-to-end test
- [ ] Submit 1 local job, verify in ProcessMonitor
- [ ] Submit 1 API job, verify in remediation_queue
- [ ] Run intelligent_orchestrator, verify API submission
- [ ] Confirm queue_manager picks up jobs
- [ ] Monitor overnight batch processing

---

## Risk Mitigation

### Risk 1: Breaking Existing Workflows
**Mitigation:**
- Keep all existing CLI commands working
- Add deprecation warnings, don't remove
- Gradual migration over 2-4 weeks

### Risk 2: Job Routing Errors
**Mitigation:**
- Conservative detection logic (err on side of local)
- Add `--force-backend local|api` override flag
- Log all routing decisions for debugging
- Add routing metrics to monitoring

### Risk 3: Queue Manager Daemon Crash
**Mitigation:**
- Add health check to orchestrator
- Warn user if daemon not running when submitting API job
- Document daemon startup in QUICK_START
- Add systemd/launchd config for auto-restart

### Risk 4: Performance Impact
**Mitigation:**
- Cache backend lookups (30s TTL)
- Async status checking for list operations
- Limit default list to 50 jobs
- Add pagination for large lists

---

## Design Complete

**Next Steps:**
1. Review design with user
2. Get approval for approach
3. Implement Phase 1 (orchestrator core)
4. Test with dry-runs
5. Roll out gradually

**Timeline Estimate:**
- Phase 1: 2-3 hours (core implementation)
- Phase 2: 1 hour (CLI integration)
- Phase 3: 30 minutes (fix orchestrator)
- Phase 4: 1 hour (documentation)
- Phase 5: 1 hour (validation)

**Total:** ~6 hours for full implementation and validation
