# Cortex Prompt Versioning System

A structured prompt management system with versioning and A/B testing capabilities.

## Overview

The prompt versioning system provides:

- **Versioned Templates**: Store prompts as YAML files with semantic versioning
- **Variable Validation**: Ensure all required variables are provided before rendering
- **Registry**: Centralized loading and caching of prompt templates
- **A/B Testing**: Consistent hash-based assignment for prompt experiments
- **Quality Tracking**: Record usage and quality metrics for each template

## Quick Start

### Loading a Template

```python
from cortex.prompts.registry import get_registry

# Get the global registry
registry = get_registry()

# Load a template (gets latest version by default)
template = registry.get_prompt("briefing_generation")

# Render with variables
result = template.render(
    date="2026-02-01",
    portfolio_pulse="3 active projects",
    active_goals="Complete Phase 1",
    recent_activity="10 commits in last 24h",
)

print(result)
```

### Creating a New Template

```python
from cortex.prompts.base import PromptTemplate
from pathlib import Path

# Define template
template = PromptTemplate(
    name="my_prompt",
    version="1.0.0",
    description="Custom prompt for X",
    template="Hello {name}, your task is: {task}",
    variables=["name", "task"],
    metadata={
        "author": "me",
        "created": "2026-02-01",
    }
)

# Save to YAML
output_path = Path("cortex/prompts/versions/v1/my_prompt.yaml")
template.to_yaml(output_path)
```

### A/B Testing

```python
from cortex.prompts.ab_testing import ABTestManager, simple_ab_test
from cortex.prompts.registry import get_registry

# Simple 50/50 test
variant = simple_ab_test(
    prompt_name="briefing_generation",
    user_id="user123",
    control="v1",
    treatment="v2"
)

# Load the assigned variant
registry = get_registry()
template = registry.get_prompt("briefing_generation", version=variant)

# Weighted test (80/20)
manager = ABTestManager()
variant = manager.get_variant(
    prompt_name="recommendation_generation",
    user_id="user456",
    variants={"v1": 0.8, "v2": 0.2}
)

# Check test statistics
stats = manager.get_assignment_stats("recommendation_generation")
print(f"Total assignments: {stats['total']}")
print(f"Variant distribution: {stats['variants']}")
```

### Quality Tracking

```python
from cortex.prompts.registry import get_registry

registry = get_registry()
template = registry.get_prompt("recommendation_generation")

# Record usage
template.record_usage()

# Record quality scores (from AI-as-a-judge or user feedback)
template.record_quality_score(0.85)
template.record_quality_score(0.90)

# Check metrics
print(f"Usage count: {template.metadata['usage_count']}")
print(f"Avg quality: {template.metadata['avg_quality_score']}")
```

## Directory Structure

```
cortex/prompts/
├── __init__.py           # Package exports
├── base.py               # PromptTemplate class
├── registry.py           # PromptRegistry class
├── ab_testing.py         # A/B testing framework
├── README.md             # This file
└── versions/             # Template versions
    ├── v1/
    │   ├── briefing.yaml
    │   ├── recommendation.yaml
    │   ├── evaluation.yaml
    │   ├── pattern_match.yaml
    │   └── bridge_context.yaml
    └── v2/               # Future versions
        └── ...
```

## YAML Template Format

```yaml
name: prompt_name
version: "1.0.0"
description: "What this prompt does"
template: |
  Your prompt template here with {variables}.

  Can be multiline.

  Variables: {var1}, {var2}
variables:
  - var1
  - var2
metadata:
  author: "author-name"
  created: "2026-02-01"
  usage_count: 0
  avg_quality_score: null
  purpose: "Brief purpose description"
  model: "claude-3-5-sonnet-20241022"
```

## Available Templates (v1)

1. **briefing_generation**: Daily briefing from project context
2. **recommendation_generation**: Actionable project recommendations
3. **quality_evaluation**: AI-as-a-judge quality scoring
4. **pattern_matching**: Semantic pattern retrieval
5. **bridge_context_query**: Context queries via Cortex bridge

## Best Practices

1. **Version Management**:
   - Use semantic versioning (major.minor.patch)
   - Create new version when changing template structure
   - Keep old versions for rollback capability

2. **Variable Naming**:
   - Use clear, descriptive names
   - Use snake_case for consistency
   - Document expected format in template description

3. **A/B Testing**:
   - Start with 50/50 splits
   - Monitor quality metrics before scaling winners
   - Keep experiment IDs for tracking

4. **Quality Tracking**:
   - Record usage for all templates
   - Integrate quality scores from AI judge
   - Review metrics regularly to identify poor performers

## Testing

Run the test suite:

```bash
pytest cortex/tests/test_prompts.py -v
```

Coverage: 32 tests, 100% passing

## Future Enhancements

- [ ] Automatic prompt optimization via learning
- [ ] Multi-variant testing (>2 variants)
- [ ] Prompt analytics dashboard
- [ ] Integration with Cortex learning system
- [ ] Template inheritance/composition
