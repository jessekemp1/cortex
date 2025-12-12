# GOLDEN SPEC: Cortex-Bridge-Upgrade

**Date**: 2025-12-10
**Status**: Draft
**Intent**: Upgrade Cortex-Orchestrator Bridge to provision functional Agent Teams

---

## 1. Deep Understanding (The "Why")

**Core Problem**: The current `cortex-orchestrator` bridge is "dumb". It can only schedule pre-existing Python functions found in the code. It cannot "spin up" a new research team on demand without a human writing code, restarting the server, and registering it. This blocks the "Zero-Loss Intent Transfer" goal.

### Context & Background
- **Current State**: `local-orchestrator` has no API for dynamic agent registration. Agents are hardcoded.
- **Constraints**: The system is active/live. We cannot risk destabilizing the core loop.

## 2. Outcome Definition (The "What")

**Target Outcome**: Cortex can "provision" a new Agent Team (e.g., "Research Windfield") by simply sending a configuration or file, without restarting the Orchestrator or writing manual Python code.

### Success Metrics
- [ ] **Provision Time**: < 5 seconds from Intent to "Pending Execution".
- [ ] **Zero Downtime**: Core Orchestrator does not need a full restart (or restarts are sub-second/safe).
- [ ] **Team Capability**: Can spawn at least 2 cooperating agents (e.g., Researcher + Writer) from one intent.

## 3. Outcome Validation (The "Check")

- [x] Is this the right problem? Yes, static agents are the bottleneck to "Symbiosis".
- [x] Is it feasible? Yes, using a "Hot-Loader" or "Dynamic Plugin" pattern.

## 4. Solution Design (The "How")

**Proposed Solution**: **The Dynamic Agent Loader (Plugin Pattern)**

### Architecture

1.  **The Drop Zone**:
    - Create `local-orchestrator/agents/dynamic/*.yaml` (or `.py`).
    - This folder is watched by the Orchestrator.

2.  **The Watcher (in Orchestrator)**:
    - Modify `orchestrator.py` *once* to scan `agents/dynamic/` on startup (and optionally periodically).
    - It uses a `DynamicAgentFactory` to convert YAML configs into executable `ScheduledTaskAgent` instances.

3.  **The Provisioner (in Cortex)**:
    - `cortex schedule --team` generates a YAML definition:
      ```yaml
      id: team_research_windfield
      type: research_team
      goal: "Analyze Windfield data schema"
      schedule: "0 8 * * *"
      context: [...]
      ```
    - Writes this file to the Drop Zone.

4.  **Dry-Run Safety**:
    - `cortex schedule --dry-run` writes to `agents/dynamic/staging/` to validate schema without loading it.

## 5. Solution-Outcome Alignment

- **Provision Time**: Writing a YAML file is instant.
- **Zero Downtime**: If the Orchestrator supports hot-reloading (future) or just robust startup scanning, we are good. For now, a "graceful reload" signal might be needed.
- **Side Effects**: Malformed YAML could crash the loader. **Mitigation**: The Loader must wrap importing in a strict try/catch block.

## 6. Implementation Planning (The "When")

### Tasks
- [ ] Create `local-orchestrator/agents/dynamic/` directory.
- [ ] Implement `DynamicAgentLoader` in `local-orchestrator`.
- [ ] Update `cortex` to generate Agent YAMLs.
- [ ] Test the loop: Intent -> YAML -> Agent Execution.

### Resources
- Required: Access to `local-orchestrator` file system (Have it).

## 7. Success Verification (The "Proof")

- [ ] **Test**: Run `cortex schedule "Research Flux Capacitor" --team`.
- [ ] **Verify**: Check `agents/dynamic/` for the new file.
- [ ] **Verify**: Monitor `local-orchestrator` logs to see it pick up the new agent.
