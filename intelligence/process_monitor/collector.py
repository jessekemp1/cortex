"""
Process data collector using psutil.
"""

import psutil
import subprocess
from datetime import datetime
from typing import List, Dict, Any, Optional
from .models import (
    ProcessSnapshot,
    ResourceMetric,
    ProcessCategory,
    ProcessStatus,
)


class ProcessCollector:
    """Collects process and resource data using psutil."""

    # Process categorization patterns
    AI_TOOL_PATTERNS = [
        "claude", "ollama", "copilot", "cursor", "anthropic",
        "openai", "gpt", "chatgpt", "codeium", "tabnine"
    ]

    DEV_SERVICE_PATTERNS = [
        "uvicorn", "streamlit", "postgres", "node", "expo",
        "fastapi", "django", "flask", "npm", "yarn", "pnpm"
    ]

    BACKGROUND_PATTERNS = [
        "launchd", "batch", "cron", "cortex",
        "com.claude", "com.nightlytests"
    ]

    CONTAINER_PATTERNS = [
        "docker", "colima", "containerd", "qemu",
        "com.docker", "docker-compose"
    ]

    BUILD_PATTERNS = [
        "pytest", "tsc", "webpack", "vite", "rollup",
        "cargo", "go build", "javac", "rustc"
    ]

    def __init__(self):
        """Initialize the collector."""
        self._process_cache: Dict[int, psutil.Process] = {}

    def collect_snapshot(self) -> List[ProcessSnapshot]:
        """
        Collect current snapshot of all processes.

        Returns:
            List of ProcessSnapshot objects
        """
        snapshots = []

        for proc in psutil.process_iter(['pid', 'name', 'status', 'cpu_percent',
                                         'memory_info', 'create_time', 'cmdline',
                                         'username', 'num_threads']):
            try:
                info = proc.info

                # Skip kernel processes
                if info['pid'] == 0:
                    continue

                # Get process details
                pid = info['pid']
                name = info['name'] or 'unknown'
                status = self._map_status(info['status'])

                # Get CPU and memory
                cpu_percent = info['cpu_percent'] or 0.0
                memory_mb = (info['memory_info'].rss / 1024 / 1024) if info['memory_info'] else 0.0

                # Get start time
                start_time = datetime.fromtimestamp(info['create_time']) if info['create_time'] else datetime.now()

                # Get command
                cmdline = info['cmdline'] or []
                command = ' '.join(cmdline) if cmdline else name

                # Categorize process
                category = self._categorize_process(name, command)

                # Get port if applicable
                port = self._get_process_port(proc)

                # Get parent PID
                try:
                    parent_pid = proc.ppid()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    parent_pid = None

                snapshot = ProcessSnapshot(
                    pid=pid,
                    name=name,
                    category=category,
                    cpu_percent=cpu_percent,
                    memory_mb=memory_mb,
                    status=status,
                    start_time=start_time,
                    command=command[:500],  # Limit command length
                    port=port,
                    parent_pid=parent_pid,
                    username=info['username'],
                    num_threads=info['num_threads'] or 1,
                )

                snapshots.append(snapshot)

            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                # Process may have terminated or we don't have access
                continue
            except Exception as e:
                # Log but continue
                print(f"Error collecting process {info.get('pid', 'unknown')}: {e}")
                continue

        return snapshots

    def get_resource_summary(self) -> ResourceMetric:
        """
        Get system-wide resource summary.

        Returns:
            ResourceMetric object
        """
        # Get CPU usage
        total_cpu = psutil.cpu_percent(interval=0.1)

        # Get memory info
        memory = psutil.virtual_memory()
        total_memory_mb = memory.total / 1024 / 1024
        available_memory_mb = memory.available / 1024 / 1024

        # Count processes
        process_count = len(psutil.pids())

        # Get category-specific metrics
        snapshots = self.collect_snapshot()
        ai_tool_cpu = sum(p.cpu_percent for p in snapshots if p.category == ProcessCategory.AI_TOOL)
        ai_tool_memory = sum(p.memory_mb for p in snapshots if p.category == ProcessCategory.AI_TOOL)
        dev_service_cpu = sum(p.cpu_percent for p in snapshots if p.category == ProcessCategory.DEV_SERVICE)
        dev_service_memory = sum(p.memory_mb for p in snapshots if p.category == ProcessCategory.DEV_SERVICE)
        docker_cpu = sum(p.cpu_percent for p in snapshots if p.category == ProcessCategory.CONTAINER)
        docker_memory = sum(p.memory_mb for p in snapshots if p.category == ProcessCategory.CONTAINER)

        return ResourceMetric(
            timestamp=datetime.now(),
            total_cpu_percent=total_cpu,
            available_memory_mb=available_memory_mb,
            total_memory_mb=total_memory_mb,
            process_count=process_count,
            ai_tool_cpu=ai_tool_cpu,
            ai_tool_memory=ai_tool_memory,
            dev_service_cpu=dev_service_cpu,
            dev_service_memory=dev_service_memory,
            docker_cpu=docker_cpu,
            docker_memory_mb=docker_memory,
        )

    def get_port_usage(self) -> Dict[int, ProcessSnapshot]:
        """
        Get mapping of ports to processes.

        Returns:
            Dictionary mapping port numbers to ProcessSnapshot objects
        """
        port_map = {}
        snapshots = self.collect_snapshot()

        for snapshot in snapshots:
            if snapshot.port:
                port_map[snapshot.port] = snapshot

        return port_map

    def get_docker_stats(self) -> Dict[str, Any]:
        """
        Get Docker/Colima statistics if available.

        Returns:
            Dictionary with Docker stats or empty dict if not available
        """
        try:
            # Check if Docker is running
            result = subprocess.run(
                ['docker', 'ps', '--format', '{{.ID}}:{{.Names}}:{{.Status}}'],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                containers = []
                for line in result.stdout.strip().split('\n'):
                    if line:
                        parts = line.split(':')
                        if len(parts) >= 3:
                            containers.append({
                                'id': parts[0],
                                'name': parts[1],
                                'status': parts[2],
                            })

                return {
                    'available': True,
                    'container_count': len(containers),
                    'containers': containers,
                }
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
            pass

        return {'available': False}

    def _categorize_process(self, name: str, command: str) -> ProcessCategory:
        """
        Categorize a process based on name and command.

        Args:
            name: Process name
            command: Full command line

        Returns:
            ProcessCategory
        """
        name_lower = name.lower()
        command_lower = command.lower()

        # Check AI tools
        if any(pattern in name_lower or pattern in command_lower
               for pattern in self.AI_TOOL_PATTERNS):
            return ProcessCategory.AI_TOOL

        # Check dev services
        if any(pattern in name_lower or pattern in command_lower
               for pattern in self.DEV_SERVICE_PATTERNS):
            return ProcessCategory.DEV_SERVICE

        # Check background agents
        if any(pattern in name_lower or pattern in command_lower
               for pattern in self.BACKGROUND_PATTERNS):
            return ProcessCategory.BACKGROUND_AGENT

        # Check containers
        if any(pattern in name_lower or pattern in command_lower
               for pattern in self.CONTAINER_PATTERNS):
            return ProcessCategory.CONTAINER

        # Check build tools
        if any(pattern in name_lower or pattern in command_lower
               for pattern in self.BUILD_PATTERNS):
            return ProcessCategory.BUILD_TOOL

        # System processes
        if name_lower.startswith(('kernel', 'system', 'launchd')):
            return ProcessCategory.SYSTEM

        return ProcessCategory.OTHER

    def _map_status(self, psutil_status: str) -> ProcessStatus:
        """
        Map psutil status to our ProcessStatus enum.

        Args:
            psutil_status: Status from psutil

        Returns:
            ProcessStatus
        """
        status_map = {
            psutil.STATUS_RUNNING: ProcessStatus.RUNNING,
            psutil.STATUS_SLEEPING: ProcessStatus.SLEEPING,
            psutil.STATUS_DISK_SLEEP: ProcessStatus.DISK_SLEEP,
            psutil.STATUS_ZOMBIE: ProcessStatus.ZOMBIE,
            psutil.STATUS_STOPPED: ProcessStatus.STOPPED,
        }
        return status_map.get(psutil_status, ProcessStatus.RUNNING)

    def _get_process_port(self, proc: psutil.Process) -> Optional[int]:
        """
        Get the primary port used by a process.

        Args:
            proc: psutil.Process object

        Returns:
            Port number or None
        """
        try:
            connections = proc.connections(kind='inet')
            for conn in connections:
                if conn.status == 'LISTEN' and conn.laddr:
                    return conn.laddr.port
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

        return None

    def get_process_by_pid(self, pid: int) -> Optional[ProcessSnapshot]:
        """
        Get a specific process by PID.

        Args:
            pid: Process ID

        Returns:
            ProcessSnapshot or None if not found
        """
        snapshots = self.collect_snapshot()
        for snapshot in snapshots:
            if snapshot.pid == pid:
                return snapshot
        return None

    def get_processes_by_category(self, category: ProcessCategory) -> List[ProcessSnapshot]:
        """
        Get all processes of a specific category.

        Args:
            category: ProcessCategory to filter by

        Returns:
            List of ProcessSnapshot objects
        """
        snapshots = self.collect_snapshot()
        return [s for s in snapshots if s.category == category]

    def get_zombie_processes(self) -> List[ProcessSnapshot]:
        """
        Get all zombie processes.

        Returns:
            List of ProcessSnapshot objects for zombie processes
        """
        snapshots = self.collect_snapshot()
        return [s for s in snapshots if s.status == ProcessStatus.ZOMBIE]

    def get_high_resource_processes(self,
                                     cpu_threshold: float = 50.0,
                                     memory_mb_threshold: float = 1000.0) -> List[ProcessSnapshot]:
        """
        Get processes using high resources.

        Args:
            cpu_threshold: CPU percentage threshold
            memory_mb_threshold: Memory threshold in MB

        Returns:
            List of ProcessSnapshot objects
        """
        snapshots = self.collect_snapshot()
        return [
            s for s in snapshots
            if s.cpu_percent > cpu_threshold or s.memory_mb > memory_mb_threshold
        ]
