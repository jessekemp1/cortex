"""
Batch Scheduler Daemon - Background process for automatic task execution.

Handles:
- Daemon lifecycle (start, stop, status)
- Signal handling for graceful shutdown
- PID file management
- File-based logging
- Automatic task scheduling and execution
"""

import logging
import os
import signal
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import psutil

from .batch_executor import BatchExecutor
from .batch_queue import BatchTaskQueue


class BatchDaemon:
    """
    Manages the batch scheduler daemon process.

    Features:
    - Signal handling (SIGTERM, SIGINT) for graceful shutdown
    - PID file tracking
    - File-based logging
    - Automatic task scheduling and execution
    """

    PID_FILE = Path.home() / ".cortex" / "batch_daemon.pid"
    LOG_FILE = Path.home() / ".cortex" / "logs" / "batch_daemon.log"

    def __init__(
        self,
        queue: Optional[BatchTaskQueue] = None,
        executor: Optional[BatchExecutor] = None,
        process_monitor: Optional[Any] = None,
    ):
        """
        Initialize daemon manager.

        Args:
            queue: BatchTaskQueue instance (creates default if None)
            executor: BatchExecutor instance (creates default if None)
            process_monitor: ProcessMonitor for capacity checking
        """
        self.queue = queue or BatchTaskQueue()
        self.executor = executor or BatchExecutor(queue=self.queue, process_monitor=process_monitor)

        # Ensure directories exist
        self.PID_FILE.parent.mkdir(parents=True, exist_ok=True)
        self.LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""

        def shutdown_handler(signum, frame):
            sig_name = "SIGTERM" if signum == signal.SIGTERM else "SIGINT"
            logging.info(f"Received {sig_name}, initiating graceful shutdown...")
            self.executor.shutdown()
            sys.exit(0)

        signal.signal(signal.SIGTERM, shutdown_handler)
        signal.signal(signal.SIGINT, shutdown_handler)

    def _setup_logging(self):
        """Setup file-based logging for daemon."""
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler(self.LOG_FILE),
                logging.StreamHandler(sys.stdout),  # Also log to stdout in foreground mode
            ],
        )

    def _write_pid_file(self) -> None:
        """Write current process PID to file."""
        pid = os.getpid()
        self.PID_FILE.write_text(str(pid))
        logging.info(f"Daemon started with PID {pid}")

    def _remove_pid_file(self) -> None:
        """Remove PID file."""
        if self.PID_FILE.exists():
            self.PID_FILE.unlink()
            logging.info("PID file removed")

    def _read_pid_file(self) -> Optional[int]:
        """
        Read PID from file.

        Returns:
            PID as integer, or None if file doesn't exist
        """
        if not self.PID_FILE.exists():
            return None

        try:
            pid_str = self.PID_FILE.read_text().strip()
            return int(pid_str)
        except (ValueError, IOError):
            return None

    def _is_process_running(self, pid: int) -> bool:
        """
        Check if process with given PID is running.

        Args:
            pid: Process ID to check

        Returns:
            True if running, False otherwise
        """
        try:
            process = psutil.Process(pid)
            return process.is_running()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False

    def start(self, interval_seconds: int = 60, foreground: bool = True) -> Dict[str, Any]:
        """
        Start the daemon.

        Args:
            interval_seconds: Task check interval (default: 60s)
            foreground: Run in foreground (True) or background (False)

        Returns:
            Status dictionary with success/error information
        """
        # Check if already running
        existing_pid = self._read_pid_file()
        if existing_pid and self._is_process_running(existing_pid):
            return {
                "success": False,
                "error": f"Daemon already running with PID {existing_pid}",
                "pid": existing_pid,
            }

        # Clean up stale PID file
        if existing_pid:
            self._remove_pid_file()

        if not foreground:
            # Fork to background
            try:
                pid = os.fork()
                if pid > 0:
                    # Parent process - return immediately
                    return {
                        "success": True,
                        "message": "Daemon started in background",
                        "pid": pid,
                        "interval": interval_seconds,
                        "log_file": str(self.LOG_FILE),
                    }
            except OSError as e:
                return {"success": False, "error": f"Failed to fork process: {e}"}

            # Child process continues below
            # Detach from parent
            os.setsid()

            # Second fork to prevent zombie
            try:
                pid = os.fork()
                if pid > 0:
                    sys.exit(0)
            except OSError:
                sys.exit(1)

            # Redirect standard file descriptors
            sys.stdout.flush()
            sys.stderr.flush()

            # Setup logging (file only for background)
            logging.basicConfig(
                level=logging.INFO,
                format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                handlers=[logging.FileHandler(self.LOG_FILE)],
            )
        else:
            # Foreground mode - setup logging with stdout
            self._setup_logging()

        # Setup signal handlers
        self._setup_signal_handlers()

        # Write PID file
        self._write_pid_file()

        try:
            # Run daemon loop
            logging.info(f"Starting scheduler daemon (interval: {interval_seconds}s)")
            self.executor.run_scheduler_daemon(interval_seconds=interval_seconds)
        except Exception as e:
            logging.error(f"Daemon error: {e}", exc_info=True)
            return {"success": False, "error": str(e)}
        finally:
            # Cleanup
            self._remove_pid_file()

        return {"success": True, "message": "Daemon stopped", "pid": os.getpid()}

    def stop(self) -> Dict[str, Any]:
        """
        Stop the daemon.

        Returns:
            Status dictionary with success/error information
        """
        pid = self._read_pid_file()

        if not pid:
            return {
                "success": False,
                "error": "Daemon is not running (no PID file found)",
            }

        if not self._is_process_running(pid):
            # Process not running, clean up stale PID file
            self._remove_pid_file()
            return {
                "success": False,
                "error": f"Daemon not running (stale PID file for PID {pid})",
            }

        # Send SIGTERM for graceful shutdown
        try:
            os.kill(pid, signal.SIGTERM)

            # Wait for process to stop (up to 10 seconds)
            import time

            for _ in range(100):  # 100 * 0.1s = 10s
                if not self._is_process_running(pid):
                    break
                time.sleep(0.1)

            # Check if stopped
            if self._is_process_running(pid):
                # Force kill if still running
                os.kill(pid, signal.SIGKILL)
                return {
                    "success": True,
                    "message": f"Daemon stopped (force killed PID {pid})",
                    "pid": pid,
                    "forced": True,
                }

            return {
                "success": True,
                "message": "Daemon stopped gracefully",
                "pid": pid,
                "forced": False,
            }

        except ProcessLookupError:
            # Process already gone
            self._remove_pid_file()
            return {"success": True, "message": "Daemon already stopped", "pid": pid}
        except PermissionError:
            return {"success": False, "error": f"Permission denied to stop PID {pid}"}
        except Exception as e:
            return {"success": False, "error": f"Failed to stop daemon: {e}"}

    def status(self) -> Dict[str, Any]:
        """
        Get daemon status.

        Returns:
            Status dictionary with running state and details
        """
        pid = self._read_pid_file()

        if not pid:
            return {
                "running": False,
                "message": "Daemon is not running",
                "pid_file": str(self.PID_FILE),
            }

        is_running = self._is_process_running(pid)

        if not is_running:
            return {
                "running": False,
                "message": f"Daemon not running (stale PID file for PID {pid})",
                "pid": pid,
                "pid_file": str(self.PID_FILE),
            }

        # Get process details
        try:
            process = psutil.Process(pid)
            create_time = datetime.fromtimestamp(process.create_time())
            uptime = datetime.now() - create_time

            # Format uptime
            hours = int(uptime.total_seconds() // 3600)
            minutes = int((uptime.total_seconds() % 3600) // 60)
            seconds = int(uptime.total_seconds() % 60)

            if hours > 0:
                uptime_str = f"{hours}h {minutes}m"
            elif minutes > 0:
                uptime_str = f"{minutes}m {seconds}s"
            else:
                uptime_str = f"{seconds}s"

            return {
                "running": True,
                "message": f"Daemon running (PID {pid})",
                "pid": pid,
                "uptime": uptime_str,
                "started_at": create_time.isoformat(),
                "cpu_percent": process.cpu_percent(interval=0.1),
                "memory_mb": process.memory_info().rss / 1024 / 1024,
                "log_file": str(self.LOG_FILE),
                "pid_file": str(self.PID_FILE),
            }
        except Exception as e:
            return {
                "running": True,
                "message": f"Daemon running (PID {pid}) - limited info",
                "pid": pid,
                "error": str(e),
            }
