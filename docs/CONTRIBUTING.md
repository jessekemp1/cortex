# Contributing to Cortex

**Contribution guidelines and process**

Thank you for your interest in contributing to Cortex!

---

## Contribution Process

### 1. Fork and Clone

```bash
# Fork the repository on GitHub
# Clone your fork
git clone https://github.com/yourusername/cortex.git
cd cortex
```

### 2. Create Branch

```bash
# Create feature branch
git checkout -b feature/your-feature-name
```

### 3. Make Changes

- Follow [Code Style Guidelines](developer/setup.md#code-style-guidelines)
- Write tests for new features
- Update documentation

### 4. Test Changes

```bash
# Run tests
pytest tests/ -v

# Run enterprise-grade tests
python test_enterprise_grade.py

# Check code style
ruff check .
```

### 5. Commit Changes

```bash
# Use conventional commits
git commit -m "feat(module): description"
```

### 6. Push and Create PR

```bash
# Push to your fork
git push origin feature/your-feature-name

# Create pull request on GitHub
```

---

## Code of Conduct

### Be Respectful

- Be respectful in all interactions
- Accept constructive criticism
- Help others learn

### Be Professional

- Write clear, maintainable code
- Document your changes
- Follow project conventions

---

## Pull Request Guidelines

### PR Description

Include:
- **What**: What changes were made
- **Why**: Why these changes were needed
- **How**: How the changes work
- **Testing**: Test results

### PR Checklist

- [ ] Code follows style guidelines
- [ ] Tests pass (unit + enterprise-grade)
- [ ] Documentation updated
- [ ] No breaking changes (or documented)
- [ ] Performance impact assessed

---

## Testing Requirements

### Unit Tests

- Write tests for all new features
- Maintain >80% coverage
- Test error cases

### Enterprise-Grade Tests

- Ensure all enterprise tests pass
- Add tests for new features if applicable

---

## Documentation Standards

### Code Documentation

- Docstrings for all public functions
- Type hints for all function signatures
- Inline comments for complex logic

### User Documentation

- Update user guides for new features
- Add examples to examples.md
- Update API documentation

---

## Review Process

### Review Criteria

- Code quality and style
- Test coverage
- Documentation completeness
- Performance impact
- Backward compatibility

### Review Timeline

- Initial review: Within 2 business days
- Feedback: Within 1 business day
- Final approval: After all feedback addressed

---

## Questions?

- Open an issue for questions
- Check [Developer Setup](developer/setup.md)
- Review [Architecture Deep Dive](developer/architecture_deep_dive.md)

---

**Version**: 1.0  
**Last Updated**: 2025-12-24

