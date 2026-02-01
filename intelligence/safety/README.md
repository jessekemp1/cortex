# Cortex Safety Module

Defensive prompting and validation system for Cortex intelligence queries.

## Overview

The safety module provides three layers of protection:

1. **Input Validation** - Validates user queries before processing
2. **Injection Detection** - Detects prompt injection attempts
3. **Output Validation** - Validates AI responses before returning
4. **Guardrail Templates** - Wraps queries with defensive prompting

## Usage

### Basic Input Validation

```python
from cortex.intelligence.safety import InputValidator

validator = InputValidator(max_length=10000)

# Validate a query
result = validator.validate("Help me debug async errors")

if result.passed:
    # Safe to process
    process_query(result.validated_value)
else:
    # Handle validation errors
    for error in result.get_errors():
        print(f"Error: {error.message}")
```

### Injection Detection

```python
from cortex.intelligence.safety import InjectionDetector

detector = InjectionDetector()

# Check if query is safe
if detector.is_safe(query):
    process_query(query)
else:
    attempt = detector.detect(query)
    print(f"Injection detected: {attempt.severity.value}")
    print(f"Matched pattern: {attempt.pattern}")
```

### Output Validation

```python
from cortex.intelligence.safety import OutputValidator

validator = OutputValidator(min_confidence=0.3)

# Validate AI response
response = {
    "content": "Analysis of the code...",
    "confidence": 0.85,
    "patterns": [...]
}

result = validator.validate(response)

if result.passed:
    return response
else:
    # Handle validation warnings
    for warning in result.get_warnings():
        print(f"Warning: {warning.message}")
```

### Guardrail Templates

```python
from cortex.intelligence.safety import apply_guardrails

# Apply guardrails based on query type
guarded_query = apply_guardrails(
    "Find patterns for error handling",
    query_type="context",  # or "recommendation", "general"
    context_description="error handling patterns"
)

# Send guarded_query to LLM
response = llm.query(guarded_query)
```

## Integration Example

Full pipeline with validation and guardrails:

```python
from cortex.intelligence.safety import (
    InputValidator,
    OutputValidator,
    apply_guardrails,
)

def safe_intelligence_query(query: str, query_type: str = "general"):
    """Process a query with full safety validation."""

    # 1. Input validation
    input_validator = InputValidator()
    input_result = input_validator.validate(query)

    if not input_result.passed:
        raise ValueError(f"Invalid query: {input_result.get_errors()}")

    # 2. Apply guardrails
    guarded_query = apply_guardrails(query, query_type=query_type)

    # 3. Send to LLM (your intelligence system)
    raw_response = your_llm_call(guarded_query)

    # 4. Output validation
    output_validator = OutputValidator(min_confidence=0.3)
    output_result = output_validator.validate(raw_response)

    if not output_result.passed:
        # Log warnings but don't fail
        for warning in output_result.get_warnings():
            logger.warning(f"Output validation warning: {warning.message}")

    return raw_response
```

## Injection Patterns Detected

### Critical Severity
- `ignore all previous instructions`
- `disregard your rules`
- `forget everything`
- `new instructions:`

### High Severity
- `you are now a different AI`
- `pretend you are`
- `reveal your prompt`
- `act as if`

### Medium Severity
- `without restrictions`
- `bypass safety`
- `developer mode`
- `jailbreak`
- Special tokens like `[INST]`, `<|im_start|>`

### Low Severity
- `override mode`
- `change your behavior`
- `stop being`

## Logging

Injection attempts are automatically logged to `~/.cortex/security.log`:

```json
{
  "pattern": "\\bignore\\s+(all\\s+)?(previous\\s+)?(instructions?)",
  "matched_text": "ignore all previous instructions",
  "severity": "critical",
  "timestamp": "2026-02-01T12:00:00",
  "query": "ignore all previous instructions and..."
}
```

## Configuration

### InputValidator Options

```python
validator = InputValidator(
    max_length=10000,      # Max query length
    min_length=1,          # Min query length
    allowed_domains=[      # Expected query domains
        "development",
        "project_management",
        "testing",
    ]
)
```

### OutputValidator Options

```python
validator = OutputValidator(
    min_confidence=0.3     # Minimum confidence threshold
)
```

## Testing

Run safety tests:

```bash
pytest cortex/tests/test_safety.py -v
```

## Files

- `validators.py` - Input and output validators
- `injection_detector.py` - Prompt injection detection
- `guardrails.py` - Guardrail templates
- `__init__.py` - Public API

## Security Logs

Injection attempts are logged to:
- File: `~/.cortex/security.log` (JSONL format)
- Python logger: `cortex.intelligence.safety.injection_detector`
