"""
Seed Patterns — Pre-loaded anti-patterns that ship with Cortex.

These provide immediate value on fresh install. Every pattern here:
1. Is detectable from local signals only (git, files, test output)
2. Has high cost when it occurs (hours lost, bugs caused, data lost)
3. Is universal across languages and frameworks
4. Has been validated across 6+ real projects over 18 months

Patterns are organized by category and include:
- detection_signals: what observable event triggers detection
- intervention: what Cortex surfaces when the pattern is detected
- confidence: how reliably this can be detected (0.0-1.0)

Users' own learned patterns take priority over seeds. Seeds decay
in relevance as project-specific patterns accumulate.
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class SeedAntiPattern:
    """A pre-loaded anti-pattern for cold-start intelligence."""

    id: str
    name: str
    category: str
    description: str
    detection_signals: List[str]
    intervention: str
    cost: str  # What happens if ignored
    confidence: float = 0.8
    keywords: List[str] = field(default_factory=list)


# ──────────────────────────────────────────────────────────────────
# Category 1: Git / Version Control
# ──────────────────────────────────────────────────────────────────

GIT_PATTERNS = [
    SeedAntiPattern(
        id="seed:git:secret-in-commit",
        name="Secret committed to git",
        category="git",
        description="API keys, passwords, or tokens committed to version control.",
        detection_signals=[
            "git diff contains API_KEY=, SECRET=, PASSWORD=, TOKEN=, or aws_secret",
            "File named .env, credentials.json, or *secret* staged for commit",
        ],
        intervention=(
            "STOP — Detected what looks like a secret in staged changes. "
            "Secrets in git history are extremely hard to remove and may be "
            "scraped by bots within minutes of pushing. Remove the secret, "
            "add the file to .gitignore, and rotate the credential."
        ),
        cost="Credential exposure. Bots scan public repos for secrets within minutes of push.",
        confidence=0.95,
        keywords=["secret", "credential", "api_key", "password", "token", "env"],
    ),
    SeedAntiPattern(
        id="seed:git:force-push-main",
        name="Force push to main/master",
        category="git",
        description="Force pushing to the default branch rewrites shared history.",
        detection_signals=[
            "git command contains 'push --force' or 'push -f' targeting main/master",
            "git reflog shows rewritten commits on default branch",
        ],
        intervention=(
            "Force pushing to the default branch rewrites history for everyone. "
            "If you need to undo, use 'git revert' instead. "
            "If you must force push, use '--force-with-lease' on a feature branch."
        ),
        cost="Team members lose work. CI/CD pipelines break. Hard to recover.",
        confidence=0.95,
        keywords=["force", "push", "main", "master", "rewrite", "history"],
    ),
    SeedAntiPattern(
        id="seed:git:large-binary",
        name="Large binary committed",
        category="git",
        description="Binary files (images, models, data) bloat the repo permanently.",
        detection_signals=[
            "Staged file > 5MB with binary extension (.pkl, .h5, .parquet, .zip, .tar)",
            "git diff --stat shows large file additions",
        ],
        intervention=(
            "Large binary file detected in staging. Binary files bloat git history "
            "permanently — even deleting them later doesn't reclaim space. "
            "Consider: Git LFS, a .gitignore entry, or storing in data/ outside the repo."
        ),
        cost="Repo size bloats permanently. Clone times increase for everyone.",
        confidence=0.85,
        keywords=["binary", "large", "file", "model", "data", "lfs"],
    ),
    SeedAntiPattern(
        id="seed:git:merge-conflict-markers",
        name="Merge conflict markers committed",
        category="git",
        description="<<<<<<< HEAD markers left in source files and committed.",
        detection_signals=[
            "Staged files contain '<<<<<<< ' or '=======' or '>>>>>>> '",
        ],
        intervention=(
            "Merge conflict markers detected in staged files. "
            "These will cause syntax errors or runtime failures. "
            "Resolve all conflicts before committing."
        ),
        cost="Broken code ships. Syntax errors in production.",
        confidence=0.99,
        keywords=["merge", "conflict", "markers", "head"],
    ),
    SeedAntiPattern(
        id="seed:git:build-artifacts",
        name="Build artifacts committed",
        category="git",
        description="Generated files (node_modules, __pycache__, dist, build) staged for commit.",
        detection_signals=[
            "Staged files match node_modules/, __pycache__/, dist/, build/, *.pyc, *.min.js",
            "Generated or compiled files in git staging area",
        ],
        intervention=(
            "Build artifacts detected in staging. These bloat the repo, cause merge "
            "conflicts, and should be regenerated from source. "
            "Add to .gitignore. If already tracked, use 'git rm --cached'."
        ),
        cost="Repo bloat. Merge conflicts on generated files. Slow clones.",
        confidence=0.95,
        keywords=["node_modules", "pycache", "dist", "build", "artifact", "generated"],
    ),
    SeedAntiPattern(
        id="seed:git:uncommitted-before-destructive",
        name="Uncommitted changes before destructive operation",
        category="git",
        description="Running git checkout, reset, or rebase with uncommitted changes.",
        detection_signals=[
            "git status shows uncommitted changes AND destructive command about to run",
            "Unstaged work present before checkout, reset, clean, or rebase",
        ],
        intervention=(
            "You have uncommitted changes. Running this command will discard them "
            "permanently — there's no reflog recovery for unstaged work. "
            "Commit or stash your changes first."
        ),
        cost="Hours of work lost permanently. No recovery possible for unstaged changes.",
        confidence=0.95,
        keywords=["uncommitted", "checkout", "reset", "clean", "rebase", "stash"],
    ),
    SeedAntiPattern(
        id="seed:git:uncommitted-migration",
        name="Schema change without migration",
        category="git",
        description="Database model changed but no migration file created.",
        detection_signals=[
            "Modified files include models.py, schema.py, or *.model.ts but no migration file",
            "ORM model fields changed without corresponding migration in migrations/",
        ],
        intervention=(
            "Schema change detected without a migration file. "
            "This works locally but will break any other environment (staging, production, "
            "teammates) that doesn't have your local database state. "
            "Create a migration file alongside the schema change."
        ),
        cost="Staging/production breaks. Silent data loss. Hours debugging 'works on my machine'.",
        confidence=0.80,
        keywords=["schema", "migration", "database", "model", "orm"],
    ),
]

# ──────────────────────────────────────────────────────────────────
# Category 2: Testing
# ──────────────────────────────────────────────────────────────────

TESTING_PATTERNS = [
    SeedAntiPattern(
        id="seed:test:deploy-without-tests",
        name="Deploy without running tests",
        category="testing",
        description="Pushing or deploying code without verifying tests pass.",
        detection_signals=[
            "git push without a recent test run in session history",
            "Deploy command invoked but no pytest/jest/cargo test in recent commands",
        ],
        intervention=(
            "About to push/deploy without running tests first. "
            "Run your test suite before deploying — catching failures locally "
            "is minutes, catching them in production is hours."
        ),
        cost="Broken deploys. Production incidents. Rollback time.",
        confidence=0.70,
        keywords=["deploy", "push", "test", "ci", "pipeline"],
    ),
    SeedAntiPattern(
        id="seed:test:permissive-assertion",
        name="Permissive test assertion",
        category="testing",
        description="Assertions that pass for both success and failure states.",
        detection_signals=[
            "Test contains 'assert status_code in [200, 500]' or similar mixed assertions",
            "Test assertion uses 'is not None' when a specific value is expected",
        ],
        intervention=(
            "This assertion would pass even if the code is broken. "
            "Use specific assertions: assert status_code == 200, not 'in [200, 500]'. "
            "A test that can't fail isn't testing anything."
        ),
        cost="False confidence. Bugs slip through test suite undetected.",
        confidence=0.85,
        keywords=["test", "assert", "permissive", "status", "validation"],
    ),
    SeedAntiPattern(
        id="seed:test:test-implementation",
        name="Testing implementation instead of behavior",
        category="testing",
        description="Tests that break when code is refactored even though behavior is unchanged.",
        detection_signals=[
            "Test mocks 5+ internal methods or patches internal implementation details",
            "Test asserts on internal state rather than external output",
        ],
        intervention=(
            "This test is tightly coupled to implementation. "
            "It will break on refactor even if behavior is correct. "
            "Test inputs and outputs, not internal method calls."
        ),
        cost="Tests become a refactoring tax. Developers skip tests to move faster.",
        confidence=0.65,
        keywords=["mock", "patch", "implementation", "refactor", "coupling"],
    ),
    SeedAntiPattern(
        id="seed:test:no-assertions",
        name="Test with no assertions",
        category="testing",
        description="Test function has no assert, expect, or verify statement.",
        detection_signals=[
            "def test_* function body contains no assert keyword",
            "Test function always passes regardless of code behavior",
        ],
        intervention=(
            "This test has no assertions — it will always pass. "
            "A test that can't fail provides zero value. "
            "Add specific assertions about expected behavior."
        ),
        cost="False coverage. Zero protection against regressions.",
        confidence=0.95,
        keywords=["test", "assert", "assertion", "empty", "coverage"],
    ),
    SeedAntiPattern(
        id="seed:test:ignored-failure",
        name="Test failure ignored",
        category="testing",
        description="Failing tests present but work continues without fixing them.",
        detection_signals=[
            "pytest output shows failures but next command is not a fix attempt",
            "Test file has @pytest.mark.skip or @pytest.mark.xfail on previously-passing test",
        ],
        intervention=(
            "Test failures detected but not addressed. "
            "Skipping failing tests erodes the test suite's value over time. "
            "Fix the failure now, or mark it with @xfail and a ticket reference."
        ),
        cost="Test suite becomes unreliable. Team stops trusting test results.",
        confidence=0.75,
        keywords=["test", "fail", "skip", "xfail", "ignore", "broken"],
    ),
]

# ──────────────────────────────────────────────────────────────────
# Category 3: Deployment & Configuration
# ──────────────────────────────────────────────────────────────────

DEPLOY_PATTERNS = [
    SeedAntiPattern(
        id="seed:deploy:env-var-missing",
        name="Missing environment variable",
        category="deployment",
        description="New env var added to code but not to deployment config.",
        detection_signals=[
            "Code references os.environ['NEW_VAR'] or process.env.NEW_VAR",
            "Variable not found in .env.example, docker-compose.yml, or CI config",
        ],
        intervention=(
            "New environment variable referenced in code but not in deployment config. "
            "This will cause a runtime crash in staging/production. "
            "Add it to .env.example and your deployment configuration."
        ),
        cost="Runtime crash on deploy. Silent misconfiguration.",
        confidence=0.80,
        keywords=["env", "environment", "variable", "config", "deploy"],
    ),
    SeedAntiPattern(
        id="seed:deploy:config-drift",
        name="Config drift between environments",
        category="deployment",
        description="Local config diverges from staging/production.",
        detection_signals=[
            ".env has variables not in .env.example or .env.template",
            "Docker/K8s config differs between environments",
        ],
        intervention=(
            "Local environment has configuration not reflected in deployment templates. "
            "This causes 'works on my machine' failures. "
            "Keep .env.example in sync with actual required variables."
        ),
        cost="Deployment failures. 'Works on my machine' debugging cycles.",
        confidence=0.70,
        keywords=["config", "drift", "environment", "deploy", "staging"],
    ),
    SeedAntiPattern(
        id="seed:deploy:hardcoded-url",
        name="Hardcoded URL or endpoint",
        category="deployment",
        description="URLs or API endpoints hardcoded instead of configured.",
        detection_signals=[
            "Source code contains 'http://localhost:' or 'https://api.production.' literals",
            "URLs in source files that should come from environment config",
        ],
        intervention=(
            "Hardcoded URL detected. This will break in other environments. "
            "Move to environment variable or configuration file."
        ),
        cost="Breaks on deploy. Security risk if production URLs exposed.",
        confidence=0.75,
        keywords=["url", "endpoint", "hardcode", "localhost", "production"],
    ),
]

# ──────────────────────────────────────────────────────────────────
# Category 4: Dependencies
# ──────────────────────────────────────────────────────────────────

DEPENDENCY_PATTERNS = [
    SeedAntiPattern(
        id="seed:deps:lock-drift",
        name="Lock file out of sync",
        category="dependencies",
        description="Package manifest changed but lock file not regenerated.",
        detection_signals=[
            "requirements.txt or package.json modified but lock file unchanged",
            "pip install or npm install output shows version resolution",
        ],
        intervention=(
            "Package manifest changed but lock file not updated. "
            "This causes version drift between environments. "
            "Run 'pip freeze > requirements.txt' or 'npm install' to sync the lock file."
        ),
        cost="Version mismatch between environments. 'Works on my machine' failures.",
        confidence=0.80,
        keywords=["lock", "package", "dependency", "version", "sync", "npm", "pip"],
    ),
    SeedAntiPattern(
        id="seed:deps:version-conflict",
        name="Dependency version conflict",
        category="dependencies",
        description="Incompatible dependency versions introduced.",
        detection_signals=[
            "pip install or npm install output shows version conflict warnings",
            "Multiple versions of same package required",
        ],
        intervention=(
            "Dependency conflict detected. This causes unpredictable behavior — "
            "the wrong version may load at runtime. "
            "Resolve the conflict before continuing."
        ),
        cost="Silent bugs from wrong dependency version. Hard to reproduce.",
        confidence=0.75,
        keywords=["dependency", "conflict", "version", "incompatible"],
    ),
]

# ──────────────────────────────────────────────────────────────────
# Category 5: Security
# ──────────────────────────────────────────────────────────────────

SECURITY_PATTERNS = [
    SeedAntiPattern(
        id="seed:security:sql-injection",
        name="SQL injection risk",
        category="security",
        description="User input concatenated directly into SQL query.",
        detection_signals=[
            "f-string or .format() used with SQL query containing user input",
            "String concatenation with 'SELECT', 'INSERT', 'UPDATE', 'DELETE'",
        ],
        intervention=(
            "Possible SQL injection: user input is being concatenated into a query. "
            "Use parameterized queries instead. "
            "f\"SELECT * FROM users WHERE id = {user_id}\" → cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))"
        ),
        cost="Data breach. Full database compromise. OWASP Top 10 vulnerability.",
        confidence=0.85,
        keywords=["sql", "injection", "query", "database", "security"],
    ),
    SeedAntiPattern(
        id="seed:security:debug-in-production",
        name="Debug mode in production config",
        category="security",
        description="Debug mode or verbose logging enabled in production configuration.",
        detection_signals=[
            "DEBUG = True or debug=True in production config files",
            "Verbose logging level (DEBUG) set in deployment config",
        ],
        intervention=(
            "Debug mode detected in production configuration. "
            "This exposes stack traces, internal paths, and potentially secrets. "
            "Set DEBUG = False and use WARNING or ERROR log level for production."
        ),
        cost="Information disclosure. Stack traces visible to attackers.",
        confidence=0.85,
        keywords=["debug", "production", "security", "logging", "verbose"],
    ),
]

# ──────────────────────────────────────────────────────────────────
# Category 6: AI Agent-Specific
# ──────────────────────────────────────────────────────────────────

AGENT_PATTERNS = [
    SeedAntiPattern(
        id="seed:agent:blind-edit",
        name="Editing a file without reading it first",
        category="agent",
        description="Agent writes or edits a file it hasn't read in the current session.",
        detection_signals=[
            "File written/edited but never read in session history",
            "Agent makes assumptions about file content without verification",
        ],
        intervention=(
            "You haven't read this file yet. Read it first to understand "
            "the current state before editing — blind edits overwrite "
            "existing code you don't know about."
        ),
        cost="Existing code overwritten. Functions deleted. Imports lost.",
        confidence=0.95,
        keywords=["edit", "write", "read", "blind", "overwrite", "file"],
    ),
    SeedAntiPattern(
        id="seed:agent:infinite-fix-loop",
        name="Same test failing after 3+ fix attempts",
        category="agent",
        description="Agent keeps modifying code to fix a test without understanding root cause.",
        detection_signals=[
            "Same test failed 3+ times in session with different fixes each time",
            "Agent cycling through modifications without resolving the failure",
        ],
        intervention=(
            "This test has failed 3 times with different fixes. Stop and investigate "
            "the root cause — read the test, check fixtures, verify the environment. "
            "Cycling through fixes without understanding the problem wastes time."
        ),
        cost="Wasted tokens and time. Root cause ignored. Code gets worse with each attempt.",
        confidence=0.90,
        keywords=["test", "fail", "loop", "retry", "fix", "cycle"],
    ),
    SeedAntiPattern(
        id="seed:agent:premature-cleanup-claim",
        name="Cleanup declared complete without verification",
        category="agent",
        description="Agent claims 'all instances fixed' without grep verification.",
        detection_signals=[
            "Agent states cleanup/migration complete but pattern still found in codebase",
            "'All fixed' or 'cleanup complete' without running grep to verify",
        ],
        intervention=(
            "Before declaring cleanup complete, verify with grep: "
            "search the entire codebase for remaining instances. "
            "Directly observed: '134 paths fixed' declared while 40+ remained."
        ),
        cost="Incomplete migrations. False confidence. Bugs from unfixed instances.",
        confidence=0.95,
        keywords=["cleanup", "complete", "fixed", "grep", "verify", "remaining"],
    ),
    SeedAntiPattern(
        id="seed:agent:circular-import",
        name="Circular import introduced",
        category="agent",
        description="AI agent introduces imports that create circular dependency.",
        detection_signals=[
            "ImportError: cannot import name 'X' from partially initialized module",
            "New import added at module level between two files that already import each other",
        ],
        intervention=(
            "Circular import risk: these modules already reference each other. "
            "Move the import inside the function that uses it, "
            "or extract the shared dependency into a third module."
        ),
        cost="ImportError at runtime. Breaks entire module.",
        confidence=0.80,
        keywords=["import", "circular", "dependency", "module"],
    ),
    SeedAntiPattern(
        id="seed:agent:reintroduce-bug",
        name="Previously fixed bug reintroduced",
        category="agent",
        description="Agent modifies code that was specifically fixed in a recent commit.",
        detection_signals=[
            "Current diff modifies lines that were changed in a recent 'fix:' commit",
            "File being edited has a recent fix commit touching the same function",
        ],
        intervention=(
            "This code was specifically fixed in a recent commit. "
            "The current change may reintroduce the bug. "
            "Review the fix commit to understand why this code was changed."
        ),
        cost="Regression. Bug that was already fixed returns.",
        confidence=0.70,
        keywords=["regression", "fix", "bug", "reintroduce", "revert"],
    ),
    SeedAntiPattern(
        id="seed:agent:over-refactor",
        name="Unnecessary refactoring",
        category="agent",
        description="AI agent refactors working code that wasn't part of the task.",
        detection_signals=[
            "Diff touches 5+ files but task description mentions only 1-2",
            "Rename/restructure changes in files unrelated to the current task",
        ],
        intervention=(
            "Changes detected in files not related to the current task. "
            "Unnecessary refactoring risks introducing bugs in working code. "
            "Keep changes focused on the task at hand."
        ),
        cost="Unnecessary risk. Bugs in working code. Harder to review.",
        confidence=0.60,
        keywords=["refactor", "rename", "restructure", "scope", "creep"],
    ),
    SeedAntiPattern(
        id="seed:agent:ignore-conventions",
        name="Project conventions ignored",
        category="agent",
        description="Agent generates code that doesn't match project style.",
        detection_signals=[
            "New code uses different naming convention than existing codebase",
            "New file structure doesn't match established project layout",
            "Linter reports style violations in generated code",
        ],
        intervention=(
            "Generated code doesn't match project conventions. "
            "Check existing code for naming patterns, file structure, "
            "and style before generating new code."
        ),
        cost="Inconsistent codebase. Maintenance burden. Code review friction.",
        confidence=0.65,
        keywords=["convention", "style", "naming", "linter", "format"],
    ),
    SeedAntiPattern(
        id="seed:agent:context-loss",
        name="Context from previous session lost",
        category="agent",
        description="Agent repeats work or asks questions answered in a previous session.",
        detection_signals=[
            "Query matches a question answered in episodic memory",
            "Task description matches recently completed work",
        ],
        intervention=(
            "This was addressed in a previous session. "
            "Here's what was decided and why — no need to re-investigate."
        ),
        cost="Duplicated work. Wasted time re-explaining.",
        confidence=0.75,
        keywords=["context", "session", "previous", "repeat", "duplicate"],
    ),
]

# ──────────────────────────────────────────────────────────────────
# Category 7: Code Quality
# ──────────────────────────────────────────────────────────────────

QUALITY_PATTERNS = [
    SeedAntiPattern(
        id="seed:quality:dead-code",
        name="Dead code accumulation",
        category="quality",
        description="Unused imports, functions, or variables left in codebase.",
        detection_signals=[
            "Linter reports unused imports or variables",
            "Functions not called anywhere in the codebase",
        ],
        intervention=(
            "Dead code detected. Remove unused imports, functions, and variables. "
            "Dead code misleads future developers and increases maintenance burden."
        ),
        cost="Confusion for future developers. Misleading code navigation.",
        confidence=0.70,
        keywords=["unused", "dead", "import", "function", "variable"],
    ),
    SeedAntiPattern(
        id="seed:quality:premature-abstraction",
        name="Premature abstraction",
        category="quality",
        description="Creating base classes, factories, or abstractions for single-use code.",
        detection_signals=[
            "New abstract base class or interface with only one implementation",
            "Factory pattern created for a single type",
            "Generic/template code with only one instantiation",
        ],
        intervention=(
            "This abstraction has only one implementation. "
            "Wait until you have 2-3 concrete cases before abstracting. "
            "Three similar lines of code is better than a premature abstraction."
        ),
        cost="Complexity without benefit. Harder to understand and modify.",
        confidence=0.60,
        keywords=["abstract", "factory", "generic", "interface", "base"],
    ),
    SeedAntiPattern(
        id="seed:quality:error-swallowing",
        name="Error silently swallowed",
        category="quality",
        description="Exceptions caught with bare except or empty except block.",
        detection_signals=[
            "'except:' or 'except Exception:' with 'pass' as the only body",
            "try/catch with empty catch block",
        ],
        intervention=(
            "Exception is being silently swallowed. This hides bugs. "
            "At minimum, log the error. Better: handle it specifically or let it propagate."
        ),
        cost="Silent failures. Bugs hidden for weeks until they cascade.",
        confidence=0.85,
        keywords=["exception", "error", "catch", "except", "pass", "swallow"],
    ),
]

# ──────────────────────────────────────────────────────────────────
# Category 8: Infrastructure
# ──────────────────────────────────────────────────────────────────

INFRA_PATTERNS = [
    SeedAntiPattern(
        id="seed:infra:port-conflict",
        name="Port already in use",
        category="infrastructure",
        description="Starting a service on a port already occupied by another process.",
        detection_signals=[
            "'Address already in use' error in server startup",
            "Multiple processes binding to the same port",
        ],
        intervention=(
            "Port conflict detected. Another process is already using this port. "
            "Kill the existing process or use a different port. "
            "Check with: lsof -i :PORT"
        ),
        cost="Service won't start. Confusion about which instance is running.",
        confidence=0.90,
        keywords=["port", "address", "bind", "conflict", "process"],
    ),
    SeedAntiPattern(
        id="seed:infra:dockerfile-layer-order",
        name="Dockerfile layer order inefficiency",
        category="infrastructure",
        description="Frequently-changing layers placed before stable layers in Dockerfile.",
        detection_signals=[
            "COPY . . appears before RUN pip install or RUN npm install",
            "Source code copied before dependencies installed in Dockerfile",
        ],
        intervention=(
            "Dockerfile copies source code before installing dependencies. "
            "This invalidates the dependency cache on every code change, "
            "causing slow rebuilds. Move COPY requirements.txt + RUN pip install "
            "BEFORE COPY . . to cache dependencies separately."
        ),
        cost="Docker builds 10-50x slower. CI/CD pipelines waste minutes per build.",
        confidence=0.85,
        keywords=["docker", "dockerfile", "layer", "cache", "build", "copy"],
    ),
    SeedAntiPattern(
        id="seed:infra:stale-cache",
        name="Stale cache causing incorrect behavior",
        category="infrastructure",
        description="Build cache, compiled files, or cached data serving outdated results.",
        detection_signals=[
            "Code changes don't take effect until cache cleared",
            "__pycache__, .next, node_modules/.cache, .pytest_cache causing issues",
        ],
        intervention=(
            "If recent changes aren't taking effect, clear the relevant cache. "
            "Common caches: __pycache__, .next/, node_modules/.cache, "
            ".pytest_cache, .mypy_cache, build/"
        ),
        cost="Debugging correct code. Changes appear not to work.",
        confidence=0.65,
        keywords=["cache", "stale", "build", "compile", "pycache"],
    ),
]

# ──────────────────────────────────────────────────────────────────
# Category 9: Collaboration
# ──────────────────────────────────────────────────────────────────

COLLAB_PATTERNS = [
    SeedAntiPattern(
        id="seed:collab:breaking-change-undocumented",
        name="Breaking change without documentation",
        category="collaboration",
        description="API or interface changed without updating documentation or changelog.",
        detection_signals=[
            "Function signature changed (parameters added/removed/renamed)",
            "API endpoint modified but no changelog or migration guide",
        ],
        intervention=(
            "Breaking change detected: function signature or API interface modified. "
            "Update the changelog, add a migration note, or bump the version. "
            "Consumers of this interface will break silently."
        ),
        cost="Downstream consumers break. Silent failures in integrations.",
        confidence=0.70,
        keywords=["breaking", "change", "api", "interface", "documentation"],
    ),
    SeedAntiPattern(
        id="seed:collab:wip-pushed",
        name="Work-in-progress code pushed",
        category="collaboration",
        description="TODO, FIXME, HACK, or incomplete code pushed to shared branch.",
        detection_signals=[
            "Committed code contains TODO, FIXME, HACK, XXX, or TEMP comments",
            "Functions with 'pass' or 'raise NotImplementedError' in non-test code",
        ],
        intervention=(
            "Work-in-progress markers detected in code being pushed. "
            "Finish the implementation or mark with a tracking issue before pushing."
        ),
        cost="Incomplete code ships. Future developers confused by placeholders.",
        confidence=0.70,
        keywords=["todo", "fixme", "hack", "wip", "incomplete"],
    ),
]

# ──────────────────────────────────────────────────────────────────
# Category 10: Data Operations
# ──────────────────────────────────────────────────────────────────

DATA_PATTERNS = [
    SeedAntiPattern(
        id="seed:data:destructive-operation",
        name="Destructive data operation without backup",
        category="data",
        description="DROP TABLE, TRUNCATE, rm -rf, or similar without backup confirmation.",
        detection_signals=[
            "Command contains DROP TABLE, TRUNCATE, DELETE FROM without WHERE",
            "rm -rf on data directories",
            "Database migration with destructive operation",
        ],
        intervention=(
            "Destructive operation detected. This is irreversible. "
            "Verify you have a backup before proceeding. "
            "Consider: snapshot the data first, or use a soft-delete approach."
        ),
        cost="Data loss. Unrecoverable without backup.",
        confidence=0.90,
        keywords=["drop", "truncate", "delete", "rm", "destructive", "backup"],
    ),
    SeedAntiPattern(
        id="seed:data:no-validation",
        name="External data used without validation",
        category="data",
        description="User input or API response used directly without validation.",
        detection_signals=[
            "request.body or request.params used directly without schema validation",
            "API response fields accessed without null/type checking",
        ],
        intervention=(
            "External data used without validation. "
            "Always validate at system boundaries: check types, ranges, "
            "and required fields before using data from users or external APIs."
        ),
        cost="Runtime errors. Data corruption. Security vulnerabilities.",
        confidence=0.75,
        keywords=["validation", "input", "sanitize", "external", "boundary"],
    ),
]


# ──────────────────────────────────────────────────────────────────
# All seed patterns combined
# ──────────────────────────────────────────────────────────────────

ALL_SEED_PATTERNS: list[SeedAntiPattern] = (
    GIT_PATTERNS
    + TESTING_PATTERNS
    + DEPLOY_PATTERNS
    + DEPENDENCY_PATTERNS
    + SECURITY_PATTERNS
    + AGENT_PATTERNS
    + QUALITY_PATTERNS
    + INFRA_PATTERNS
    + COLLAB_PATTERNS
    + DATA_PATTERNS
)


def get_seed_patterns() -> list[SeedAntiPattern]:
    """Return all seed anti-patterns."""
    return ALL_SEED_PATTERNS


def get_seed_patterns_by_category(category: str) -> list[SeedAntiPattern]:
    """Return seed patterns for a specific category."""
    return [p for p in ALL_SEED_PATTERNS if p.category == category]


def get_categories() -> list[str]:
    """Return all seed pattern categories."""
    return sorted(set(p.category for p in ALL_SEED_PATTERNS))


def match_seed_patterns(
    context: str,
    keywords: list[str] | None = None,
    min_confidence: float = 0.5,
) -> list[SeedAntiPattern]:
    """
    Match seed patterns against a context string and optional keywords.

    Returns patterns sorted by confidence (highest first).
    """
    context_lower = context.lower()
    matches = []

    for pattern in ALL_SEED_PATTERNS:
        if pattern.confidence < min_confidence:
            continue

        # Check keyword overlap
        score = 0.0
        for kw in pattern.keywords:
            if kw in context_lower:
                score += 1.0

        if keywords:
            for kw in keywords:
                if kw.lower() in [k.lower() for k in pattern.keywords]:
                    score += 2.0  # Explicit keyword match weighted higher

        if score > 0:
            matches.append((pattern, score))

    # Sort by score * confidence
    matches.sort(key=lambda x: x[1] * x[0].confidence, reverse=True)
    return [m[0] for m in matches]
