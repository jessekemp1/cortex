# Extension Points

**How to extend Cortex with custom functionality**

This guide explains how to extend Cortex with custom analyzers, integrations, and features.

---

## Plugin Architecture

### Custom Analyzers

**Create custom analyzer**:

```python
from cortex.agents.data_agent.analyzers.dependency_mapper import DependencyMapper

class CustomAnalyzer(DependencyMapper):
    def analyze_custom_metric(self, project_path):
        """Custom analysis logic"""
        # Your custom analysis
        return {"custom_metric": "value"}

# Use custom analyzer
analyzer = CustomAnalyzer(project_path)
result = analyzer.analyze_custom_metric(project_path)
```

---

### Custom Integrations

**MCP Server Integration**:

```python
# mcp_server.py
from mcp import Server
from cortex.bridge import CortexBridge

server = Server("cortex")
bridge = CortexBridge()

@server.resource("cortex://context")
def get_context(query: str):
    return bridge.get_context(query)

# Register resources and tools
server.run()
```

---

### Custom Intelligence Sources

**Add new intelligence source**:

```python
from cortex.intelligence.unified_intelligence import UnifiedIntelligence

class CustomIntelligenceSource:
    def query(self, request: str, project: str) -> Dict[str, Any]:
        """Custom intelligence query"""
        # Your custom logic
        return {"results": [...]}

# Integrate with UnifiedIntelligence
unified = UnifiedIntelligence()
unified.add_source(CustomIntelligenceSource())
```

---

## Adding New Features

### New Bridge Methods

**Add method to Bridge API**:

```python
# In bridge.py
class CortexBridge:
    def your_new_method(self, param: str) -> Dict[str, Any]:
        """
        Your new method.
        
        Args:
            param: Parameter description
        
        Returns:
            Result dictionary
        """
        # Implementation
        return {"result": "value"}
```

---

### New CLI Commands

**Add command to CLI**:

```python
# In cli.py or bridge.py
def cmd_your_command(args):
    """Your command implementation"""
    bridge = CortexBridge()
    result = bridge.your_new_method(args.param)
    print(json.dumps(result, indent=2))

# Register command
your_parser = subparsers.add_parser("your-command", help="Description")
your_parser.add_argument("param", help="Parameter")
your_parser.set_defaults(func=cmd_your_command)
```

---

## Integration Examples

### Session Hooks

**Custom session hook**:

```bash
#!/bin/bash
# ~/.claude/hooks/SessionStart.custom.sh

# Your custom logic
python bridge.py your-custom-command
```

---

### Automation Scripts

**Custom automation**:

```python
#!/usr/bin/env python3
from cortex.bridge import CortexBridge

bridge = CortexBridge()

# Your custom automation logic
result = bridge.your_new_method("param")
print(result)
```

---

## Best Practices

### Error Handling

**Always handle errors gracefully**:

```python
def your_method(self, param: str) -> Dict[str, Any]:
    try:
        # Your logic
        return {"result": "value"}
    except Exception as e:
        return {"error": str(e)}
```

### Performance

**Optimize for performance**:
- Use lazy loading
- Cache results when appropriate
- Batch operations when possible

### Testing

**Test your extensions**:
- Write unit tests
- Test error cases
- Verify performance

---

## Next Steps

- [Developer Setup](setup.md) - Development environment
- [Architecture Deep Dive](architecture_deep_dive.md) - Internal design
- [Contributing Guide](../CONTRIBUTING.md) - Contribution process

---

**Version**: 1.0  
**Last Updated**: 2025-12-24

