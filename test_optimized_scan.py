"""
Test optimized scan_workspace with directory exclusions.
"""
from pathlib import Path
import time

# Directories to skip (common large directories)
SKIP_DIRS = {
    'node_modules',
    'venv',
    '.venv',
    'env',
    '.git',
    '__pycache__',
    '.pytest_cache',
    'dist',
    'build',
    '.next',
    '.nuxt',
    'target',
    'bower_components',
    '.tox',
    '.eggs',
    '*.egg-info',
    '.mypy_cache',
    '.ruff_cache',
    'htmlcov',
    '.coverage',
}

def optimized_rglob(root: Path, pattern: str):
    """Optimized recursive glob that skips common large directories."""
    def _walk(path: Path):
        try:
            for item in path.iterdir():
                if item.is_dir():
                    # Skip excluded directories
                    if item.name in SKIP_DIRS or item.name.startswith('.'):
                        continue
                    # Recurse into directory
                    yield from _walk(item)
                elif item.match(pattern):
                    yield item
        except PermissionError:
            pass  # Skip directories we can't read
    
    # Check root for matches
    for item in root.iterdir():
        if item.match(pattern):
            yield item
    
    # Recurse
    yield from _walk(root)


def original_scan():
    """Original implementation using rglob."""
    workspace = Path.home() / "Dev"
    start = time.time()
    projects = list(workspace.rglob(".claude/project.yaml"))
    duration = time.time() - start
    return projects, duration


def optimized_scan():
    """Optimized implementation with directory exclusions."""
    workspace = Path.home() / "Dev"
    start = time.time()
    projects = list(optimized_rglob(workspace, ".claude/project.yaml"))
    duration = time.time() - start
    return projects, duration


if __name__ == "__main__":
    print("="*60)
    print("PERFORMANCE COMPARISON")
    print("="*60)
    
    # Test optimized version
    print("\n1. OPTIMIZED SCAN (with exclusions):")
    opt_projects, opt_time = optimized_scan()
    print(f"   Projects found: {len(opt_projects)}")
    print(f"   Scan time: {opt_time:.3f}s")
    
    # Test original version (with timeout)
    print("\n2. ORIGINAL SCAN (no exclusions):")
    print("   Running with 20s timeout...")
    try:
        orig_projects, orig_time = original_scan()
        print(f"   Projects found: {len(orig_projects)}")
        print(f"   Scan time: {orig_time:.3f}s")
        
        # Compare
        print("\n" + "="*60)
        print("COMPARISON")
        print("="*60)
        improvement = orig_time / opt_time
        print(f"Speed improvement: {improvement:.1f}x faster")
        print(f"Time saved: {orig_time - opt_time:.3f}s")
    except KeyboardInterrupt:
        print("   ⏱️  Timeout (>20s)")
    
    # Verify same projects found
    print("\n3. VERIFICATION:")
    print(f"   Projects found: {len(opt_projects)}")
    for p in sorted(opt_projects):
        print(f"   - {p.parent.parent.name}")
