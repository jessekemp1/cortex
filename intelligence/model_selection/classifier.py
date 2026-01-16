#!/usr/bin/env python3
"""
Task Complexity Classifier.

Analyzes task descriptions and context to classify complexity level.
Used by model recommender to choose appropriate model power.
"""

from typing import Any, Dict, Tuple


class TaskComplexityClassifier:
    """
    Classify task complexity from prompt and context.

    Returns: (complexity, confidence)
    - complexity: "simple" | "moderate" | "complex"
    - confidence: 0.0-1.0
    """

    # Keywords that suggest simple tasks
    SIMPLE_KEYWORDS = [
        "search",
        "find",
        "list",
        "show",
        "get",
        "read",
        "view",
        "check",
        "typo",
        "rename",
        "format",
        "import",
        "comment",
        "docstring",
    ]

    # Keywords that suggest complex tasks
    COMPLEX_KEYWORDS = [
        "refactor",
        "architect",
        "design",
        "implement feature",
        "authentication",
        "optimize",
        "migrate",
        "integrate",
        "security",
        "performance",
        "scalability",
        "architecture",
    ]

    # Keywords that suggest moderate complexity
    MODERATE_KEYWORDS = [
        "fix",
        "bug",
        "implement",
        "add",
        "update",
        "modify",
        "change",
        "improve",
        "test",
        "debug",
    ]

    def classify(self, task_description: str, context: Dict[str, Any]) -> Tuple[str, float]:
        """
        Classify task complexity.

        Args:
            task_description: Description of the task
            context: Additional context (files, project, etc.)

        Returns:
            Tuple of (complexity, confidence)
            - complexity: "simple", "moderate", or "complex"
            - confidence: 0.0-1.0
        """
        score = 0.0
        desc_lower = task_description.lower()

        # 1. Keyword analysis
        simple_matches = sum(1 for kw in self.SIMPLE_KEYWORDS if kw in desc_lower)
        complex_matches = sum(1 for kw in self.COMPLEX_KEYWORDS if kw in desc_lower)
        moderate_matches = sum(1 for kw in self.MODERATE_KEYWORDS if kw in desc_lower)

        # Weight keywords
        score += simple_matches * -2.0  # Simple keywords decrease score
        score += complex_matches * 3.0  # Complex keywords increase score
        score += moderate_matches * 1.0  # Moderate keywords increase score slightly

        # 2. File count analysis
        files = context.get("files", [])
        files_count = len(files) if isinstance(files, list) else 0

        if files_count == 0:
            score -= 1.0  # Probably just exploration/search
        elif files_count == 1:
            score += 0.0  # Single file, moderate
        elif files_count <= 3:
            score += 1.0  # Few files, slightly complex
        elif files_count <= 10:
            score += 2.0  # Many files, complex
        else:
            score += 3.0  # Very many files, very complex

        # 3. Length analysis (longer descriptions often more complex)
        if len(task_description) < 20:
            score -= 0.5  # Very short = likely simple
        elif len(task_description) > 100:
            score += 1.0  # Long description = more complex

        # 4. Architectural terms
        architectural_terms = [
            "class",
            "interface",
            "api",
            "database",
            "schema",
            "model",
            "controller",
            "service",
            "module",
            "package",
            "system",
        ]
        if any(term in desc_lower for term in architectural_terms):
            score += 1.0

        # 5. Multi-step indicators
        multi_step_indicators = [" and ", " then ", " after ", " before ", "workflow"]
        if any(indicator in desc_lower for indicator in multi_step_indicators):
            score += 1.0

        # 6. Context-specific signals
        project_name = context.get("project", "").lower()
        if any(keyword in project_name for keyword in ["legacy", "monorepo", "enterprise"]):
            score += 0.5  # Larger projects tend to be more complex

        # Classify based on score
        if score <= -1.0:
            complexity = "simple"
            confidence = min(0.9, 0.7 + abs(score) * 0.1)
        elif score <= 2.0:
            complexity = "moderate"
            confidence = 0.7  # Moderate tasks have lower confidence (ambiguous)
        else:
            complexity = "complex"
            confidence = min(0.9, 0.7 + (score - 2.0) * 0.05)

        # Adjust confidence based on evidence
        evidence_count = simple_matches + complex_matches + moderate_matches + files_count
        if evidence_count == 0:
            confidence *= 0.5  # Low confidence with no evidence

        return (complexity, confidence)

    def explain(self, task_description: str, context: Dict[str, Any]) -> str:
        """
        Explain classification reasoning (for debugging/transparency).

        Args:
            task_description: Description of the task
            context: Additional context

        Returns:
            Human-readable explanation
        """
        complexity, confidence = self.classify(task_description, context)

        desc_lower = task_description.lower()
        simple_matches = [kw for kw in self.SIMPLE_KEYWORDS if kw in desc_lower]
        complex_matches = [kw for kw in self.COMPLEX_KEYWORDS if kw in desc_lower]
        moderate_matches = [kw for kw in self.MODERATE_KEYWORDS if kw in desc_lower]

        files_count = len(context.get("files", []))

        explanation = f"Complexity: {complexity.upper()} (confidence: {confidence:.0%})\n\n"
        explanation += "Reasoning:\n"

        if simple_matches:
            explanation += f"  • Simple keywords detected: {', '.join(simple_matches)}\n"
        if moderate_matches:
            explanation += f"  • Moderate keywords detected: {', '.join(moderate_matches)}\n"
        if complex_matches:
            explanation += f"  • Complex keywords detected: {', '.join(complex_matches)}\n"

        if files_count > 0:
            explanation += f"  • Files involved: {files_count}\n"

        explanation += f"  • Description length: {len(task_description)} chars\n"

        return explanation
