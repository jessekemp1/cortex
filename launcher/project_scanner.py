#!/usr/bin/env python3
"""
Cortex Project Scanner - Auto-discover web projects in the monorepo
"""

import json
import subprocess
from pathlib import Path
from typing import Dict, List

MONOREPO_ROOT = Path.home() / "Dev"


def scan_projects() -> List[Dict]:
    """Scan monorepo for projects with web interfaces."""
    projects = []

    # Known project locations
    known_projects = {
        "cortex/site": {"name": "Cortex Command Center", "type": "react"},
        "cortex/dashboard": {"name": "Cortex Orchestration", "type": "streamlit"},
        "cortex/api": {"name": "Cortex Bridge API", "type": "fastapi"},
        "Vortex/VortexV2": {"name": "VortexV2", "type": "mixed"},
        "Vortex/VortexV3": {"name": "VortexV3", "type": "react"},
        "alpha_arena": {"name": "Alpha Arena", "type": "streamlit"},
        "kempion-research-site": {"name": "Kempion Research", "type": "react"},
        "DJ-CoPilot": {"name": "DJ CoPilot", "type": "react"},
    }

    for path_str, info in known_projects.items():
        project_path = MONOREPO_ROOT / path_str
        if not project_path.exists():
            continue

        project = {
            "name": info["name"],
            "path": str(project_path),
            "type": info["type"],
            "port": None,
            "start_command": None,
            "status": "stopped",
        }

        # Detect configuration
        if info["type"] == "react":
            package_json = project_path / "package.json"
            if package_json.exists():
                project["port"] = detect_vite_port(package_json)
                project["start_command"] = "npm run dev"

        elif info["type"] == "streamlit":
            project["port"] = detect_streamlit_port(project_path)
            # Alpha Arena uses ui/command_center.py (Mission Control), not app.py
            app_file = "ui/command_center.py" if "alpha" in info["name"].lower() else "app.py"
            project["start_command"] = f"streamlit run {app_file} --server.port {project['port']}"

        elif info["type"] == "fastapi":
            project["port"] = 8765 if "cortex" in path_str else 8000
            project["start_command"] = f"uvicorn api.bridge_endpoint:app --port {project['port']}"

        elif info["type"] == "mixed":
            # VortexV2 has both API and UI
            project["services"] = [
                {
                    "name": "API",
                    "port": 8000,
                    "start_command": "uvicorn app.main:app --port 8000",
                },
                {
                    "name": "UI",
                    "port": 8503,
                    "start_command": "streamlit run ui/command_center.py --server.port 8503",
                },
            ]

        projects.append(project)

    return projects


def detect_vite_port(package_json_path: Path) -> int:
    """Detect Vite dev server port from vite.config.ts or default."""
    vite_config = package_json_path.parent / "vite.config.ts"
    if vite_config.exists():
        content = vite_config.read_text()
        if "port:" in content:
            # Parse port from config using regex
            import re

            match = re.search(r"port:\s*(\d+)", content)
            if match:
                return int(match.group(1))

    # Project-specific defaults to avoid conflicts
    project_path_str = str(package_json_path.parent)
    if "VortexV3" in project_path_str:
        return 3002  # VortexV3 uses 3002 per PORT_ALLOCATION.md
    elif "kempion" in project_path_str.lower():
        return 5174  # Kempion Research uses 5174
    elif "cortex/site" in project_path_str:
        return 5173  # Cortex Command Center keeps 5173

    return 5173  # Default Vite port


def detect_streamlit_port(project_path: Path) -> int:
    """Detect Streamlit port from config or suggest one."""
    # Check for .streamlit/config.toml
    config_file = project_path / ".streamlit" / "config.toml"
    if config_file.exists():
        content = config_file.read_text()
        if "port" in content:
            import re

            match = re.search(r"port\s*=\s*(\d+)", content)
            if match:
                return int(match.group(1))

    # Default ports by project (avoid conflicts)
    if "cortex" in str(project_path):
        return 8502  # Cortex Orchestration
    elif "alpha" in str(project_path).lower():
        return 8504  # Alpha Arena (changed from 8503 to avoid VortexV2 UI conflict)
    elif "vortex" in str(project_path).lower():
        return 8503  # VortexV2 UI
    return 8501


def get_running_processes() -> Dict[int, Dict]:
    """Get all running web server processes and their ports."""
    processes = {}

    try:
        # Get processes
        subprocess.run(["ps", "aux"], capture_output=True, text=True, check=True).stdout

        # Get port listeners
        lsof_output = subprocess.run(
            ["lsof", "-i", "-P", "-n"], capture_output=True, text=True, check=True
        ).stdout

        # Parse lsof for ports
        for line in lsof_output.splitlines()[1:]:
            parts = line.split()
            if len(parts) > 9 and "LISTEN" in line:
                pid = int(parts[1])
                port_info = parts[8]
                if ":" in port_info:
                    port = int(port_info.split(":")[-1])
                    processes[port] = {
                        "pid": pid,
                        "command": parts[0],
                        "status": "running",
                    }

    except Exception as e:
        print(f"Error scanning processes: {e}")

    return processes


def generate_launcher_data() -> Dict:
    """Generate complete launcher data structure."""
    projects = scan_projects()
    running = get_running_processes()

    # Match projects to running processes
    for project in projects:
        if "services" in project:
            for service in project["services"]:
                if service["port"] in running:
                    service["status"] = "running"
                    service["pid"] = running[service["port"]]["pid"]
        elif project["port"] and project["port"] in running:
            project["status"] = "running"
            project["pid"] = running[project["port"]]["pid"]

    return {
        "projects": projects,
        "running_processes": running,
        "generated_at": subprocess.run(
            ["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip(),
    }


if __name__ == "__main__":
    data = generate_launcher_data()
    output_file = Path(__file__).parent / "launcher_data.json"
    output_file.write_text(json.dumps(data, indent=2))
    print(f"✅ Launcher data written to {output_file}")
    print(f"   Found {len(data['projects'])} projects")
    print(f"   {len(data['running_processes'])} ports in use")
