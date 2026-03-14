# Autoresearch Discovery Brief

date: 2026-03-14 | source: manual research | priority: high

## Autonomous Experiment Loop Patterns

**Karpathy autoresearch — Autonomous ML Experiment Agent**

Source: [github.com/karpathy/autoresearch](https://github.com/karpathy/autoresearch)

What: 630-line Python tool enabling AI agents to autonomously run ML experiments on a single GPU. Agent reads program.md (human directives), modifies train.py, trains for 5 min, evaluates val_bpb metric, keeps/discards, repeats. ~12 experiments/hour, ~100 overnight.
Impact: Reference architecture for Cortex CRA Phase 3. The program.md pattern directly maps to research_directives.md. Single scalar metric constraint validated — agent independently rediscovered RMSNorm and tied embeddings in 17 hours.
Action: Adopted. research_directives.md created, adoption_outcome_score implemented, experiment loop runner wired.

**autoresearch-macos — Apple Silicon Fork**

Source: [github.com/miolini/autoresearch-macos](https://github.com/miolini/autoresearch-macos)

What: Community fork extending autoresearch to Apple Silicon via MPS backend. Enables experiment loops on M-series Macs without NVIDIA GPU requirement.
Impact: Relevant for Cortex development environment (macOS). If CRA experiment loop needs to run GPU-accelerated tests locally, this pattern shows how to adapt.
Action: Monitor. Not directly applicable until CRA needs local GPU workloads.

**autoresearch-mlx — MLX Framework Fork**

Source: [github.com/trevin-creator/autoresearch-mlx](https://github.com/trevin-creator/autoresearch-mlx)

What: Fork using Apple's MLX framework instead of PyTorch. Demonstrates that the autoresearch pattern is framework-agnostic — the experiment loop is the innovation, not the training backend.
Impact: Validates that the program.md → agent → evaluate → keep/discard pattern generalizes beyond PyTorch ML training to any measurable optimization task.
Action: Monitor. Confirms our adaptation to CRA (non-ML domain) is architecturally sound.

## Agent Memory Experiment Patterns

**RetroAgent — Dual Intrinsic Feedback**

Source: [arxiv.org/abs/2603.08561](https://arxiv.org/abs/2603.08561)

What: Agent architecture using dual intrinsic feedback (success/failure signals) without external reward. Self-evaluating experiment loop similar to autoresearch but for agent task completion rather than ML training.
Impact: Could enhance CRA's adoption_outcome_score with intrinsic feedback signals beyond test pass rate — e.g., measuring whether the agent's code changes reduced complexity or improved readability.
Action: Assess for Phase 3. Complementary to autoresearch pattern.

**EverMemOS — Memory Operating System**

Source: [research reference — no public repo yet]

What: Memory operating system for structured long-horizon reasoning. Architecturally close to Cortex — assess for convergent design patterns.
Impact: If EverMemOS publishes code, compare their memory admission/retrieval against Cortex's approach. Convergent evolution validates our architecture.
Action: Monitor. Track for public release.
