"""
CLI Input Validation Module for Cortex

This module provides comprehensive input validation for CLI arguments to prevent
security vulnerabilities and ensure data integrity. It validates project names,
file paths, directory paths, and identifiers against security patterns and
application requirements.

Security Features:
    - Path traversal attack detection
    - Command injection prevention
    - SQL injection pattern detection
    - Reserved name validation
    - Length and character set restrictions

Example:
    >>> from cortex.validation import InputValidator, ValidationType
    >>> validator = InputValidator()
    >>> result = validator.validate_project_name("my-project")
    >>> if result.is_valid:
    ...     print(f"Valid project name: {result.sanitized_value}")
"""

import re
import os
from enum import Enum
from dataclasses import dataclass
from typing import List, Optional, Pattern, Set
from pathlib import Path


class ValidationType(Enum):
    """Enumeration of validation types for categorizing validation results."""
    
    PROJECT_NAME = "project_name"
    FILE_PATH = "file_path"
    DIRECTORY_PATH = "directory_path"
    IDENTIFIER = "identifier"
    GENERIC = "generic"


@dataclass
class ValidationResult:
    """
    Result of an input validation operation.
    
    Attributes:
        is_valid: Whether the input passed validation
        validation_type: Type of validation performed
        original_value: The original input value
        sanitized_value: Cleaned/sanitized version of the input (if valid)
        errors: List of validation error messages
        warnings: List of non-critical warnings
    """
    
    is_valid: bool
    validation_type: ValidationType
    original_value: str
    sanitized_value: Optional[str] = None
    errors: List[str] = None
    warnings: List[str] = None
    
    def __post_init__(self):
        """Initialize mutable default values."""
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []
    
    def add_error(self, error: str) -> None:
        """Add an error message to the result."""
        self.errors.append(error)
        self.is_valid = False
    
    def add_warning(self, warning: str) -> None:
        """Add a warning message to the result."""
        self.warnings.append(warning)


class ValidationError(Exception):
    """
    Exception raised when input validation fails.
    
    Attributes:
        message: Description of the validation failure
        validation_type: Type of validation that failed
        original_value: The input value that failed validation
        errors: List of specific validation errors
    """
    
    def __init__(
        self,
        message: str,
        validation_type: ValidationType,
        original_value: str,
        errors: Optional[List[str]] = None
    ):
        """
        Initialize ValidationError.
        
        Args:
            message: Main error message
            validation_type: Type of validation that failed
            original_value: The input that failed validation
            errors: List of specific validation errors
        """
        super().__init__(message)
        self.message = message
        self.validation_type = validation_type
        self.original_value = original_value
        self.errors = errors or []
    
    def __str__(self) -> str:
        """Return formatted error message."""
        base_msg = f"{self.message} (type: {self.validation_type.value})"
        if self.errors:
            base_msg += f"\nErrors: {', '.join(self.errors)}"
        return base_msg


class InputValidator:
    """
    Comprehensive input validator for CLI arguments.
    
    This class provides validation methods for various input types with
    security pattern detection and sanitization capabilities.
    
    Attributes:
        MAX_PROJECT_NAME_LENGTH: Maximum allowed length for project names
        MAX_PATH_LENGTH: Maximum allowed length for file paths
        MAX_IDENTIFIER_LENGTH: Maximum allowed length for identifiers
        RESERVED_NAMES: Set of reserved names that cannot be used
    """
    
    # Length constraints
    MAX_PROJECT_NAME_LENGTH: int = 100
    MAX_PATH_LENGTH: int = 4096
    MAX_IDENTIFIER_LENGTH: int = 255
    
    # Reserved names (Windows reserved names + common system names)
    RESERVED_NAMES: Set[str] = {
        'con', 'prn', 'aux', 'nul',
        'com1', 'com2', 'com3', 'com4', 'com5', 'com6', 'com7', 'com8', 'com9',
        'lpt1', 'lpt2', 'lpt3', 'lpt4', 'lpt5', 'lpt6', 'lpt7', 'lpt8', 'lpt9',
        'system', 'root', 'admin', 'administrator',
        '.', '..',
    }
    
    # Security patterns
    PATH_TRAVERSAL_PATTERNS: List[Pattern] = [
        re.compile(r'\.\.[\\/]'),  # Parent directory traversal
        re.compile(r'[\\/]\.\.'),  # Parent directory traversal
        re.compile(r'\.\.'),  # Double dots
        re.compile(r'~[\\/]'),  # Home directory reference
        re.compile(r'[\\/]~'),  # Home directory reference
    ]
    
    COMMAND_INJECTION_PATTERNS: List[Pattern] = [
        re.compile(r'[;&|`$]'),  # Shell metacharacters
        re.compile(r'\$\(.*\)'),  # Command substitution
        re.compile(r'`.*`'),  # Backtick command substitution
        re.compile(r'\n|\r'),  # Newline characters
        re.compile(r'\\x[0-9a-fA-F]{2}'),  # Hex escape sequences
    ]
    
    SQL_INJECTION_PATTERNS: List[Pattern] = [
        re.compile(r"'|\""),  # Quote characters
        re.compile(r'--'),  # SQL comment
        re.compile(r'/\*|\*/'),  # Multi-line comment
        re.compile(r'\bOR\b.*=', re.IGNORECASE),  # OR condition
        re.compile(r'\bUNION\b', re.IGNORECASE),  # UNION query
        re.compile(r'\bSELECT\b', re.IGNORECASE),  # SELECT statement
        re.compile(r'\bINSERT\b', re.IGNORECASE),  # INSERT statement
        re.compile(r'\bUPDATE\b', re.IGNORECASE),  # UPDATE statement
        re.compile(r'\bDELETE\b', re.IGNORECASE),  # DELETE statement
        re.compile(r'\bDROP\b', re.IGNORECASE),  # DROP statement
    ]
    
    # Valid character patterns
    PROJECT_NAME_PATTERN: Pattern = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9_-]*$')
    IDENTIFIER_PATTERN: Pattern = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')
    
    def __init__(self, strict_mode: bool = True):
        """
        Initialize InputValidator.
        
        Args:
            strict_mode: If True, apply stricter validation rules
        """
        self.strict_mode = strict_mode
    
    def validate_project_name(
        self,
        name: str,
        allow_empty: bool = False
    ) -> ValidationResult:
        """
        Validate a project name.
        
        Project names must:
        - Start with alphanumeric character
        - Contain only alphanumeric, hyphens, and underscores
        - Not exceed MAX_PROJECT_NAME_LENGTH
        - Not be a reserved name
        - Not contain security-sensitive patterns
        
        Args:
            name: Project name to validate
            allow_empty: Whether to allow empty strings
        
        Returns:
            ValidationResult with validation outcome
        
        Example:
            >>> validator = InputValidator()
            >>> result = validator.validate_project_name("my-project")
            >>> print(result.is_valid)
            True
        """
        result = ValidationResult(
            is_valid=True,
            validation_type=ValidationType.PROJECT_NAME,
            original_value=name
        )
        
        # Check for empty input
        if not name or not name.strip():
            if allow_empty:
                result.sanitized_value = ""
                return result
            result.add_error("Project name cannot be empty")
            return result
        
        name = name.strip()
        
        # Check length
        if len(name) > self.MAX_PROJECT_NAME_LENGTH:
            result.add_error(
                f"Project name exceeds maximum length of "
                f"{self.MAX_PROJECT_NAME_LENGTH} characters"
            )
        
        # Check for reserved names
        if name.lower() in self.RESERVED_NAMES:
            result.add_error(f"'{name}' is a reserved name and cannot be used")
        
        # Check character pattern
        if not self.PROJECT_NAME_PATTERN.match(name):
            result.add_error(
                "Project name must start with alphanumeric character and "
                "contain only alphanumeric characters, hyphens, and underscores"
            )
        
        # Security checks
        self._check_security_patterns(name, result)
        
        # Sanitize if valid
        if result.is_valid:
            result.sanitized_value = name
            
            # Warnings for potentially problematic names
            if name.startswith('-'):
                result.add_warning("Project name starts with hyphen")
            if name.endswith('-'):
                result.add_warning("Project name ends with hyphen")
            if '__' in name:
                result.add_warning("Project name contains consecutive underscores")
        
        return result
    
    def validate_file_path(
        self,
        path: str,
        must_exist: bool = False,
        allowed_extensions: Optional[List[str]] = None,
        base_directory: Optional[str] = None
    ) -> ValidationResult:
        """
        Validate a file path.
        
        File paths must:
        - Not contain path traversal patterns
        - Not exceed MAX_PATH_LENGTH
        - Not contain command injection patterns
        - Optionally exist on the filesystem
        - Optionally have allowed extensions
        - Optionally be within a base directory
        
        Args:
            path: File path to validate
            must_exist: If True, path must exist on filesystem
            allowed_extensions: List of allowed file extensions (e.g., ['.py', '.txt'])
            base_directory: If provided, path must be within this directory
        
        Returns:
            ValidationResult with validation outcome
        
        Example:
            >>> validator = InputValidator()
            >>> result = validator.validate_file_path("data/file.txt")
            >>> print(result.is_valid)
            True
        """
        result = ValidationResult(
            is_valid=True,
            validation_type=ValidationType.FILE_PATH,
            original_value=path
        )
        
        # Check for empty input
        if not path or not path.strip():
            result.add_error("File path cannot be empty")
            return result
        
        path = path.strip()
        
        # Check length
        if len(path) > self.MAX_PATH_LENGTH:
            result.add_error(
                f"File path exceeds maximum length of {self.MAX_PATH_LENGTH} characters"
            )
        
        # Security checks
        self._check_path_traversal(path, result)
        self._check_command_injection(path, result)
        
        # Convert to Path object for further validation
        try:
            path_obj = Path(path)
            
            # Check for absolute path in strict mode
            if self.strict_mode and path_obj.is_absolute():
                result.add_warning("Absolute paths may pose security risks")
            
            # Check if path exists
            if must_exist and not path_obj.exists():
                result.add_error(f"File does not exist: {path}")
            
            # Check if it's actually a file (if it exists)
            if path_obj.exists() and not path_obj.is_file():
                result.add_error(f"Path exists but is not a file: {path}")
            
            # Check file extension
            if allowed_extensions:
                ext = path_obj.suffix.lower()
                allowed_exts_lower = [e.lower() for e in allowed_extensions]
                if ext not in allowed_exts_lower:
                    result.add_error(
                        f"File extension '{ext}' not allowed. "
                        f"Allowed extensions: {', '.join(allowed_extensions)}"
                    )
            
            # Check base directory constraint
            if base_directory:
                try:
                    base_path = Path(base_directory).resolve()
                    resolved_path = path_obj.resolve()
                    if not str(resolved_path).startswith(str(base_path)):
                        result.add_error(
                            f"File path must be within base directory: {base_directory}"
                        )
                except (OSError, RuntimeError) as e:
                    result.add_error(f"Error resolving path: {e}")
            
            # Sanitize if valid
            if result.is_valid:
                # Normalize the path
                result.sanitized_value = os.path.normpath(path)
        
        except (ValueError, OSError) as e:
            result.add_error(f"Invalid file path: {e}")
        
        return result
    
    def validate_directory_path(
        self,
        path: str,
        must_exist: bool = False,
        create_if_missing: bool = False,
        base_directory: Optional[str] = None
    ) -> ValidationResult:
        """
        Validate a directory path.
        
        Directory paths must:
        - Not contain path traversal patterns
        - Not exceed MAX_PATH_LENGTH
        - Not contain command injection patterns
        - Optionally exist on the filesystem
        - Optionally be within a base directory
        
        Args:
            path: Directory path to validate
            must_exist: If True, directory must exist on filesystem
            create_if_missing: If True and must_exist is False, create directory
            base_directory: If provided, path must be within this directory
        
        Returns:
            ValidationResult with validation outcome
        
        Example:
            >>> validator = InputValidator()
            >>> result = validator.validate_directory_path("output/reports")
            >>> print(result.is_valid)
            True
        """
        result = ValidationResult(
            is_valid=True,
            validation_type=ValidationType.DIRECTORY_PATH,
            original_value=path
        )
        
        # Check for empty input
        if not path or not path.strip():
            result.add_error("Directory path cannot be empty")
            return result
        
        path = path.strip()
        
        # Check length
        if len(path) > self.MAX_PATH_LENGTH:
            result.add_error(
                f"Directory path exceeds maximum length of "
                f"{self.MAX_PATH_LENGTH} characters"
            )
        
        # Security checks
        self._check_path_traversal(path, result)
        self._check_command_injection(path, result)
        
        # Convert to Path object for further validation
        try:
            path_obj = Path(path)
            
            # Check for absolute path in strict mode
            if self.strict_mode and path_obj.is_absolute():
                result.add_warning("Absolute paths may pose security risks")
            
            # Check if directory exists
            if path_obj.exists():
                if not path_obj.is_dir():
                    result.add_error(f"Path exists but is not a directory: {path}")
            elif must_exist:
                result.add_error(f"Directory does not exist: {path}")
            elif create_if_missing:
                result.add_warning(f"Directory will be created: {path}")
            
            # Check base directory constraint
            if base_directory:
                try:
                    base_path = Path(base_directory).resolve()
                    resolved_path = path_obj.resolve() if path_obj.exists() else path_obj
                    if not str(resolved_path).startswith(str(base_path)):
                        result.add_error(
                            f"Directory path must be within base directory: {base_directory}"
                        )
                except (OSError, RuntimeError) as e:
                    result.add_error(f"Error resolving path: {e}")
            
            # Sanitize if valid
            if result.is_valid:
                # Normalize the path
                result.sanitized_value = os.path.normpath(path)
        
        except (ValueError, OSError) as e:
            result.add_error(f"Invalid directory path: {e}")
        
        return result
    
    def validate_identifier(
        self,
        identifier: str,
        allow_empty: bool = False
    ) -> ValidationResult:
        """
        Validate a Python-style identifier.
        
        Identifiers must:
        - Start with letter or underscore
        - Contain only alphanumeric characters and underscores
        - Not exceed MAX_IDENTIFIER_LENGTH
        - Not be a Python keyword or reserved name
        - Not contain security-sensitive patterns
        
        Args:
            identifier: Identifier to validate
            allow_empty: Whether to allow empty strings
        
        Returns:
            ValidationResult with validation outcome
        
        Example:
            >>> validator = InputValidator()
            >>> result = validator.validate_identifier("my_variable")
            >>> print(result.is_valid)
            True
        """
        result = ValidationResult(
            is_valid=True,
            validation_type=ValidationType.IDENTIFIER,
            original_value=identifier
        )
        
        # Check for empty input
        if not identifier or not identifier.strip():
            if allow_empty:
                result.sanitized_value = ""
                return result
            result.add_error("Identifier cannot be empty")
            return result
        
        identifier = identifier.strip()
        
        # Check length
        if len(identifier) > self.MAX_IDENTIFIER_LENGTH:
            result.add_error(
                f"Identifier exceeds maximum length of "
                f"{self.MAX_IDENTIFIER_LENGTH} characters"
            )
        
        # Check character pattern
        if not self.IDENTIFIER_PATTERN.match(identifier):
            result.add_error(
                "Identifier must start with letter or underscore and "
                "contain only alphanumeric characters and underscores"
            )
        
        # Check for reserved names
        if identifier.lower() in self.RESERVED_NAMES:
            result.add_error(f"'{identifier}' is a reserved name and cannot be used")
        
        # Check for Python keywords
        import keyword
        if keyword.iskeyword(identifier):
            result.add_error(f"'{identifier}' is a Python keyword and cannot be used")
        
        # Security checks
        self._check_security_patterns(identifier, result)
        
        # Sanitize if valid
        if result.is_valid:
            result.sanitized_value = identifier
            
            # Warnings for potentially problematic identifiers
            if identifier.startswith('_') and identifier.endswith('_'):
                result.add_warning("Identifier has leading and trailing underscores")
            if identifier.startswith('__'):
                result.add_warning("Identifier starts with double underscore (name mangling)")
        
        return result
    
    def _check_security_patterns(
        self,
        value: str,
        result: ValidationResult
    ) -> None:
        """
        Check for common security attack patterns.
        
        Args:
            value: String to check
            result: ValidationResult to update with any findings
        """
        self._check_command_injection(value, result)
        self._check_sql_injection(value, result)
    
    def _check_path_traversal(
        self,
        path: str,
        result: ValidationResult
    ) -> None:
        """
        Check for path traversal attack patterns.
        
        Args:
            path: Path string to check
            result: ValidationResult to update with any findings
        """
        for pattern in self.PATH_TRAVERSAL_PATTERNS:
            if pattern.search(path):
                result.add_error(
                    f"Path contains potential path traversal pattern: "
                    f"{pattern.pattern}"
                )
    
    def _check_command_injection(
        self,
        value: str,
        result: ValidationResult
    ) -> None:
        """
        Check for command injection attack patterns.
        
        Args:
            value: String to check
            result: ValidationResult to update with any findings
        """
        for pattern in self.COMMAND_INJECTION_PATTERNS:
            if pattern.search(value):
                result.add_error(
                    f"Input contains potential command injection pattern: "
                    f"{pattern.pattern}"
                )
    
    def _check_sql_injection(
        self,
        value: str,
        result: ValidationResult
    ) -> None:
        """
        Check for SQL injection attack patterns.
        
        Args:
            value: String to check
            result: ValidationResult to update with any findings
        """
        for pattern in self.SQL_INJECTION_PATTERNS:
            if pattern.search(value):
                result.add_error(
                    f"Input contains potential SQL injection pattern: "
                    f"{pattern.pattern}"
                )
