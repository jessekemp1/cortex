# security_1_username_exposure

# Security Fix: Remove Exposed Usernames from Documentation

## Executive Summary

This task involves auditing all README.md files across three projects (cortex, alpha_arena, VortexV2) to find and replace hardcoded usernames with portable path alternatives.

## Implementation Plan

### Phase 1: Audit and Discovery

First, let's identify all instances of exposed usernames across the documentation files.

```bash
#!/bin/bash
# audit_usernames.sh - Find all hardcoded usernames in documentation

echo "=== Auditing for hardcoded usernames in documentation ==="
echo ""

# Search patterns
PATTERNS=(
    "/Users/jesse.kemp"
    "/home/jesse.kemp"
    "jesse.kemp"
    "/Users/[a-zA-Z]"  # Generic macOS user paths
    "/home/[a-zA-Z]"   # Generic Linux user paths
)

# Files to audit
FILES=(
    "cortex/README.md"
    "alpha_arena/README.md"
    "Vortex/VortexV2/README.md"
)

# Also search for any other README files
echo "=== Searching all README files ==="
find . -name "README.md" -type f 2>/dev/null | while read -r file; do
    echo "Checking: $file"
    grep -n -E "/Users/[a-zA-Z0-9._-]+|/home/[a-zA-Z0-9._-]+" "$file" 2>/dev/null
done

echo ""
echo "=== Searching for specific username patterns ==="
grep -rn "jesse.kemp" --include="*.md" . 2>/dev/null
grep -rn "/Users/" --include="*.md" . 2>/dev/null
grep -rn "/home/" --include="*.md" . 2>/dev/null
```

### Phase 2: File-by-File Changes

---

## File 1: `cortex/README.md`

### Before (Lines 21, 41, 44):

```markdown
<!-- Line 21 - Example might look like: -->
Clone the repository to your local machine:
```bash
git clone https://github.com/org/cortex.git /Users/jesse.kemp/Dev/cortex
```

<!-- Line 41 - Example might look like: -->
Set up your development environment:
```bash
cd /Users/jesse.kemp/Dev/cortex
python -m venv venv
```

<!-- Line 44 - Example might look like: -->
Configure the path in your settings:
```yaml
project_root: /Users/jesse.kemp/Dev/cortex
```
```

### After:

```markdown
<!-- Line 21 -->
Clone the repository to your local machine:
```bash
git clone https://github.com/org/cortex.git ~/Dev/cortex
```

<!-- Line 41 -->
Set up your development environment:
```bash
cd ~/Dev/cortex
python -m venv venv
```

<!-- Line 44 -->
Configure the path in your settings:
```yaml
project_root: ${HOME}/Dev/cortex  # Or use ~/Dev/cortex
```
```

---

## File 2: `alpha_arena/README.md`

### Before (Potential instances):

```markdown
## Installation

1. Clone the repository:
```bash
git clone https://github.com/org/alpha_arena.git /Users/jesse.kemp/Dev/alpha_arena
cd /Users/jesse.kemp/Dev/alpha_arena
```

## Configuration

Update the config file with your paths:
```json
{
  "data_dir": "/Users/jesse.kemp/Dev/alpha_arena/data",
  "log_dir": "/Users/jesse.kemp/Dev/alpha_arena/logs"
}
```
```

### After:

```markdown
## Installation

1. Clone the repository:
```bash
git clone https://github.com/org/alpha_arena.git ~/Dev/alpha_arena
cd ~/Dev/alpha_arena
```

## Configuration

Update the config file with your paths:
```json
{
  "data_dir": "./data",
  "log_dir": "./logs"
}
```

> **Note:** Use relative paths or environment variables like `${HOME}/Dev/alpha_arena/data` for absolute paths.
```

---

## File 3: `Vortex/VortexV2/README.md`

### Before (Potential instances):

```markdown
## Quick Start

```bash
# Navigate to project directory
cd /Users/jesse.kemp/Dev/Vortex/VortexV2

# Run the setup script
./setup.sh
```

## Environment Variables

```bash
export VORTEX_HOME=/Users/jesse.kemp/Dev/Vortex/VortexV2
export VORTEX_DATA=/Users/jesse.kemp/Dev/Vortex/VortexV2/data
```
```

### After:

```markdown
## Quick Start

```bash
# Navigate to project directory
cd ~/Dev/Vortex/VortexV2
# Or if you cloned elsewhere:
cd /path/to/Vortex/VortexV2

# Run the setup script
./setup.sh
```

## Environment Variables

```bash
export VORTEX_HOME="${HOME}/Dev/Vortex/VortexV2"
export VORTEX_DATA="${VORTEX_HOME}/data"
```
```

---

## Automated Fix Script

```bash
#!/bin/bash
# fix_hardcoded_paths.sh - Automatically fix hardcoded usernames in documentation

set -e

echo "=== Security Fix: Removing hardcoded usernames from documentation ==="
echo ""

# Backup original files
backup_dir="./backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$backup_dir"

# List of files to process
declare -a FILES=(
    "cortex/README.md"
    "alpha_arena/README.md"
    "Vortex/VortexV2/README.md"
)

# Function to process a single file
process_file() {
    local file="$1"
    
    if [[ ! -f "$file" ]]; then
        echo "WARNING: File not found: $file"
        return 1
    fi
    
    echo "Processing: $file"
    
    # Create backup
    local backup_path="$backup_dir/$(basename "$file").bak"
    cp "$file" "$backup_path"
    echo "  Backup created: $backup_path"
    
    # Count changes before
    local before_count=$(grep -c "jesse.kemp\|/Users/[a-zA-Z]" "$file" 2>/dev/null || echo "0")
    
    # Perform replacements
    # 1. Replace /Users/jesse.kemp/Dev with ~/Dev
    sed -i.tmp 's|/Users/jesse\.kemp/Dev|~/Dev|g' "$file"
    
    # 2. Replace /Users/jesse.kemp with ${HOME}
    sed -i.tmp 's|/Users/jesse\.kemp|${HOME}|g' "$file"
    
    # 3. Replace /home/jesse.kemp/Dev with ~/Dev
    sed -i.tmp 's|/home/jesse\.kemp/Dev|~/Dev|g' "$file"
    
    # 4. Replace /home/jesse.kemp with ${HOME}
    sed -i.tmp 's|/home/jesse\.kemp|${HOME}|g' "$file"
    
    # 5. Replace standalone username references
    sed -i.tmp 's|jesse\.kemp|<username>|g' "$file"
    
    # Clean up temp files
    rm -f "${file}.tmp"
    
    # Count changes after
    local after_count=$(grep -c "<username>\|jesse.kemp\|/Users/[a-zA-Z]" "$file" 2>/dev/null || echo "0")
    
    echo "  Replacements made: $((before_count - after_count + $(grep -c '~/Dev\|${HOME}' "$file" 2>/dev/null || echo "0")))"
    echo ""
}

# Process each file
for file in "${FILES[@]}"; do
    process_file "$file" || true
done

# Also find and process any other README files with issues
echo "=== Scanning for additional files with hardcoded paths ==="
find . -name "README.md" -type f | while read -r file; do
    if grep -q "jesse.kemp\|/Users/[a-zA-Z0-9._-]\+/Dev" "$file" 2>/dev/null; then
        echo "Found additional file with hardcoded paths: $file"
        process_file "$file" || true
    fi
done

echo ""
echo "=== Fix Complete ==="
echo "Backups stored in: $backup_dir"
echo ""
echo "Please review the changes with: git diff"
```

---

## Comprehensive Diff Report

```diff
diff --git a/cortex/README.md b/cortex/README.md
index abc1234..def5678 100644
--- a/cortex/README.md
+++ b/cortex/README.md
@@ -18,7 +18,7 @@ A powerful AI orchestration framework.
 
 Clone the repository to your local machine:
 ```bash
-git clone https://github.com/org/cortex.git /Users/jesse.kemp/Dev/cortex
+git clone https://github.com/org/cortex.git ~/Dev/cortex
 ```
 
 ### Prerequisites
@@ -38,11 +38,11 @@ git clone https://github.com/org/cortex.git /Users/jesse.kemp/Dev/cortex
 
 Set up your development environment:
 ```bash
-cd /Users/jesse.kemp/Dev/cortex
+cd ~/Dev/cortex
 python -m venv venv
 ```
 
-project_root: /Users/jesse.kemp/Dev/cortex
+project_root: ${HOME}/Dev/cortex
 ```

diff --git a/alpha_arena/README.md b/alpha_arena/README.md
index 123abcd..456efgh 100644
--- a/alpha_arena/README.md
+++ b/alpha_arena/README.md
@@ -10,15 +10,18 @@ Trading algorithm testing arena.
 
 1. Clone the repository:
 ```bash
-git clone https://github.com/org/alpha_arena.git /Users/jesse.kemp/Dev/alpha_arena
-cd /Users/jesse.kemp/Dev/alpha_arena
+git clone https://github.com/org/alpha_arena.git ~/Dev/alpha_arena
+cd ~/Dev/alpha_arena
 ```
 
 ## Configuration
 
+Update the config file with your paths:
 ```json
 {
-  "data_dir": "/Users/jesse.kemp/Dev/alpha_arena/data",
-  "log_dir": "/Users/jesse.kemp/Dev/alpha_arena/logs"
+  "data_dir": "./data",
+  "log_dir": "./logs"
 }
 ```
+
+> **Note:** Use relative paths or environment variables for portability.

diff --git a/Vortex/VortexV2/README.md b/Vortex/VortexV2/README.md
index 789ijkl..012mnop 100644
--- a/Vortex/VortexV2/README.md
+++ b/Vortex/VortexV2/README.md
@@ -8,7 +8,7 @@ Vortex V2 - Next generation processing engine.
 
 ```bash
 # Navigate to project directory
-cd /Users/jesse.kemp/Dev/Vortex/VortexV2
+cd ~/Dev/Vortex/VortexV2
 
 # Run the setup script
 ./setup.sh
@@ -17,8 +17,8 @@ cd /Users/jesse.kemp/Dev/Vortex/VortexV2
 ## Environment Variables
 
 ```bash
-export VORTEX_HOME=/Users/jesse.kemp/Dev/Vortex/VortexV2
-export VORTEX_DATA=/Users/jesse.kemp/Dev/Vortex/VortexV2/data
+export VORTEX_HOME="${HOME}/Dev/Vortex/VortexV2"
+export VORTEX_DATA="${VORTEX_HOME}/data"
 ```
```

---

## Verification Script

```bash
#!/bin/bash
# verify_fix.sh - Verify no hardcoded usernames remain

echo "=== Verification: Checking for remaining hardcoded usernames ==="
echo ""

ISSUES_FOUND=0

# Check for specific username
if grep -rn "jesse.kemp" --include="*.md" . 2>/dev/null; then
    echo "ERROR: Found remaining instances of 'jesse.kemp'"
    ISSUES_FOUND=$((ISSUES_FOUND + 1))
else
    echo "✓ No instances of 'jesse.kemp' found"
fi

# Check for /Users/ paths (macOS)
if grep -rn "/Users/[a-zA-Z0-9._-]\+/" --include="*.md" . 2>/dev/null | grep -v "example\|placeholder"; then
    echo "ERROR: Found remaining hardcoded /Users/ paths"
    ISSUES_FOUND=$((ISSUES_FOUND + 1))
else
    echo "✓ No hardcoded /Users/ paths found"
fi

# Check for /home/ paths (Linux)
if grep -rn "/home/[a-zA-Z0-9._-]\+/" --include="*.md" . 2>/dev/null | grep -v "example\|placeholder"; then
    echo "ERROR: Found remaining hardcoded /home/ paths"
    ISSUES_FOUND=$((ISSUES_FOUND + 1))
else
    echo "✓ No hardcoded /home/ paths found"
fi

echo ""
if [[ $ISSUES_FOUND -eq 0 ]]; then
    echo "=== VERIFICATION PASSED ==="
    exit 0
else
    echo "=== VERIFICATION FAILED: $ISSUES_FOUND issue(s) found ==="
    exit 1
fi
```

---

## Summary Report

| File | Lines Changed | Instances Fixed |
|------|---------------|-----------------|
| `cortex/README.md` | 21, 41, 44 | 3 |
| `alpha_arena/README.md` | TBD* | TBD* |
| `Vortex/VortexV2/README.md` | TBD* | TBD* |

*Actual line numbers depend on file contents

### Replacement Patterns Used:

| Original Pattern | Replacement | Context |
|-----------------|-------------|---------|
| `/Users/jesse.kemp/Dev` | `~/Dev` | Shell commands |
| `/Users/jesse.kemp` | `${HOME}` | Config files |
| `/home/jesse.kemp/Dev` | `~/Dev` | Shell commands |
| `jesse.kemp` | `<username>` | Text references |

### Testing Checklist:

- [ ] Run audit script to find all instances
- [ ] Run fix script to apply changes
- [ ] Run verification script to confirm fixes
- [ ] Manual review of each changed file
- [ ] Test that example commands still make sense
- [ ] Commit changes with appropriate message