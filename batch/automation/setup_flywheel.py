#!/usr/bin/env python3
"""
Flywheel Setup Script

Installs and configures the Development Flywheel automation:
1. Creates required directories
2. Installs launchd plists
3. Installs git hooks
4. Starts the flywheel daemon
5. Verifies installation

Usage:
    python setup_flywheel.py           # Full installation
    python setup_flywheel.py --check   # Verify installation
    python setup_flywheel.py --remove  # Uninstall
"""

import argparse
import os
import shutil
import subprocess
from pathlib import Path

# Paths
SCRIPT_DIR = Path(__file__).parent
CORTEX_DIR = SCRIPT_DIR.parent.parent
DEV_DIR = CORTEX_DIR.parent
LAUNCH_AGENTS_DIR = Path.home() / "Library" / "LaunchAgents"
GIT_HOOKS_DIR = DEV_DIR / ".git" / "hooks"
FLYWHEEL_STATE_DIR = Path.home() / ".cortex" / "flywheel"
BATCH_STATE_DIR = Path.home() / ".cortex" / "batch"
BUDGET_STATE_DIR = Path.home() / ".cortex" / "budget"

# Plist files to install
PLIST_FILES = [
    "com.cortex.flywheel.plist",
    "com.cortex.batch.nightly.plist",
    "com.cortex.batch.morning.plist",
]


def create_directories():
    """Create required state directories"""
    print("📁 Creating directories...")

    dirs = [
        FLYWHEEL_STATE_DIR,
        BATCH_STATE_DIR,
        BATCH_STATE_DIR / "results",
        BUDGET_STATE_DIR,
    ]

    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
        print(f"   ✓ {d}")


def install_launchd_plists():
    """Install launchd plist files"""
    print("\n🔧 Installing launchd agents...")

    LAUNCH_AGENTS_DIR.mkdir(parents=True, exist_ok=True)

    for plist_name in PLIST_FILES:
        src = SCRIPT_DIR / plist_name
        dst = LAUNCH_AGENTS_DIR / plist_name

        if not src.exists():
            print(f"   ⚠️  Missing: {plist_name}")
            continue

        # Copy file
        shutil.copy(src, dst)
        print(f"   ✓ Installed {plist_name}")

        # Load the agent
        subprocess.run(["launchctl", "unload", str(dst)], capture_output=True)
        result = subprocess.run(["launchctl", "load", str(dst)], capture_output=True, text=True)

        if result.returncode == 0:
            print(f"   ✓ Loaded {plist_name}")
        else:
            print(f"   ⚠️  Load failed: {result.stderr}")


def install_git_hooks():
    """Install git hooks for batch integration"""
    print("\n🪝 Installing git hooks...")

    if not GIT_HOOKS_DIR.exists():
        print("   ⚠️  Git hooks directory not found")
        return

    # Post-commit hook
    post_commit = GIT_HOOKS_DIR / "post-commit"

    hook_content = """#!/bin/bash
# Cortex Flywheel - Post-Commit Hook
# Suggests batch analysis for significant commits

# Count changes
CHANGES=$(git diff HEAD~1 --stat | tail -1)
FILES=$(echo "$CHANGES" | grep -oE '[0-9]+ file' | grep -oE '[0-9]+' || echo "0")
INSERTIONS=$(echo "$CHANGES" | grep -oE '[0-9]+ insertion' | grep -oE '[0-9]+' || echo "0")

# Trigger batch suggestion for large commits
if [ "$FILES" -gt 5 ] || [ "$INSERTIONS" -gt 500 ]; then
    echo ""
    echo "💡 Large commit detected ($FILES files, +$INSERTIONS lines)"
    echo "   Consider: /batch-submit review HEAD"
    echo ""
fi
"""

    # Check if hook exists and has our marker
    if post_commit.exists():
        existing = post_commit.read_text()
        if "Cortex Flywheel" in existing:
            print("   ✓ post-commit hook already installed")
        else:
            # Append to existing hook
            with open(post_commit, "a") as f:
                f.write("\n" + hook_content)
            print("   ✓ Updated post-commit hook")
    else:
        post_commit.write_text(hook_content)
        post_commit.chmod(0o755)
        print("   ✓ Created post-commit hook")


def verify_installation():
    """Verify flywheel installation"""
    print("\n🔍 Verifying installation...")

    checks = []

    # Check directories
    for d in [FLYWHEEL_STATE_DIR, BATCH_STATE_DIR, BUDGET_STATE_DIR]:
        if d.exists():
            checks.append((f"Directory: {d.name}", True))
        else:
            checks.append((f"Directory: {d.name}", False))

    # Check launchd agents
    for plist_name in PLIST_FILES:
        plist_path = LAUNCH_AGENTS_DIR / plist_name
        if plist_path.exists():
            # Check if loaded
            result = subprocess.run(["launchctl", "list"], capture_output=True, text=True)
            label = plist_name.replace(".plist", "")
            if label in result.stdout:
                checks.append((f"Agent: {label}", True))
            else:
                checks.append((f"Agent: {label} (not running)", False))
        else:
            checks.append((f"Agent: {plist_name}", False))

    # Check flywheel daemon
    pid_file = FLYWHEEL_STATE_DIR / "daemon.pid"
    if pid_file.exists():
        pid = pid_file.read_text().strip()
        try:
            os.kill(int(pid), 0)  # Check if process exists
            checks.append(("Flywheel daemon", True))
        except (ProcessLookupError, ValueError):
            checks.append(("Flywheel daemon (stale PID)", False))
    else:
        checks.append(("Flywheel daemon", False))

    # Print results
    all_ok = True
    for name, ok in checks:
        icon = "✅" if ok else "❌"
        print(f"   {icon} {name}")
        if not ok:
            all_ok = False

    return all_ok


def remove_installation():
    """Remove flywheel installation"""
    print("🗑️  Removing flywheel installation...")

    # Unload and remove launchd agents
    for plist_name in PLIST_FILES:
        plist_path = LAUNCH_AGENTS_DIR / plist_name
        if plist_path.exists():
            subprocess.run(["launchctl", "unload", str(plist_path)], capture_output=True)
            plist_path.unlink()
            print(f"   ✓ Removed {plist_name}")

    # Stop flywheel daemon
    pid_file = FLYWHEEL_STATE_DIR / "daemon.pid"
    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
            os.kill(pid, 15)  # SIGTERM
            print("   ✓ Stopped flywheel daemon")
        except Exception:
            pass
        pid_file.unlink(missing_ok=True)

    print("\n   Note: State directories preserved at ~/.cortex/")
    print("   To fully remove: rm -rf ~/.cortex/flywheel ~/.cortex/batch ~/.cortex/budget")


def print_post_install_info():
    """Print helpful post-installation information"""
    print("\n" + "=" * 60)
    print("✅ FLYWHEEL INSTALLATION COMPLETE")
    print("=" * 60)
    print()
    print("The Development Flywheel is now active!")
    print()
    print("📊 Monitor status:")
    print("   python cortex/batch/flywheel_daemon.py --status")
    print()
    print("🔧 Manual commands:")
    print("   /batch-orchestrate  - Queue overnight work")
    print("   /batch-status       - Check batch queue")
    print("   /briefing           - See overnight results")
    print()
    print("⏰ Automated schedule:")
    print("   • Flywheel daemon: Always running, checks every 5 min")
    print("   • Nightly orchestrator: 10 PM daily")
    print("   • Morning processor: 6 AM daily")
    print()
    print("📝 Logs:")
    print("   ~/.cortex/flywheel/daemon.log")
    print("   ~/.cortex/batch/nightly_stdout.log")
    print()


def main():
    parser = argparse.ArgumentParser(description="Setup Development Flywheel")
    parser.add_argument("--check", action="store_true", help="Verify installation only")
    parser.add_argument("--remove", action="store_true", help="Remove installation")

    args = parser.parse_args()

    print("╔══════════════════════════════════════════════════════╗")
    print("║        DEVELOPMENT FLYWHEEL SETUP                   ║")
    print("╚══════════════════════════════════════════════════════╝")
    print()

    if args.check:
        success = verify_installation()
        if success:
            print("\n✅ All checks passed!")
        else:
            print("\n⚠️  Some checks failed. Run without --check to install.")
        return

    if args.remove:
        remove_installation()
        print("\n✅ Removal complete!")
        return

    # Full installation
    create_directories()
    install_launchd_plists()
    install_git_hooks()

    # Verify
    print()
    success = verify_installation()

    if success:
        print_post_install_info()
    else:
        print("\n⚠️  Some components failed to install.")
        print("   Check the output above for details.")


if __name__ == "__main__":
    main()
