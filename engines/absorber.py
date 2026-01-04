"""
Engine A: The Context Absorber

Passive ingestion of environmental signals.
This is the INPUT layer of Cortex V2 Prime.

Components:
- FileWatcher: Monitor filesystem events
- ShellListener: Capture terminal history/exit codes  
- IDEBridge: Receive cursor position/active file via MCP
- GitTracker: Track repository state (V1 foundation)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable
import json
import logging

logger = logging.getLogger(__name__)


class SignalType(Enum):
    """Types of environmental signals that can be absorbed."""
    FILE_CREATED = "file_created"
    FILE_MODIFIED = "file_modified"
    FILE_DELETED = "file_deleted"
    COMMAND_EXECUTED = "command_executed"
    COMMAND_FAILED = "command_failed"
    GIT_COMMIT = "git_commit"
    GIT_BRANCH_SWITCH = "git_branch_switch"
    IDE_FOCUS_CHANGE = "ide_focus_change"
    IDE_FILE_OPEN = "ide_file_open"
    IDE_FILE_SAVE = "ide_file_save"
    PLAN_STEP_STARTED = "plan_step_started"
    PLAN_STEP_COMPLETED = "plan_step_completed"


@dataclass
class Signal:
    """Raw environmental signal captured by the Absorber."""
    id: str
    type: SignalType
    timestamp: datetime
    source: str
    payload: Dict[str, Any]
    project: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    processed: bool = False
    absorbed_into: Optional[str] = None  # work_item_id

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "type": self.type.value,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "payload": self.payload,
            "project": self.project,
            "metadata": self.metadata,
            "processed": self.processed,
            "absorbed_into": self.absorbed_into,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "Signal":
        return cls(
            id=data["id"],
            type=SignalType(data["type"]),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            source=data["source"],
            payload=data["payload"],
            project=data.get("project"),
            metadata=data.get("metadata"),
            processed=data.get("processed", False),
            absorbed_into=data.get("absorbed_into"),
        )


class SignalSource(ABC):
    """Abstract base for signal sources."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name for this source."""
        pass

    @abstractmethod
    def start(self) -> None:
        """Start listening for signals."""
        pass

    @abstractmethod
    def stop(self) -> None:
        """Stop listening for signals."""
        pass

    @abstractmethod
    def get_signals(self) -> List[Signal]:
        """Get pending signals since last call."""
        pass

    @property
    def is_running(self) -> bool:
        """Check if source is currently running."""
        return False


class FileWatcher(SignalSource):
    """
    Monitor filesystem events.
    
    Uses watchdog library when available, falls back to polling.
    """

    def __init__(self, watch_paths: List[Path], ignore_patterns: Optional[List[str]] = None):
        self.watch_paths = watch_paths
        self.ignore_patterns = ignore_patterns or [
            "*.pyc", "__pycache__", ".git", "node_modules", "venv", ".venv"
        ]
        self._running = False
        self._signals: List[Signal] = []
        self._observer = None

    @property
    def name(self) -> str:
        return "FileWatcher"

    def start(self) -> None:
        """Start filesystem monitoring."""
        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler

            class SignalHandler(FileSystemEventHandler):
                def __init__(handler_self, watcher):
                    handler_self.watcher = watcher

                def _should_ignore(handler_self, path: str) -> bool:
                    for pattern in handler_self.watcher.ignore_patterns:
                        if pattern.replace("*", "") in path:
                            return True
                    return False

                def _create_signal(handler_self, event, signal_type: SignalType) -> Optional[Signal]:
                    if handler_self._should_ignore(event.src_path):
                        return None
                    
                    import uuid
                    return Signal(
                        id=f"sig_{uuid.uuid4().hex[:8]}",
                        type=signal_type,
                        timestamp=datetime.now(),
                        source="file_watcher",
                        payload={"path": event.src_path, "is_directory": event.is_directory},
                        project=handler_self.watcher._detect_project(event.src_path),
                    )

                def on_created(handler_self, event):
                    signal = handler_self._create_signal(event, SignalType.FILE_CREATED)
                    if signal:
                        handler_self.watcher._signals.append(signal)

                def on_modified(handler_self, event):
                    if not event.is_directory:
                        signal = handler_self._create_signal(event, SignalType.FILE_MODIFIED)
                        if signal:
                            handler_self.watcher._signals.append(signal)

                def on_deleted(handler_self, event):
                    signal = handler_self._create_signal(event, SignalType.FILE_DELETED)
                    if signal:
                        handler_self.watcher._signals.append(signal)

            self._observer = Observer()
            handler = SignalHandler(self)
            
            for path in self.watch_paths:
                if path.exists():
                    self._observer.schedule(handler, str(path), recursive=True)
            
            self._observer.start()
            self._running = True
            logger.info(f"FileWatcher started for {len(self.watch_paths)} paths")

        except ImportError:
            logger.warning("watchdog not installed, FileWatcher disabled")
            self._running = False

    def stop(self) -> None:
        """Stop filesystem monitoring."""
        if self._observer:
            self._observer.stop()
            self._observer.join()
        self._running = False
        logger.info("FileWatcher stopped")

    def get_signals(self) -> List[Signal]:
        """Get pending filesystem signals."""
        signals = self._signals.copy()
        self._signals.clear()
        return signals

    @property
    def is_running(self) -> bool:
        return self._running

    def _detect_project(self, path: str) -> Optional[str]:
        """Detect project from file path."""
        path_obj = Path(path)
        for watch_path in self.watch_paths:
            if str(path_obj).startswith(str(watch_path)):
                # Project is first directory under watch path
                relative = path_obj.relative_to(watch_path)
                parts = relative.parts
                if parts:
                    return parts[0]
        return None


class ShellListener(SignalSource):
    """
    Capture terminal history and exit codes.
    
    Monitors shell history files for new commands.
    """

    def __init__(self, history_file: Optional[Path] = None):
        self.history_file = history_file or Path.home() / ".zsh_history"
        self._last_position = 0
        self._running = False
        self._signals: List[Signal] = []

    @property
    def name(self) -> str:
        return "ShellListener"

    def start(self) -> None:
        """Start monitoring shell history."""
        if self.history_file.exists():
            self._last_position = self.history_file.stat().st_size
        self._running = True
        logger.info(f"ShellListener started, monitoring {self.history_file}")

    def stop(self) -> None:
        """Stop monitoring shell history."""
        self._running = False
        logger.info("ShellListener stopped")

    def get_signals(self) -> List[Signal]:
        """Get new shell commands since last check."""
        signals = []
        
        if not self.history_file.exists():
            return signals

        try:
            current_size = self.history_file.stat().st_size
            if current_size > self._last_position:
                with open(self.history_file, "rb") as f:
                    f.seek(self._last_position)
                    new_content = f.read().decode("utf-8", errors="ignore")
                
                import uuid
                for line in new_content.strip().split("\n"):
                    if line.strip():
                        # Parse zsh history format: : timestamp:0;command
                        command = line.split(";", 1)[-1] if ";" in line else line
                        signals.append(Signal(
                            id=f"sig_{uuid.uuid4().hex[:8]}",
                            type=SignalType.COMMAND_EXECUTED,
                            timestamp=datetime.now(),
                            source="shell_listener",
                            payload={"command": command.strip()},
                        ))
                
                self._last_position = current_size

        except Exception as e:
            logger.warning(f"Error reading shell history: {e}")

        return signals

    @property
    def is_running(self) -> bool:
        return self._running


class IDEBridge(SignalSource):
    """
    Receive signals from IDE via MCP.
    
    Connects to MCP server to receive IDE events.
    """

    def __init__(self, mcp_endpoint: str = "localhost:3000"):
        self.mcp_endpoint = mcp_endpoint
        self._running = False
        self._signals: List[Signal] = []
        self._callback: Optional[Callable] = None

    @property
    def name(self) -> str:
        return "IDEBridge"

    def start(self) -> None:
        """Start MCP connection."""
        # MCP integration happens via mcp_server.py
        # This receives signals when MCP tools are called
        self._running = True
        logger.info(f"IDEBridge ready to receive MCP signals")

    def stop(self) -> None:
        """Stop MCP connection."""
        self._running = False

    def get_signals(self) -> List[Signal]:
        """Get IDE signals from MCP."""
        signals = self._signals.copy()
        self._signals.clear()
        return signals

    def inject_signal(self, signal: Signal) -> None:
        """Inject a signal from external source (e.g., MCP server)."""
        self._signals.append(signal)

    @property
    def is_running(self) -> bool:
        return self._running


class ContextAbsorber:
    """
    Engine A: Aggregates signals from all sources.
    
    This is the input layer of Cortex V2 Prime.
    Collects signals from FileWatcher, ShellListener, IDEBridge, and GitTracker.
    """

    def __init__(self, root_dir: Path, storage_path: Optional[Path] = None):
        self.root_dir = root_dir
        self.storage_path = storage_path or Path.home() / ".cortex" / "signals.json"
        self.sources: List[SignalSource] = []
        self._signal_buffer: List[Signal] = []
        self._callbacks: List[Callable[[Signal], None]] = []

    def register_source(self, source: SignalSource) -> None:
        """Register a signal source."""
        self.sources.append(source)
        logger.info(f"Registered signal source: {source.name}")

    def register_callback(self, callback: Callable[[Signal], None]) -> None:
        """Register callback for new signals."""
        self._callbacks.append(callback)

    def start_all(self) -> None:
        """Start all signal sources."""
        for source in self.sources:
            try:
                source.start()
            except Exception as e:
                logger.error(f"Failed to start {source.name}: {e}")

    def stop_all(self) -> None:
        """Stop all signal sources."""
        for source in self.sources:
            try:
                source.stop()
            except Exception as e:
                logger.error(f"Failed to stop {source.name}: {e}")

    def absorb(self) -> List[Signal]:
        """
        Collect signals from all sources.
        
        Returns list of new signals since last call.
        """
        signals = []
        for source in self.sources:
            try:
                source_signals = source.get_signals()
                signals.extend(source_signals)
            except Exception as e:
                logger.error(f"Error getting signals from {source.name}: {e}")

        # Sort by timestamp
        signals.sort(key=lambda s: s.timestamp)

        # Buffer for Synthesis Core
        self._signal_buffer.extend(signals)

        # Notify callbacks
        for signal in signals:
            for callback in self._callbacks:
                try:
                    callback(signal)
                except Exception as e:
                    logger.error(f"Callback error: {e}")

        # Persist signals
        self._persist_signals(signals)

        return signals

    def get_buffer(self) -> List[Signal]:
        """Get buffered signals for Synthesis Core."""
        buffer = self._signal_buffer.copy()
        self._signal_buffer.clear()
        return buffer

    def get_recent_signals(self, limit: int = 100, signal_type: Optional[SignalType] = None) -> List[Signal]:
        """Get recent signals from storage."""
        signals = self._load_signals()
        
        if signal_type:
            signals = [s for s in signals if s.type == signal_type]
        
        return signals[-limit:]

    def _persist_signals(self, signals: List[Signal]) -> None:
        """Persist signals to storage."""
        if not signals:
            return

        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            
            existing = self._load_signals()
            existing.extend(signals)
            
            # Keep last 10000 signals
            if len(existing) > 10000:
                existing = existing[-10000:]
            
            with open(self.storage_path, "w") as f:
                json.dump([s.to_dict() for s in existing], f)

        except Exception as e:
            logger.error(f"Failed to persist signals: {e}")

    def _load_signals(self) -> List[Signal]:
        """Load signals from storage."""
        if not self.storage_path.exists():
            return []

        try:
            with open(self.storage_path) as f:
                data = json.load(f)
                return [Signal.from_dict(s) for s in data]
        except Exception as e:
            logger.error(f"Failed to load signals: {e}")
            return []

    def get_status(self) -> Dict[str, Any]:
        """Get absorber status."""
        return {
            "sources": [
                {"name": s.name, "running": s.is_running}
                for s in self.sources
            ],
            "buffer_size": len(self._signal_buffer),
            "total_signals": len(self._load_signals()),
            "storage_path": str(self.storage_path),
        }


def create_default_absorber(root_dir: Path) -> ContextAbsorber:
    """Create absorber with default sources configured."""
    absorber = ContextAbsorber(root_dir)
    
    # Add FileWatcher for Dev directory
    absorber.register_source(FileWatcher([root_dir]))
    
    # Add ShellListener
    absorber.register_source(ShellListener())
    
    # Add IDEBridge for MCP
    absorber.register_source(IDEBridge())
    
    return absorber
