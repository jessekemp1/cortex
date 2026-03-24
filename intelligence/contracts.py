#!/usr/bin/env python3
"""
Contract Generation System

Uses Opus 4.5 to generate comprehensive task contracts that eliminate
mid-execution questions. The contract includes:
- Specific, unambiguous requirements
- Measurable success criteria
- Mandatory human gates
- Risk assessment
- All clarifying questions asked UPFRONT

This is the key to reducing back-and-forth during execution.
"""

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from cortex.intelligence.signals import Signal
except ImportError:
    from intelligence.signals import Signal  # type: ignore[no-redef]


@dataclass
class TaskContract:
    """Comprehensive task specification - eliminates ambiguity."""

    # Core definition
    signal_id: str
    title: str
    description: str

    # Requirements (WHAT must be achieved)
    requirements: List[str]

    # Constraints (WHAT cannot change)
    constraints: List[str]

    # Success criteria (HOW we verify)
    success_criteria: Dict[str, Any]  # {"tests": [...], "metrics": {...}, "benchmarks": [...]}

    # Dependencies (WHAT must exist first)
    dependencies: List[str]

    # Human gates (WHERE approval mandatory)
    human_gates: List[str]  # e.g., ["START", "DEPLOY", "PRODUCTION"]

    # Risk classification
    risk_level: str  # "low", "medium", "high", "critical"
    auto_executable: bool  # Can this run without human approval?

    # Autonomy budget
    max_attempts: int = 3
    max_cost_usd: float = 5.00
    escalate_conditions: List[str] = field(
        default_factory=lambda: ["tests_fail_twice", "metric_regression", "cost_exceeded"]
    )

    # Context for execution
    relevant_files: List[str] = field(default_factory=list)
    relevant_docs: List[str] = field(default_factory=list)
    similar_past_work: List[str] = field(default_factory=list)

    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    contract_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "contract_id": self.contract_id,
            "signal_id": self.signal_id,
            "title": self.title,
            "description": self.description,
            "requirements": self.requirements,
            "constraints": self.constraints,
            "success_criteria": self.success_criteria,
            "dependencies": self.dependencies,
            "human_gates": self.human_gates,
            "risk_level": self.risk_level,
            "auto_executable": self.auto_executable,
            "max_attempts": self.max_attempts,
            "max_cost_usd": self.max_cost_usd,
            "escalate_conditions": self.escalate_conditions,
            "relevant_files": self.relevant_files,
            "relevant_docs": self.relevant_docs,
            "similar_past_work": self.similar_past_work,
            "created_at": self.created_at.isoformat(),
        }


class ContractGenerator:
    """Opus-powered contract generation - asks ALL questions upfront."""

    def __init__(self, root_dir: str = os.environ.get("CORTEX_ROOT_DIR", str(Path.cwd()))):
        self.root_dir = Path(root_dir)
        self.cache_dir = Path.home() / ".cortex" / "contracts"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Initialize AI client — prefer conductor async for non-blocking calls
        self._conductor_available = False
        self._conductor_async_available = False
        try:
            from cortex.conductor import async_call as conductor_async_call
            from cortex.conductor import call as conductor_call

            self._conductor_call = conductor_call
            self._conductor_async_call = conductor_async_call
            self._conductor_available = True
            self._conductor_async_available = True
        except ImportError:
            try:
                from cortex.conductor import call as conductor_call

                self._conductor_call = conductor_call
                self._conductor_available = True
            except ImportError:
                from anthropic import Anthropic

                api_key = os.getenv("ANTHROPIC_API_KEY")
                if not api_key:
                    raise ValueError("ANTHROPIC_API_KEY environment variable not set")
                self._anthropic_client = Anthropic(api_key=api_key)

    async def generate_contract(
        self, signal: Signal, user_answers: Optional[Dict[str, str]] = None
    ) -> TaskContract:
        """
        Generate comprehensive contract that eliminates mid-execution questions.

        This is the KEY to eliminating back-and-forth:
        - Analyzes signal context deeply
        - Queries Cortex for similar past work
        - Identifies ALL potential ambiguities
        - Generates specific, unambiguous requirements
        - Defines measurable success criteria
        - Specifies mandatory human gates

        Args:
            signal: The signal to generate contract for
            user_answers: Optional answers to clarifying questions

        Returns:
            TaskContract with complete specification
        """

        # 1. Query Cortex memory for similar work
        similar_work = self._query_cortex_memory(signal)

        # 2. Analyze files/context
        relevant_files = self._identify_relevant_files(signal)

        # 3. Read sample file contents for context
        file_contents_sample = self._read_file_samples(relevant_files[:5])

        # 4. Generate contract via Opus
        prompt = self._build_contract_prompt(
            signal, similar_work, relevant_files, file_contents_sample, user_answers
        )

        try:
            # Route through conductor — prefer async to avoid blocking event loop
            if self._conductor_async_available:
                result = await self._conductor_async_call(
                    prompt,
                    use_case="architecture",
                    max_tokens=8000,
                )
                response_text = result.content
            elif self._conductor_available:
                import asyncio

                result = await asyncio.to_thread(
                    self._conductor_call,
                    prompt,
                    use_case="architecture",
                    max_tokens=8000,
                )
                response_text = result.content
            else:
                import asyncio

                response = await asyncio.to_thread(
                    self._anthropic_client.messages.create,
                    model="claude-opus-4-6",
                    max_tokens=8000,
                    messages=[{"role": "user", "content": prompt}],
                )
                response_text = response.content[0].text

            # Parse response
            contract_data = self._parse_contract_response(response_text)

            # 5. Build TaskContract
            contract = TaskContract(
                contract_id=f"contract_{signal.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                signal_id=signal.id,
                title=signal.title,
                description=signal.description,
                requirements=contract_data["requirements"],
                constraints=contract_data["constraints"],
                success_criteria=contract_data["success_criteria"],
                dependencies=contract_data["dependencies"],
                human_gates=contract_data.get("human_gates", ["START"]),
                risk_level=contract_data["risk_level"],
                auto_executable=(contract_data["risk_level"] in ["low", "medium"]),
                max_attempts=3,
                max_cost_usd=10.0 if contract_data["risk_level"] == "high" else 5.0,
                escalate_conditions=contract_data.get(
                    "escalate_conditions",
                    ["tests_fail_twice", "metric_regression", "cost_exceeded"],
                ),
                relevant_files=relevant_files,
                relevant_docs=[],
                similar_past_work=similar_work,
            )

            # Cache contract
            self._cache_contract(contract)

            return contract

        except Exception:
            # Fallback: Generate basic contract
            return self._generate_fallback_contract(signal)

    def _build_contract_prompt(
        self,
        signal: Signal,
        similar_work: List[str],
        relevant_files: List[str],
        file_contents_sample: str,
        user_answers: Optional[Dict[str, str]] = None,
    ) -> str:
        """Build comprehensive prompt for Opus to generate contract."""

        user_answers_section = ""
        if user_answers:
            newline = "\n"
            qa_lines = newline.join(f"Q: {q}\nA: {a}" for q, a in user_answers.items())
            user_answers_section = f"""

USER ANSWERS TO CLARIFYING QUESTIONS:
{qa_lines}
"""

        prompt = f"""You are a technical architect generating a comprehensive task contract.

SIGNAL:
Title: {signal.title}
Type: {signal.type.value}
Severity: {signal.severity}

DESCRIPTION:
{signal.description}

CONTEXT:
{json.dumps(signal.context, indent=2)}

EVIDENCE:
{chr(10).join(f"- {e}" for e in signal.evidence)}

ESTIMATED IMPACT:
{signal.estimated_impact}

SIMILAR PAST WORK:
{chr(10).join(f"- {w}" for w in similar_work) if similar_work else "None found"}

RELEVANT FILES ({len(relevant_files)} total):
{chr(10).join(relevant_files[:10])}

FILE CONTENTS SAMPLE:
{file_contents_sample}
{user_answers_section}

YOUR TASK:
Generate a comprehensive task contract that answers EVERY question an implementer might have.
The goal is ZERO back-and-forth during execution.

Include:

1. REQUIREMENTS: Specific, measurable, unambiguous statements of what must be achieved.
   - Each requirement should be independently verifiable
   - Use concrete terms, not vague language
   - Example: "Wire FieldSelectiveEnsemble as production default in config.py line 42" not "Update configuration"

2. CONSTRAINTS: What cannot change (API compatibility, performance, security).
   - List specific things that MUST remain unchanged
   - Include performance thresholds, backwards compatibility requirements
   - Example: "API response format must remain unchanged", "Zero downtime deployment required"

3. SUCCESS CRITERIA: Objective tests/metrics that prove completion.
   - Tests: Specific test suites that must pass
   - Metrics: Numeric thresholds (e.g., accuracy >= 0.87, latency < 200ms)
   - Benchmarks: Manual verification steps if needed

4. DEPENDENCIES: What must exist before work can start.
   - Files, data, services that must be available
   - Example: "GRIB sample data in tests/fixtures/", "Feature flag framework deployed"

5. HUMAN GATES: Where mandatory human approval is needed.
   - Options: START (before beginning), REVIEW (before deployment), PRODUCTION (before prod push)
   - Only include if truly necessary (deployments, breaking changes, security)

6. RISK ASSESSMENT: Classify risk level.
   - low: Tests, docs, analysis - no production impact
   - medium: Feature additions, refactors - tested, reversible
   - high: Deployments, API changes - production impact
   - critical: Security fixes, data migrations - high stakes

7. CLARIFYING QUESTIONS: If ANY ambiguity exists, list questions for human.
   - Only ask if answer significantly affects implementation
   - Make questions specific and actionable
   - Example: "Use feature flag or direct cutover?" not "How should we deploy?"

Output ONLY valid JSON in this exact format:
{{
  "requirements": ["Specific requirement 1", "Specific requirement 2"],
  "constraints": ["Must maintain API compatibility", "Zero downtime deployment"],
  "success_criteria": {{
    "tests": ["Integration tests pass", "Coverage > 80%"],
    "metrics": {{"accuracy": ">= 0.87", "latency_p95_ms": "< 200"}},
    "benchmarks": ["Manual QA checklist completed"]
  }},
  "dependencies": ["GRIB data available", "Test fixtures exist"],
  "human_gates": ["PRODUCTION"],
  "risk_level": "medium",
  "escalate_conditions": ["tests_fail_twice", "metric_regression"],
  "clarifying_questions": ["Should we use feature flag or direct cutover?"]
}}

IMPORTANT: Output ONLY the JSON, no other text."""

        return prompt

    def _parse_contract_response(self, response_text: str) -> Dict[str, Any]:
        """Parse Opus response into contract data."""
        # Extract JSON from response (handles cases where model adds explanation)
        json_start = response_text.find("{")
        json_end = response_text.rfind("}") + 1

        if json_start == -1 or json_end == 0:
            raise ValueError("No JSON found in response")

        json_str = response_text[json_start:json_end]
        return json.loads(json_str)

    def _query_cortex_memory(self, signal: Signal) -> List[str]:
        """Query Cortex for similar past work."""
        # TODO: Integrate with Cortex intelligence system
        # For now, return placeholder
        return [
            "Similar deployment in Vortex backend on 2026-01-15",
            "Feature flag pattern used in Alpha Arena",
        ]

    def _identify_relevant_files(self, signal: Signal) -> List[str]:
        """Identify files relevant to this signal."""
        relevant_files = []
        project = signal.context.get("project", "")

        if project == "vortex-backend":
            base_dir = self.root_dir / "Vortex" / "backend"
        elif project == "Alpha Arena":
            base_dir = self.root_dir / "alpha_arena"
        elif project == "Cortex":
            base_dir = self.root_dir / "cortex"
        else:
            base_dir = self.root_dir

        # Search for relevant files based on signal type
        if signal.type.value == "validation_gap":
            # Look for model files, config files
            for pattern in ["**/models/*.py", "**/config*.py", "**/ensemble*.py"]:
                relevant_files.extend(str(f) for f in base_dir.glob(pattern))

        # Limit to 20 files
        return relevant_files[:20]

    def _read_file_samples(self, files: List[str]) -> str:
        """Read sample content from files for context."""
        samples = []

        for file_path in files[:3]:  # Only first 3 files
            try:
                path = Path(file_path)
                if path.exists() and path.stat().st_size < 100_000:  # Skip large files
                    content = path.read_text()
                    # Take first 50 lines
                    lines = content.split("\n")[:50]
                    samples.append(f"--- {path.name} ---\n" + "\n".join(lines))
            except Exception:
                continue

        return "\n\n".join(samples) if samples else "No file samples available"

    def _generate_fallback_contract(self, signal: Signal) -> TaskContract:
        """Generate basic contract when Opus fails."""
        return TaskContract(
            contract_id=f"fallback_{signal.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            signal_id=signal.id,
            title=signal.title,
            description=signal.description,
            requirements=[
                f"Address the issue: {signal.description}",
                "Ensure all tests pass",
                "Update relevant documentation",
            ],
            constraints=[
                "Maintain API compatibility",
                "Zero downtime deployment if production change",
            ],
            success_criteria={
                "tests": ["All unit tests pass", "All integration tests pass"],
                "metrics": {},
                "benchmarks": ["Manual verification of fix"],
            },
            dependencies=[],
            human_gates=["START", "PRODUCTION"],
            risk_level="medium",
            auto_executable=False,  # Fallback contracts require approval
            max_attempts=3,
            max_cost_usd=5.00,
            escalate_conditions=["tests_fail_twice", "cost_exceeded"],
            relevant_files=[],
            relevant_docs=[],
            similar_past_work=[],
        )

    def _cache_contract(self, contract: TaskContract) -> None:
        """Cache contract to disk."""
        cache_file = self.cache_dir / f"{contract.contract_id}.json"
        cache_file.write_text(json.dumps(contract.to_dict(), indent=2))

    def load_contract(self, contract_id: str) -> Optional[TaskContract]:
        """Load contract from cache."""
        cache_file = self.cache_dir / f"{contract_id}.json"

        if not cache_file.exists():
            return None

        try:
            data = json.loads(cache_file.read_text())

            return TaskContract(
                contract_id=data["contract_id"],
                signal_id=data["signal_id"],
                title=data["title"],
                description=data["description"],
                requirements=data["requirements"],
                constraints=data["constraints"],
                success_criteria=data["success_criteria"],
                dependencies=data["dependencies"],
                human_gates=data["human_gates"],
                risk_level=data["risk_level"],
                auto_executable=data["auto_executable"],
                max_attempts=data["max_attempts"],
                max_cost_usd=data["max_cost_usd"],
                escalate_conditions=data["escalate_conditions"],
                relevant_files=data["relevant_files"],
                relevant_docs=data["relevant_docs"],
                similar_past_work=data["similar_past_work"],
                created_at=datetime.fromisoformat(data["created_at"]),
            )
        except (json.JSONDecodeError, KeyError):
            return None


if __name__ == "__main__":
    import asyncio

    from intelligence.signals import SignalDetector

    async def test_contract_generation():
        # Detect signals
        detector = SignalDetector()
        signals = detector.detect_all()

        if not signals:
            print("No signals detected")
            return

        # Generate contract for first signal
        signal = signals[0]
        print(f"Generating contract for: {signal.title}\n")

        generator = ContractGenerator()
        contract = await generator.generate_contract(signal)

        print("=== GENERATED CONTRACT ===")
        print(f"Contract ID: {contract.contract_id}")
        print(f"Risk Level: {contract.risk_level}")
        print(f"Auto-executable: {contract.auto_executable}")
        print(f"\nRequirements ({len(contract.requirements)}):")
        for req in contract.requirements:
            print(f"  - {req}")
        print("\nSuccess Criteria:")
        print(f"  Tests: {contract.success_criteria.get('tests', [])}")
        print(f"  Metrics: {contract.success_criteria.get('metrics', {})}")

    asyncio.run(test_contract_generation())
