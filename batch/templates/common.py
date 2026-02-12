"""
Common Batch Job Templates

Reusable templates for the most common batch operations.
Each template includes:
- System prompt
- User prompt template
- Expected output format
- Token estimates
"""

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class BatchTemplate:
    """A reusable batch job template"""

    name: str
    description: str
    category: str  # review, docs, research, security, analysis
    system_prompt: str
    user_prompt_template: str
    estimated_input_tokens: int
    estimated_output_tokens: int
    priority: str = "normal"
    deadline_hours: int = 24


BATCH_TEMPLATES: Dict[str, BatchTemplate] = {
    # === CODE REVIEW TEMPLATES ===
    "pr-review": BatchTemplate(
        name="pr-review",
        description="Comprehensive pull request review",
        category="review",
        system_prompt="""You are an expert code reviewer. Provide thorough, constructive feedback
focused on security, performance, correctness, and maintainability. Reference specific
file:line locations. Be direct but supportive.""",
        user_prompt_template="""Review this pull request:

**Title:** {title}
**Description:** {description}

**Changed Files:**
{files}

**Diff:**
{diff}

Provide:
1. Security issues (Critical/High/Medium/Low)
2. Performance concerns
3. Logic/correctness issues
4. Code quality suggestions
5. Overall assessment (Approve/Request Changes)""",
        estimated_input_tokens=15000,
        estimated_output_tokens=4000,
        priority="normal",
        deadline_hours=24,
    ),
    "security-review": BatchTemplate(
        name="security-review",
        description="Security-focused code review",
        category="security",
        system_prompt="""You are a security expert reviewing code for vulnerabilities.
Focus on OWASP Top 10, authentication, authorization, input validation,
and data protection. Rate findings by severity.""",
        user_prompt_template="""Security review for:

{files}

Check for:
1. Injection vulnerabilities (SQL, command, XSS)
2. Authentication/authorization issues
3. Sensitive data exposure
4. Security misconfigurations
5. Cryptographic weaknesses
6. Input validation gaps

Rate each finding: CRITICAL | HIGH | MEDIUM | LOW""",
        estimated_input_tokens=20000,
        estimated_output_tokens=5000,
        priority="high",
        deadline_hours=12,
    ),
    # === DOCUMENTATION TEMPLATES ===
    "api-docs": BatchTemplate(
        name="api-docs",
        description="Generate API documentation",
        category="docs",
        system_prompt="""You are a technical writer specializing in API documentation.
Create clear, comprehensive documentation with examples. Use OpenAPI/Swagger
format where applicable.""",
        user_prompt_template="""Generate API documentation for:

{files}

Include:
1. Endpoint summaries
2. Request/response schemas
3. Authentication requirements
4. Example requests (curl)
5. Error codes and handling
6. Rate limits if applicable

Format as markdown.""",
        estimated_input_tokens=10000,
        estimated_output_tokens=6000,
        priority="low",
        deadline_hours=48,
    ),
    "module-docs": BatchTemplate(
        name="module-docs",
        description="Generate module/class documentation",
        category="docs",
        system_prompt="""You are a technical writer. Create clear, comprehensive
documentation following Python docstring conventions (Google style).""",
        user_prompt_template="""Document this module:

{content}

Include:
1. Module overview
2. Class descriptions
3. Method documentation with args/returns
4. Usage examples
5. Dependencies and integration notes

Format as markdown suitable for ReadTheDocs.""",
        estimated_input_tokens=8000,
        estimated_output_tokens=4000,
        priority="low",
        deadline_hours=48,
    ),
    # === RESEARCH TEMPLATES ===
    "tech-research": BatchTemplate(
        name="tech-research",
        description="Technology research and comparison",
        category="research",
        system_prompt="""You are a senior software architect researching technical solutions.
Provide balanced, evidence-based analysis with practical recommendations.""",
        user_prompt_template="""Research: {topic}

Context: {context}

Provide:
1. Overview (2-3 sentences)
2. Options Analysis (pros/cons for each)
3. Performance Considerations
4. Security Implications
5. Cost/Complexity Tradeoffs
6. Recommendation with justification
7. Implementation Roadmap (if adopting)
8. Key Resources/Documentation""",
        estimated_input_tokens=2000,
        estimated_output_tokens=4000,
        priority="normal",
        deadline_hours=24,
    ),
    "architecture-review": BatchTemplate(
        name="architecture-review",
        description="Architecture analysis and recommendations",
        category="research",
        system_prompt="""You are a software architect analyzing system design.
Focus on scalability, maintainability, and best practices.""",
        user_prompt_template="""Analyze the architecture of:

{description}

Current structure:
{structure}

Key files:
{files}

Evaluate:
1. Current architecture patterns
2. Scalability concerns
3. Coupling/cohesion analysis
4. Suggested improvements
5. Migration path if changes needed""",
        estimated_input_tokens=15000,
        estimated_output_tokens=5000,
        priority="normal",
        deadline_hours=24,
    ),
    # === ANALYSIS TEMPLATES ===
    "test-coverage": BatchTemplate(
        name="test-coverage",
        description="Analyze test coverage gaps",
        category="analysis",
        system_prompt="""You are a QA engineer focused on test coverage.
Identify gaps and prioritize test cases by risk.""",
        user_prompt_template="""Analyze test coverage for:

Source files:
{source_files}

Test files:
{test_files}

Identify:
1. Untested functions/methods
2. Missing edge cases
3. Error path coverage gaps
4. Integration test needs
5. Suggested test cases (prioritized by risk)

Format as actionable checklist.""",
        estimated_input_tokens=25000,
        estimated_output_tokens=6000,
        priority="normal",
        deadline_hours=24,
    ),
    "refactoring": BatchTemplate(
        name="refactoring",
        description="Identify refactoring opportunities",
        category="analysis",
        system_prompt="""You are an expert in code refactoring and clean code principles.
Identify improvement opportunities while respecting backward compatibility.""",
        user_prompt_template="""Analyze for refactoring opportunities:

{files}

Look for:
1. Long methods (>50 lines)
2. God classes
3. Code duplication
4. Complex conditionals
5. Dead code
6. Naming improvements
7. Design pattern opportunities

For each finding, provide:
- Location (file:line)
- Issue description
- Suggested refactoring
- Risk level (Low/Medium/High)""",
        estimated_input_tokens=20000,
        estimated_output_tokens=6000,
        priority="low",
        deadline_hours=48,
    ),
    "performance": BatchTemplate(
        name="performance",
        description="Performance analysis and optimization",
        category="analysis",
        system_prompt="""You are a performance engineer. Identify bottlenecks and
optimization opportunities with specific, measurable recommendations.""",
        user_prompt_template="""Performance analysis for:

{files}

Focus on:
1. Algorithm complexity (O(n) issues)
2. Database queries (N+1, missing indexes)
3. Memory usage patterns
4. I/O bottlenecks
5. Caching opportunities
6. Async/parallel opportunities

For each finding:
- Location
- Current complexity/impact
- Recommended optimization
- Expected improvement""",
        estimated_input_tokens=15000,
        estimated_output_tokens=5000,
        priority="normal",
        deadline_hours=24,
    ),
    # === SECURITY TEMPLATES ===
    "dependency-audit": BatchTemplate(
        name="dependency-audit",
        description="Audit project dependencies",
        category="security",
        system_prompt="""You are a security analyst auditing project dependencies.
Check for vulnerabilities, outdated packages, and license issues.""",
        user_prompt_template="""Audit dependencies:

requirements.txt / pyproject.toml:
{requirements}

package.json (if applicable):
{package_json}

Check for:
1. Known CVEs in dependencies
2. Outdated packages (major versions behind)
3. License compatibility issues
4. Unused dependencies
5. Dependency conflicts
6. Supply chain risks

Provide severity ratings and update recommendations.""",
        estimated_input_tokens=5000,
        estimated_output_tokens=4000,
        priority="high",
        deadline_hours=12,
    ),
    # === PLANNING TEMPLATES ===
    "implementation-plan": BatchTemplate(
        name="implementation-plan",
        description="Create implementation plan for feature",
        category="planning",
        system_prompt="""You are a senior developer creating implementation plans.
Break down work into clear, testable steps with time estimates.""",
        user_prompt_template="""Create implementation plan for:

**Feature:** {feature}

**Requirements:**
{requirements}

**Existing codebase context:**
{context}

Provide:
1. High-level approach
2. Step-by-step implementation tasks
3. Files to create/modify
4. Testing strategy
5. Risk areas and mitigations
6. Time estimates per step
7. Definition of done""",
        estimated_input_tokens=5000,
        estimated_output_tokens=4000,
        priority="normal",
        deadline_hours=24,
    ),
}


def get_template(name: str) -> Optional[BatchTemplate]:
    """Get a template by name."""
    return BATCH_TEMPLATES.get(name)


def list_templates(category: Optional[str] = None) -> List[BatchTemplate]:
    """List available templates, optionally filtered by category."""
    templates = list(BATCH_TEMPLATES.values())
    if category:
        templates = [t for t in templates if t.category == category]
    return templates


def template_summary() -> str:
    """Get a formatted summary of all templates."""
    lines = ["Available Batch Templates:", "=" * 50]

    categories = {}
    for template in BATCH_TEMPLATES.values():
        if template.category not in categories:
            categories[template.category] = []
        categories[template.category].append(template)

    for category, templates in sorted(categories.items()):
        lines.append(f"\n{category.upper()}")
        lines.append("-" * 30)
        for t in templates:
            lines.append(f"  {t.name:<20} - {t.description}")

    return "\n".join(lines)
