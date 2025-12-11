from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple

@dataclass
class SpecPhaseStatus:
    name: str
    completed: bool
    evidence: str  # Line showing it's complete, or missing reason

@dataclass
class GoldenSpecStatus:
    project_name: str
    has_spec_file: bool
    spec_path: Optional[str]
    phases: List[SpecPhaseStatus]
    compliance_score: float  # 0.0 to 1.0
    recommendations: List[str]

class GoldenSpecValidator:
    """Validates a project against Golden Spec Method criteria."""
    
    REQUIRED_PHASES = [
        "1. Deep Understanding",
        "2. Outcome Definition",
        "3. Outcome Validation",
        "4. Solution Design",
        "5. Solution-Outcome Alignment",
        "6. Implementation Planning",
        "7. Success Verification"
    ]
    
    def __init__(self, root_dir: Path):
        self.root_dir = root_dir
        
    def validate_project(self, project_name: str) -> GoldenSpecStatus:
        """
        Validate a project's alignment with Golden Spec.
        Look for *SPEC.md, DESIGN.md, or GOLDEN_SPEC.md files.
        """
        project_path = self.root_dir / project_name
        
        # 1. Find the Spec File
        spec_candidates = [
            f"{project_name}_SPEC.md",
            "GOLDEN_SPEC.md",
            "DESIGN_SPEC.md",
            "SPEC.md",
            "ARCHITECTURE.md"
        ]
        
        found_spec = None
        for candidate in spec_candidates:
            if (project_path / candidate).exists():
                found_spec = project_path / candidate
                break
                
        if not found_spec:
            # Try recursive search if not in root
            try:
                specs = list(project_path.glob("*_SPEC.md"))
                if specs:
                    found_spec = specs[0]
            except Exception:
                pass
                
        if not found_spec:
            return GoldenSpecStatus(
                project_name=project_name,
                has_spec_file=False,
                spec_path=None,
                phases=[],
                compliance_score=0.0,
                recommendations=["Create a GOLDEN_SPEC.md file to define outcomes."]
            )
            
        # 2. Analyze Content
        content = found_spec.read_text()
        phases_status = []
        completed_count = 0
        
        for phase in self.REQUIRED_PHASES:
            # Loose matching for phase headers
            # e.g. "## 1. Deep Understanding" or "Phase 1: Deep Understanding"
            key_term = phase.split(". ")[1] # "Deep Understanding"
            
            is_present = key_term.lower() in content.lower()
            
            # Simple heuristic for "completed": Phase is present and has content
            # (In a real implementation, we'd enable LLM analysis here)
            evidence = ""
            if is_present:
                evidence = f"Found section containing '{key_term}'"
                completed_count += 1
            else:
                evidence = "Section missing"
                
            phases_status.append(SpecPhaseStatus(
                name=phase,
                completed=is_present,
                evidence=evidence
            ))
            
        score = completed_count / len(self.REQUIRED_PHASES)
        
        recs = []
        if score < 1.0:
            missing_phases = [p.name for p in phases_status if not p.completed]
            recs.append(f"Complete missing phases: {', '.join(missing_phases)}")
            
        return GoldenSpecStatus(
            project_name=project_name,
            has_spec_file=True,
            spec_path=str(found_spec.name),
            phases=phases_status,
            compliance_score=score,
            recommendations=recs
        )
