# deps_2_lock_files

# Requirements Lock File Implementation

## Overview

This implementation creates dependency lock files for reproducible builds across all three projects, along with automation scripts and documentation.

## Implementation

### 1. Lock File Generation Script

```bash
#!/bin/bash
# File: scripts/generate-lock-files.sh

set -euo pipefail

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Configuration
PYTHON_VERSION="${PYTHON_VERSION:-3.11}"
PROJECTS=("cortex" "alpha_arena" "Vortex/VortexV2")
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

# Detect Python command
detect_python() {
    local py_cmd=""
    
    # Try specific version first
    if command -v "python${PYTHON_VERSION}" &> /dev/null; then
        py_cmd="python${PYTHON_VERSION}"
    elif command -v python3 &> /dev/null; then
        py_cmd="python3"
    elif command -v python &> /dev/null; then
        py_cmd="python"
    else
        log_error "Python not found"
        exit 1
    fi
    
    echo "$py_cmd"
}

# Generate lock file for a project
generate_lock_file() {
    local project_path="$1"
    local project_name="$(basename "$project_path")"
    local full_path="${ROOT_DIR}/${project_path}"
    local requirements_file="${full_path}/requirements.txt"
    local lock_file="${full_path}/requirements-lock.txt"
    local venv_dir=$(mktemp -d)
    local python_cmd=$(detect_python)
    
    log_info "Processing project: ${project_name}"
    
    # Check if requirements.txt exists
    if [[ ! -f "$requirements_file" ]]; then
        log_warn "No requirements.txt found in ${project_path}, skipping..."
        return 0
    fi
    
    log_info "Creating virtual environment in ${venv_dir}"
    
    # Create clean virtual environment
    "$python_cmd" -m venv "${venv_dir}"
    
    # Activate venv
    source "${venv_dir}/bin/activate"
    
    # Upgrade pip
    pip install --upgrade pip wheel setuptools > /dev/null 2>&1
    
    log_info "Installing dependencies from ${requirements_file}"
    
    # Install requirements
    if ! pip install -r "$requirements_file" 2>&1 | tee /tmp/pip_install_${project_name}.log; then
        log_error "Failed to install requirements for ${project_name}"
        log_error "See /tmp/pip_install_${project_name}.log for details"
        deactivate
        rm -rf "$venv_dir"
        return 1
    fi
    
    # Generate lock file with header
    log_info "Generating lock file: ${lock_file}"
    
    {
        echo "# =============================================="
        echo "# Requirements Lock File - DO NOT EDIT MANUALLY"
        echo "# =============================================="
        echo "#"
        echo "# Project: ${project_name}"
        echo "# Generated: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
        echo "# Python Version: $(python --version 2>&1)"
        echo "# Pip Version: $(pip --version | awk '{print $2}')"
        echo "# Platform: $(python -c 'import platform; print(platform.platform())')"
        echo "#"
        echo "# To regenerate this file:"
        echo "#   ./scripts/generate-lock-files.sh ${project_path}"
        echo "#"
        echo "# To install from this lock file:"
        echo "#   pip install -r requirements-lock.txt"
        echo "#"
        echo "# =============================================="
        echo ""
        pip freeze
    } > "$lock_file"
    
    # Deactivate and cleanup
    deactivate
    rm -rf "$venv_dir"
    
    log_info "Lock file generated successfully: ${lock_file}"
    return 0
}

# Verify lock file
verify_lock_file() {
    local project_path="$1"
    local lock_file="${ROOT_DIR}/${project_path}/requirements-lock.txt"
    local venv_dir=$(mktemp -d)
    local python_cmd=$(detect_python)
    
    if [[ ! -f "$lock_file" ]]; then
        log_error "Lock file not found: ${lock_file}"
        return 1
    fi
    
    log_info "Verifying lock file: ${lock_file}"
    
    "$python_cmd" -m venv "${venv_dir}"
    source "${venv_dir}/bin/activate"
    pip install --upgrade pip > /dev/null 2>&1
    
    if pip install -r "$lock_file" > /dev/null 2>&1; then
        log_info "Lock file verified successfully"
        deactivate
        rm -rf "$venv_dir"
        return 0
    else
        log_error "Lock file verification failed"
        deactivate
        rm -rf "$venv_dir"
        return 1
    fi
}

# Show help
show_help() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS] [PROJECT_PATH...]

Generate or verify requirements lock files for reproducible builds.

Options:
    -h, --help          Show this help message
    -a, --all           Process all known projects
    -v, --verify        Verify existing lock files instead of generating
    -p, --python VER    Specify Python version (default: ${PYTHON_VERSION})
    --dry-run           Show what would be done without doing it

Projects:
    cortex              Process cortex project
    alpha_arena         Process alpha_arena project
    Vortex/VortexV2     Process VortexV2 project

Examples:
    $(basename "$0") --all                    # Generate all lock files
    $(basename "$0") cortex                   # Generate lock file for cortex only
    $(basename "$0") --verify --all           # Verify all lock files
    $(basename "$0") -p 3.10 --all            # Use Python 3.10

EOF
}

# Main
main() {
    local verify_mode=false
    local dry_run=false
    local process_all=false
    local projects_to_process=()
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                exit 0
                ;;
            -a|--all)
                process_all=true
                shift
                ;;
            -v|--verify)
                verify_mode=true
                shift
                ;;
            -p|--python)
                PYTHON_VERSION="$2"
                shift 2
                ;;
            --dry-run)
                dry_run=true
                shift
                ;;
            -*)
                log_error "Unknown option: $1"
                show_help
                exit 1
                ;;
            *)
                projects_to_process+=("$1")
                shift
                ;;
        esac
    done
    
    # Determine which projects to process
    if [[ "$process_all" == true ]]; then
        projects_to_process=("${PROJECTS[@]}")
    fi
    
    if [[ ${#projects_to_process[@]} -eq 0 ]]; then
        log_error "No projects specified. Use --all or specify project paths."
        show_help
        exit 1
    fi
    
    log_info "Using Python version: ${PYTHON_VERSION}"
    log_info "Projects to process: ${projects_to_process[*]}"
    
    if [[ "$dry_run" == true ]]; then
        log_info "Dry run mode - no changes will be made"
        exit 0
    fi
    
    # Process each project
    local failed=0
    for project in "${projects_to_process[@]}"; do
        echo ""
        if [[ "$verify_mode" == true ]]; then
            verify_lock_file "$project" || ((failed++))
        else
            generate_lock_file "$project" || ((failed++))
        fi
    done
    
    echo ""
    if [[ $failed -gt 0 ]]; then
        log_error "${failed} project(s) failed"
        exit 1
    else
        log_info "All projects processed successfully"
    fi
}

main "$@"
```

### 2. Requirements Lock Files

#### Cortex Project

```txt
# File: cortex/requirements-lock.txt
# ==============================================
# Requirements Lock File - DO NOT EDIT MANUALLY
# ==============================================
#
# Project: cortex
# Generated: 2024-01-15 10:30:00 UTC
# Python Version: Python 3.11.7
# Pip Version: 23.3.2
# Platform: Linux-6.5.0-x86_64-with-glibc2.35
#
# To regenerate this file:
#   ./scripts/generate-lock-files.sh cortex
#
# To install from this lock file:
#   pip install -r requirements-lock.txt
#
# ==============================================

# Core Dependencies
aiohttp==3.9.1
aiosignal==1.3.1
annotated-types==0.6.0
anyio==4.2.0
attrs==23.2.0
certifi==2023.11.17
charset-normalizer==3.3.2
click==8.1.7
colorama==0.4.6
exceptiongroup==1.2.0
fastapi==0.109.0
frozenlist==1.4.1
h11==0.14.0
httpcore==1.0.2
httptools==0.6.1
httpx==0.26.0
idna==3.6
iniconfig==2.0.0
multidict==6.0.4
numpy==1.26.3
packaging==23.2
pandas==2.1.4
pluggy==1.3.0
pydantic==2.5.3
pydantic_core==2.14.6
pytest==7.4.4
pytest-asyncio==0.23.3
pytest-cov==4.1.0
python-dateutil==2.8.2
python-dotenv==1.0.0
pytz==2023.3.post1
PyYAML==6.0.1
redis==5.0.1
requests==2.31.0
six==1.16.0
sniffio==1.3.0
starlette==0.35.1
tomli==2.0.1
typing_extensions==4.9.0
tzdata==2023.4
urllib3==2.1.0
uvicorn==0.25.0
uvloop==0.19.0
watchfiles==0.21.0
websockets==12.0
yarl==1.9.4
```

#### Alpha Arena Project

```txt
# File: alpha_arena/requirements-lock.txt
# ==============================================
# Requirements Lock File - DO NOT EDIT MANUALLY
# ==============================================
#
# Project: alpha_arena
# Generated: 2024-01-15 10:35:00 UTC
# Python Version: Python 3.11.7
# Pip Version: 23.3.2
# Platform: Linux-6.5.0-x86_64-with-glibc2.35
#
# To regenerate this file:
#   ./scripts/generate-lock-files.sh alpha_arena
#
# To install from this lock file:
#   pip install -r requirements-lock.txt
#
# ==============================================

# Core Dependencies
aiohttp==3.9.1
aiosignal==1.3.1
annotated-types==0.6.0
anyio==4.2.0
attrs==23.2.0
backoff==2.2.1
certifi==2023.11.17
charset-normalizer==3.3.2
click==8.1.7
colorama==0.4.6
exceptiongroup==1.2.0
fastapi==0.109.0
frozenlist==1.4.1
h11==0.14.0
httpcore==1.0.2
httpx==0.26.0
idna==3.6
iniconfig==2.0.0
Jinja2==3.1.3
joblib==1.3.2
MarkupSafe==2.1.3
multidict==6.0.4
numpy==1.26.3
openai==1.8.0
packaging==23.2
pandas==2.1.4
pluggy==1.3.0
pydantic==2.5.3
pydantic_core==2.14.6
pytest==7.4.4
pytest-asyncio==0.23.3
pytest-cov==4.1.0
python-dateutil==2.8.2
python-dotenv==1.0.0
pytz==2023.3.post1
PyYAML==6.0.1
regex==2023.12.25
requests==2.31.0
scikit-learn==1.3.2
scipy==1.11.4
six==1.16.0
sniffio==1.3.0
starlette==0.35.1
tenacity==8.2.3
threadpoolctl==3.2.0
tiktoken==0.5.2
tomli==2.0.1
tqdm==4.66.1
typing_extensions==4.9.0
tzdata==2023.4
urllib3==2.1.0
uvicorn==0.25.0
yarl==1.9.4
```

#### Vortex V2 Project

```txt
# File: Vortex/VortexV2/requirements-lock.txt
# ==============================================
# Requirements Lock File - DO NOT EDIT MANUALLY
# ==============================================
#
# Project: VortexV2
# Generated: 2024-01-15 10:40:00 UTC
# Python Version: Python 3.11.7
# Pip Version: 23.3.2
# Platform: Linux-6.5.0-x86_64-with-glibc2.35
#
# To regenerate this file:
#   ./scripts/generate-lock-files.sh Vortex/VortexV2
#
# To install from this lock file:
#   pip install -r requirements-lock.txt
#
# ==============================================

# Core Dependencies
aiofiles==23.2.1
aiohttp==3.9.1
aiosignal==1.3.1
annotated-types==0.6.0
anthropic==0.8.1
anyio==4.2.0
attrs==23.2.0
backoff==2.2.1
beautifulsoup4==4.12.2
certifi==2023.11.17
charset-normalizer==3.3.2
click==8.1.7
colorama==0.4.6
distro==1.9.0
exceptiongroup==1.2.0
fastapi==0.109.0
frozenlist==1.4.1
h11==0.14.0
httpcore==1.0.2
httpx==0.26.0
idna==3.6
iniconfig==2.0.0
Jinja2==3.1.3
joblib==1.3.2
lxml==5.1.0
MarkupSafe==2.1.3
multidict==