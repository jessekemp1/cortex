# security_4_config_permissions

# Config File Permissions Fix - Implementation Plan

## Overview

This implementation adds proper permission enforcement (mode 600/700) for sensitive configuration files and directories in the Cortex CLI tool.

## Analysis of Current Code

Based on typical patterns, I'll provide a comprehensive solution that:
1. Enforces permissions when creating config files
2. Checks permissions on load with warnings
3. Applies the same pattern to all sensitive files

---

## Implementation

### 1. New Security Module: `cortex/security.py`

```python
"""
cortex/security.py - File permission security utilities

This module provides utilities for enforcing secure file permissions
on sensitive configuration files and directories.
"""

import os
import stat
import warnings
from pathlib import Path
from typing import Optional, Union
import logging

logger = logging.getLogger(__name__)

# Secure permission modes
SECURE_FILE_MODE = 0o600  # rw-------
SECURE_DIR_MODE = 0o700   # rwx------

# Maximum permissive modes (anything more permissive triggers warning)
MAX_PERMISSIVE_FILE_MODE = 0o600
MAX_PERMISSIVE_DIR_MODE = 0o700


class PermissionWarning(UserWarning):
    """Warning raised when file permissions are too permissive."""
    pass


class PermissionError(Exception):
    """Exception raised when permission operations fail."""
    pass


def get_file_permissions(path: Union[str, Path]) -> int:
    """
    Get the current permission bits for a file or directory.
    
    Args:
        path: Path to the file or directory
        
    Returns:
        Permission bits as an integer (e.g., 0o644)
        
    Raises:
        FileNotFoundError: If path doesn't exist
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Path does not exist: {path}")
    
    return stat.S_IMODE(path.stat().st_mode)


def is_permission_secure(path: Union[str, Path], is_directory: bool = False) -> bool:
    """
    Check if a file or directory has secure permissions.
    
    Secure means:
    - Files: mode 600 or more restrictive (no group/other access)
    - Directories: mode 700 or more restrictive (no group/other access)
    
    Args:
        path: Path to check
        is_directory: Whether the path is a directory
        
    Returns:
        True if permissions are secure, False otherwise
    """
    try:
        current_mode = get_file_permissions(path)
    except FileNotFoundError:
        return True  # Non-existent files are "secure"
    
    # Check if group or other have any permissions
    group_other_bits = current_mode & 0o077
    return group_other_bits == 0


def get_permission_string(mode: int) -> str:
    """
    Convert permission bits to a human-readable string.
    
    Args:
        mode: Permission bits (e.g., 0o644)
        
    Returns:
        String like "644" or "rwxr-xr-x"
    """
    return oct(mode)[2:]  # Remove '0o' prefix


def set_secure_permissions(
    path: Union[str, Path], 
    is_directory: bool = False,
    mode: Optional[int] = None
) -> None:
    """
    Set secure permissions on a file or directory.
    
    Args:
        path: Path to secure
        is_directory: Whether the path is a directory
        mode: Specific mode to set (defaults to SECURE_FILE_MODE or SECURE_DIR_MODE)
        
    Raises:
        PermissionError: If unable to set permissions
    """
    path = Path(path)
    
    if mode is None:
        mode = SECURE_DIR_MODE if is_directory else SECURE_FILE_MODE
    
    try:
        os.chmod(path, mode)
        logger.debug(f"Set permissions {get_permission_string(mode)} on {path}")
    except OSError as e:
        raise PermissionError(f"Failed to set permissions on {path}: {e}")


def check_and_warn_permissions(
    path: Union[str, Path],
    is_directory: bool = False,
    fix: bool = False
) -> bool:
    """
    Check file permissions and warn if too permissive.
    
    Args:
        path: Path to check
        is_directory: Whether the path is a directory
        fix: If True, automatically fix insecure permissions
        
    Returns:
        True if permissions are secure (or were fixed), False otherwise
    """
    path = Path(path)
    
    if not path.exists():
        return True
    
    if is_permission_secure(path, is_directory):
        return True
    
    current_mode = get_file_permissions(path)
    expected_mode = SECURE_DIR_MODE if is_directory else SECURE_FILE_MODE
    
    warning_msg = (
        f"Insecure permissions {get_permission_string(current_mode)} on {path}. "
        f"Expected {get_permission_string(expected_mode)} or more restrictive. "
        f"This file may contain sensitive data."
    )
    
    if fix:
        try:
            set_secure_permissions(path, is_directory)
            logger.warning(
                f"{warning_msg} Permissions have been automatically fixed."
            )
            return True
        except PermissionError as e:
            logger.error(f"Could not fix permissions: {e}")
            warnings.warn(warning_msg, PermissionWarning, stacklevel=2)
            return False
    else:
        fix_hint = (
            f"\nTo fix, run: chmod {get_permission_string(expected_mode)} {path}"
        )
        warnings.warn(warning_msg + fix_hint, PermissionWarning, stacklevel=2)
        return False


def secure_create_file(
    path: Union[str, Path],
    content: str = "",
    mode: int = SECURE_FILE_MODE
) -> Path:
    """
    Securely create a file with proper permissions.
    
    This function creates the file with secure permissions atomically,
    preventing race conditions where the file might be readable by
    others between creation and chmod.
    
    Args:
        path: Path to create
        content: Initial content for the file
        mode: Permission mode (default: 600)
        
    Returns:
        Path object for the created file
    """
    path = Path(path)
    
    # Ensure parent directory exists with secure permissions
    parent = path.parent
    if not parent.exists():
        secure_create_directory(parent)
    
    # Create file with secure permissions using os.open for atomicity
    fd = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
        mode
    )
    
    try:
        if content:
            os.write(fd, content.encode('utf-8'))
    finally:
        os.close(fd)
    
    logger.debug(f"Securely created file {path} with mode {get_permission_string(mode)}")
    return path


def secure_create_directory(
    path: Union[str, Path],
    mode: int = SECURE_DIR_MODE,
    parents: bool = True
) -> Path:
    """
    Securely create a directory with proper permissions.
    
    Args:
        path: Path to create
        mode: Permission mode (default: 700)
        parents: Create parent directories if needed
        
    Returns:
        Path object for the created directory
    """
    path = Path(path)
    
    if path.exists():
        # Check and fix existing directory permissions
        check_and_warn_permissions(path, is_directory=True, fix=True)
        return path
    
    # Save current umask and set restrictive umask
    old_umask = os.umask(0o077)
    
    try:
        path.mkdir(mode=mode, parents=parents, exist_ok=True)
        # Explicitly set permissions (mkdir's mode is affected by umask)
        os.chmod(path, mode)
    finally:
        os.umask(old_umask)
    
    logger.debug(f"Securely created directory {path} with mode {get_permission_string(mode)}")
    return path


def secure_write_file(
    path: Union[str, Path],
    content: str,
    mode: int = SECURE_FILE_MODE
) -> None:
    """
    Securely write content to a file, preserving or setting secure permissions.
    
    Uses atomic write (write to temp, then rename) to prevent corruption.
    
    Args:
        path: Path to write to
        content: Content to write
        mode: Permission mode for new files (default: 600)
    """
    path = Path(path)
    temp_path = path.with_suffix(path.suffix + '.tmp')
    
    # Ensure parent directory exists
    if not path.parent.exists():
        secure_create_directory(path.parent)
    
    # Write to temp file with secure permissions
    secure_create_file(temp_path, content, mode)
    
    # Atomic rename
    temp_path.rename(path)
    
    logger.debug(f"Securely wrote to {path}")


def audit_cortex_directory(
    cortex_dir: Union[str, Path],
    fix: bool = False
) -> dict:
    """
    Audit all files in the Cortex configuration directory.
    
    Args:
        cortex_dir: Path to ~/.cortex or similar
        fix: If True, automatically fix insecure permissions
        
    Returns:
        Dictionary with audit results
    """
    cortex_dir = Path(cortex_dir)
    results = {
        'checked': 0,
        'secure': 0,
        'insecure': [],
        'fixed': [],
        'errors': []
    }
    
    if not cortex_dir.exists():
        return results
    
    # Check main directory
    results['checked'] += 1
    if is_permission_secure(cortex_dir, is_directory=True):
        results['secure'] += 1
    else:
        if fix:
            try:
                set_secure_permissions(cortex_dir, is_directory=True)
                results['fixed'].append(str(cortex_dir))
            except PermissionError as e:
                results['errors'].append(str(e))
        else:
            results['insecure'].append(str(cortex_dir))
    
    # Walk through all files and directories
    for item in cortex_dir.rglob('*'):
        results['checked'] += 1
        is_dir = item.is_dir()
        
        if is_permission_secure(item, is_directory=is_dir):
            results['secure'] += 1
        else:
            if fix:
                try:
                    set_secure_permissions(item, is_directory=is_dir)
                    results['fixed'].append(str(item))
                except PermissionError as e:
                    results['errors'].append(str(e))
            else:
                results['insecure'].append(str(item))
    
    return results
```

---

### 2. Updated Config Module: `cortex/config.py`

```python
"""
cortex/config.py - Configuration management with secure file handling

Before (INSECURE):
    def save_config(self, config: dict) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, 'w') as f:
            yaml.safe_dump(config, f)

After (SECURE):
    Uses secure file creation with proper permissions
"""

import os
import yaml
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Union

from .security import (
    secure_create_directory,
    secure_create_file,
    secure_write_file,
    check_and_warn_permissions,
    is_permission_secure,
    SECURE_FILE_MODE,
    SECURE_DIR_MODE,
    PermissionWarning
)

logger = logging.getLogger(__name__)

# Default configuration directory
DEFAULT_CONFIG_DIR = Path.home() / '.cortex'
DEFAULT_CONFIG_FILE = 'config.yaml'

# Sensitive subdirectories that need secure permissions
SENSITIVE_SUBDIRS = [
    'batches',
    'cache',
    'credentials',
    'sessions',
]


class ConfigManager:
    """
    Manages Cortex configuration with secure file handling.
    
    All configuration files are created with mode 600 (rw-------).
    All configuration directories are created with mode 700 (rwx------).
    """
    
    def __init__(
        self,
        config_dir: Optional[Union[str, Path]] = None,
        auto_fix_permissions: bool = True
    ):
        """
        Initialize the configuration manager.
        
        Args:
            config_dir: Custom configuration directory (default: ~/.cortex)
            auto_fix_permissions: Automatically fix insecure permissions
        """
        self.config_dir = Path(config_dir) if config_dir else DEFAULT_CONFIG_DIR
        self.config_path = self.config_dir / DEFAULT_CONFIG_FILE
        self.auto_fix_permissions = auto_fix_permissions
        self._config_cache: Optional[Dict[str, Any]] = None
        
    def _ensure_config_dir(self) -> None:
        """Ensure the configuration directory exists with secure permissions."""
        secure_create_directory(self.config_dir)
        
        # Create sensitive subdirectories
        for subdir in SENSITIVE_SUBDIRS:
            subdir_path = self.config_dir / subdir
            if subdir_path.exists():
                check_and_warn_permissions(
                    subdir_path, 
                    is_directory=True, 
                    fix=self.auto_fix_permissions
                )
            # Don't create subdirs until needed
    
    def _check_config_permissions(self) -> bool:
        """
        Check configuration file permissions and warn if insecure.
        
        Returns:
            True if permissions are secure
        """
        # Check directory
        if self.config_dir.exists():
            check_and_warn_permissions(
                self.config_dir,
                is_directory=True,
                fix=self.auto_fix_permissions
            )
        
        # Check config file
        if self.config_path.exists():
            return check_and_warn_permissions(
                self.config_path,
                is_directory=False,
                fix=self.auto_fix_permissions
            )
        
        return True
    
    def load(self, check_permissions: bool = True) -> Dict[str, Any]:
        """
        Load configuration from file.
        
        Args:
            check_permissions: Whether to check file permissions
            
        Returns:
            Configuration dictionary
        """
        if check_permissions:
            self._check_config_permissions()
        
        if not self.config_path.exists():
            logger.debug(f"Config file not found: {self.config_path}")
            return {}
        
        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f) or {}
                self._config_cache = config
                return config
        except yaml.YAMLError as e:
            logger.error(f"Failed to parse config file: {e}")
            raise
        except IOError as e:
            logger.error(f"Failed to read config file: {e}")
            raise
    
    def save(self, config: Dict[str, Any]) -> None:
        """
        Save configuration to file with secure permissions.
        
        Args:
            config: Configuration dictionary to save
        """
        self._ensure_config_dir()
        
        # Serialize to YAML
        content = yaml.safe_dump(config, default_flow_style=False