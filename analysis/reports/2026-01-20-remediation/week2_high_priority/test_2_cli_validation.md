# test_2_cli_validation

# Implementation Plan: Add Input Validation to CLI Commands

## Executive Summary

This implementation adds comprehensive input validation to the Cortex CLI to prevent injection attacks, path traversal vulnerabilities, and ensure data integrity. The solution includes a reusable validation module, updated CLI commands, and a complete test suite.

## 1. New Validation Module

### File: `cortex/validation.py`

```python
"""
Input validation utilities for Cortex CLI.

This module provides comprehensive validation for all user inputs to prevent
injection attacks, path traversal, and other security vulnerabilities.
"""

import re
import os
from pathlib import Path
from typing import Optional, List, Union, Callable, Any
from dataclasses import dataclass
from enum import Enum
import shlex


class ValidationError(Exception):
    """Raised when input validation fails."""
    
    def __init__(self, message: str, field: str = None, value: Any = None):
        self.message = message
        self.field = field
        self.value = value
        super().__init__(self.format_message())
    
    def format_message(self) -> str:
        """Format error message with context."""
        parts = []
        if self.field:
            parts.append(f"Field '{self.field}'")
        parts.append(self.message)
        if self.value is not None:
            # Truncate long values for display
            display_value = str(self.value)
            if len(display_value) > 50:
                display_value = display_value[:47] + "..."
            parts.append(f"(got: {display_value!r})")
        return ": ".join(parts) if len(parts) > 1 else parts[0]


class ValidationType(Enum):
    """Types of validation that can be applied."""
    PROJECT_NAME = "project_name"
    FILE_PATH = "file_path"
    DIRECTORY_PATH = "directory_path"
    COMMAND = "command"
    IDENTIFIER = "identifier"
    URL = "url"
    VERSION = "version"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    CHOICE = "choice"


@dataclass
class ValidationResult:
    """Result of a validation operation."""
    is_valid: bool
    value: Any  # The validated/sanitized value
    error: Optional[str] = None
    warnings: List[str] = None
    
    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


class InputValidator:
    """
    Comprehensive input validator for CLI arguments.
    
    Usage:
        validator = InputValidator()
        
        # Validate a project name
        result = validator.validate_project_name("my-project")
        if not result.is_valid:
            raise ValidationError(result.error)
        
        # Validate a file path
        result = validator.validate_file_path("/path/to/file.py")
    """
    
    # Pattern constants
    PROJECT_NAME_PATTERN = re.compile(r'^[a-zA-Z][a-zA-Z0-9_-]{0,63}$')
    IDENTIFIER_PATTERN = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]{0,127}$')
    VERSION_PATTERN = re.compile(r'^v?\d+\.\d+(\.\d+)?(-[a-zA-Z0-9.]+)?(\+[a-zA-Z0-9.]+)?$')
    URL_PATTERN = re.compile(
        r'^https?://'
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'
        r'localhost|'
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
        r'(?::\d+)?'
        r'(?:/?|[/?]\S+)$',
        re.IGNORECASE
    )
    
    # Dangerous patterns for path traversal
    PATH_TRAVERSAL_PATTERNS = [
        r'\.\.',           # Parent directory
        r'^/',             # Absolute paths (when relative expected)
        r'^~',             # Home directory expansion
        r'\$\{',           # Variable expansion
        r'\$\(',           # Command substitution
        r'`',              # Backtick command substitution
        r'\x00',           # Null bytes
        r'[\r\n]',         # Newlines (could be used for log injection)
    ]
    
    # Shell injection patterns
    SHELL_INJECTION_PATTERNS = [
        r'[;&|]',          # Command chaining
        r'\$\(',           # Command substitution
        r'`',              # Backtick substitution
        r'\|',             # Pipe
        r'<',              # Input redirection
        r'>',              # Output redirection
        r'\x00',           # Null bytes
    ]
    
    # Reserved names (Windows and common)
    RESERVED_NAMES = {
        'con', 'prn', 'aux', 'nul',
        'com1', 'com2', 'com3', 'com4', 'com5', 'com6', 'com7', 'com8', 'com9',
        'lpt1', 'lpt2', 'lpt3', 'lpt4', 'lpt5', 'lpt6', 'lpt7', 'lpt8', 'lpt9',
    }
    
    def __init__(self, 
                 max_path_length: int = 4096,
                 max_name_length: int = 64,
                 allowed_extensions: Optional[List[str]] = None,
                 base_directory: Optional[Path] = None):
        """
        Initialize validator with configuration.
        
        Args:
            max_path_length: Maximum allowed path length
            max_name_length: Maximum allowed name length
            allowed_extensions: List of allowed file extensions (e.g., ['.py', '.yaml'])
            base_directory: Base directory for path validation (prevents traversal outside)
        """
        self.max_path_length = max_path_length
        self.max_name_length = max_name_length
        self.allowed_extensions = allowed_extensions
        self.base_directory = Path(base_directory).resolve() if base_directory else None
    
    def validate_project_name(self, name: str, field: str = "project_name") -> ValidationResult:
        """
        Validate a project name.
        
        Rules:
        - Must start with a letter
        - Can contain letters, numbers, underscores, and hyphens
        - Length: 1-64 characters
        - Cannot be a reserved name
        
        Args:
            name: The project name to validate
            field: Field name for error messages
            
        Returns:
            ValidationResult with validated name or error
        """
        warnings = []
        
        # Check for None or empty
        if not name:
            return ValidationResult(
                is_valid=False,
                value=None,
                error=f"{field} cannot be empty"
            )
        
        # Type check
        if not isinstance(name, str):
            return ValidationResult(
                is_valid=False,
                value=None,
                error=f"{field} must be a string, got {type(name).__name__}"
            )
        
        # Strip whitespace and check
        name = name.strip()
        if not name:
            return ValidationResult(
                is_valid=False,
                value=None,
                error=f"{field} cannot be empty or whitespace only"
            )
        
        # Length check
        if len(name) > self.max_name_length:
            return ValidationResult(
                is_valid=False,
                value=None,
                error=f"{field} exceeds maximum length of {self.max_name_length} characters"
            )
        
        # Pattern check
        if not self.PROJECT_NAME_PATTERN.match(name):
            return ValidationResult(
                is_valid=False,
                value=None,
                error=f"{field} must start with a letter and contain only letters, "
                      f"numbers, underscores, and hyphens"
            )
        
        # Reserved name check
        if name.lower() in self.RESERVED_NAMES:
            return ValidationResult(
                is_valid=False,
                value=None,
                error=f"{field} '{name}' is a reserved name"
            )
        
        # Check for potential issues (warnings, not errors)
        if name.startswith('_'):
            warnings.append(f"Project names starting with underscore may be hidden in some systems")
        
        if name.lower() != name:
            warnings.append(f"Consider using lowercase for better cross-platform compatibility")
        
        return ValidationResult(
            is_valid=True,
            value=name,
            warnings=warnings
        )
    
    def validate_file_path(self, 
                          path: str, 
                          field: str = "file_path",
                          must_exist: bool = False,
                          allow_absolute: bool = True,
                          check_extension: bool = True) -> ValidationResult:
        """
        Validate a file path for security issues.
        
        Checks for:
        - Path traversal attacks (../)
        - Null bytes
        - Command injection
        - Length limits
        - Extension restrictions (if configured)
        
        Args:
            path: The path to validate
            field: Field name for error messages
            must_exist: If True, verify the path exists
            allow_absolute: If True, allow absolute paths
            check_extension: If True, check against allowed_extensions
            
        Returns:
            ValidationResult with resolved path or error
        """
        warnings = []
        
        # Check for None or empty
        if not path:
            return ValidationResult(
                is_valid=False,
                value=None,
                error=f"{field} cannot be empty"
            )
        
        # Type check
        if not isinstance(path, str):
            return ValidationResult(
                is_valid=False,
                value=None,
                error=f"{field} must be a string, got {type(name).__name__}"
            )
        
        # Length check
        if len(path) > self.max_path_length:
            return ValidationResult(
                is_valid=False,
                value=None,
                error=f"{field} exceeds maximum length of {self.max_path_length} characters"
            )
        
        # Check for null bytes (critical security issue)
        if '\x00' in path:
            return ValidationResult(
                is_valid=False,
                value=None,
                error=f"{field} contains null bytes (potential injection attack)"
            )
        
        # Check for newlines (log injection)
        if '\n' in path or '\r' in path:
            return ValidationResult(
                is_valid=False,
                value=None,
                error=f"{field} contains newline characters"
            )
        
        # Check for command substitution attempts
        dangerous_patterns = [r'\$\(', r'`', r'\$\{']
        for pattern in dangerous_patterns:
            if re.search(pattern, path):
                return ValidationResult(
                    is_valid=False,
                    value=None,
                    error=f"{field} contains potentially dangerous characters"
                )
        
        # Convert to Path object for safer handling
        try:
            path_obj = Path(path)
        except (ValueError, OSError) as e:
            return ValidationResult(
                is_valid=False,
                value=None,
                error=f"{field} is not a valid path: {e}"
            )
        
        # Check for absolute path if not allowed
        if not allow_absolute and path_obj.is_absolute():
            return ValidationResult(
                is_valid=False,
                value=None,
                error=f"{field} must be a relative path"
            )
        
        # Check for path traversal
        if '..' in path_obj.parts:
            return ValidationResult(
                is_valid=False,
                value=None,
                error=f"{field} contains path traversal sequence (..)"
            )
        
        # Resolve the path and check it stays within base directory
        try:
            resolved = path_obj.resolve()
            
            if self.base_directory:
                try:
                    resolved.relative_to(self.base_directory)
                except ValueError:
                    return ValidationResult(
                        is_valid=False,
                        value=None,
                        error=f"{field} resolves outside allowed directory"
                    )
        except (OSError, RuntimeError) as e:
            return ValidationResult(
                is_valid=False,
                value=None,
                error=f"{field} cannot be resolved: {e}"
            )
        
        # Check extension if configured
        if check_extension and self.allowed_extensions:
            if path_obj.suffix.lower() not in [ext.lower() for ext in self.allowed_extensions]:
                return ValidationResult(
                    is_valid=False,
                    value=None,
                    error=f"{field} has invalid extension. Allowed: {', '.join(self.allowed_extensions)}"
                )
        
        # Check existence if required
        if must_exist and not resolved.exists():
            return ValidationResult(
                is_valid=False,
                value=None,
                error=f"{field} does not exist: {path}"
            )
        
        # Check for reserved names in path components (Windows compatibility)
        for part in path_obj.parts:
            name_without_ext = Path(part).stem.lower()
            if name_without_ext in self.RESERVED_NAMES:
                warnings.append(f"Path contains Windows reserved name: {part}")
        
        return ValidationResult(
            is_valid=True,
            value=str(resolved),
            warnings=warnings
        )
    
    def validate_directory_path(self,
                               path: str,
                               field: str = "directory_path",
                               must_exist: bool = False,
                               allow_creation: bool = True,
                               allow_absolute: bool = True) -> ValidationResult:
        """
        Validate a directory path.
        
        Args:
            path: The directory path to validate
            field: Field name for error messages
            must_exist: If True, directory must exist
            allow_creation: If True, allow paths that could be created
            allow_absolute: If True, allow absolute paths
            
        Returns:
            ValidationResult with resolved path or error
        """
        # First, validate as a generic path
        result = self.validate_file_path(
            path, 
            field=field, 
            must_exist=False,
            allow_absolute=allow_absolute,
            check_extension=False
        )
        
        if not result.is_valid:
            return result
        
        resolved = Path(result.value)
        
        # Check if exists and is a directory
        if resolved.exists():
            if not resolved.is_dir():
                return ValidationResult(
                    is_valid=False,
                    value=None,
                    error=f"{field} exists but is not a directory"
                )
        elif must_exist:
            return ValidationResult(
                is_valid=False,
                value=None,
                error=f"{field} directory does not exist: {path}"
            )
        elif not allow_creation:
            return ValidationResult(
                is_valid=False,
                value=None,
                error=f"{field} directory does not exist and creation is not allowed"
            )
        
        return ValidationResult(
            is_valid=True,
            value=str(resolved),
            warnings=result.warnings
        )
    
    def validate_identifier(self, 
                           name: str, 
                           field: str = "identifier") -> ValidationResult:
        """
        Validate a Python-style identifier.
        
        Rules:
        - Must start with a letter