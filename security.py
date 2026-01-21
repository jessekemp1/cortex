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
        String like "644" or "600"
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
    Create a file with secure permissions atomically.

    Args:
        path: Path to the file to create
        content: Content to write to the file
        mode: Permission mode to set (default: 600)

    Returns:
        Path object for the created file

    Raises:
        PermissionError: If unable to create file or set permissions
    """
    path = Path(path)

    try:
        # Create parent directories if needed
        path.parent.mkdir(parents=True, exist_ok=True)

        # Create file with secure permissions
        # Use os.open with mode to create file atomically with correct permissions
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
        try:
            os.write(fd, content.encode('utf-8'))
        finally:
            os.close(fd)

        logger.debug(f"Created secure file {path} with mode {get_permission_string(mode)}")
        return path

    except FileExistsError:
        # File already exists - write content and fix permissions
        path.write_text(content, encoding='utf-8')
        set_secure_permissions(path, is_directory=False, mode=mode)
        return path

    except OSError as e:
        raise PermissionError(f"Failed to create secure file {path}: {e}")


def secure_create_directory(
    path: Union[str, Path],
    mode: int = SECURE_DIR_MODE
) -> Path:
    """
    Create a directory with secure permissions.

    Args:
        path: Path to the directory to create
        mode: Permission mode to set (default: 700)

    Returns:
        Path object for the created directory

    Raises:
        PermissionError: If unable to create directory or set permissions
    """
    path = Path(path)

    try:
        path.mkdir(parents=True, exist_ok=True, mode=mode)
        # Ensure permissions are set correctly (mkdir mode can be affected by umask)
        set_secure_permissions(path, is_directory=True, mode=mode)
        logger.debug(f"Created secure directory {path} with mode {get_permission_string(mode)}")
        return path
    except OSError as e:
        raise PermissionError(f"Failed to create secure directory {path}: {e}")


def secure_config_directory(config_dir: Union[str, Path]) -> bool:
    """
    Secure all files in a configuration directory.

    Args:
        config_dir: Path to the configuration directory

    Returns:
        True if all files were secured successfully, False otherwise
    """
    config_dir = Path(config_dir)

    if not config_dir.exists():
        return True

    success = True

    # Secure the directory itself
    if not is_permission_secure(config_dir, is_directory=True):
        try:
            set_secure_permissions(config_dir, is_directory=True)
        except PermissionError:
            success = False

    # Secure all files in the directory
    for item in config_dir.rglob('*'):
        if item.is_file():
            # Skip hidden system files
            if item.name.startswith('.') and item.name in {'.DS_Store', '.gitkeep'}:
                continue

            if not is_permission_secure(item, is_directory=False):
                try:
                    set_secure_permissions(item, is_directory=False)
                except PermissionError:
                    success = False
        elif item.is_dir():
            if not is_permission_secure(item, is_directory=True):
                try:
                    set_secure_permissions(item, is_directory=True)
                except PermissionError:
                    success = False

    return success
