"""
Shared pytest fixtures for CortexDBx tests.

Provides test fixtures for:
- CortexDBx clients (local backend)
- Synthetic data generators
- Calibration engines
- Agent orchestrators
- Temporary data directories

Aligned with cortex/tests/conftest.py testing framework.
"""

import sys
import tempfile
from pathlib import Path

import pytest

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from cortexdbx.agents.orchestrator import AgentOrchestrator
from cortexdbx.calibration.engine import CalibrationEngine
from cortexdbx.sdk.client import CortexDBxClient
from cortexdbx.synthetic.generator import SyntheticDataGenerator

# ============================================================================
# Client Fixtures
# ============================================================================


@pytest.fixture
def client():
    """Create a fresh CortexDBxClient with local backend."""
    return CortexDBxClient()


@pytest.fixture
def orchestrator():
    """Create an AgentOrchestrator for testing."""
    orch = AgentOrchestrator(max_workers=2)
    yield orch
    orch.shutdown()


# ============================================================================
# Generator Fixtures
# ============================================================================


@pytest.fixture
def fraud_generator():
    """Create a generator for fraud_investigation domain."""
    return SyntheticDataGenerator("fraud_investigation", seed=42)


@pytest.fixture
def clinical_generator():
    """Create a generator for clinical_trial domain."""
    return SyntheticDataGenerator("clinical_trial", seed=42)


@pytest.fixture(
    params=[
        "fraud_investigation",
        "clinical_trial",
        "maintenance",
        "marketing_campaign",
        "security_incident",
        "supply_chain",
    ]
)
def domain_generator(request):
    """Parametrized generator for all 6 domains."""
    return SyntheticDataGenerator(request.param, seed=42)


# ============================================================================
# Calibration Fixtures
# ============================================================================


@pytest.fixture
def calibration_engine():
    """Create a fresh CalibrationEngine."""
    return CalibrationEngine()


@pytest.fixture
def seeded_calibration_engine(fraud_generator):
    """Create a CalibrationEngine pre-seeded with fraud data."""
    engine = CalibrationEngine()
    data = list(fraud_generator.generate_dataset(100))

    for record in data:
        engine.update(
            record["context"]["context_id"],
            record["strategy"]["strategy_id"],
            record["outcome"]["result"],
        )

    return engine


# ============================================================================
# Data Fixtures
# ============================================================================


@pytest.fixture
def sample_outcomes(fraud_generator):
    """Generate sample outcomes for testing."""
    data = list(fraud_generator.generate_dataset(50))
    return [
        {
            "context_id": r["context"]["context_id"],
            "strategy_id": r["strategy"]["strategy_id"],
            "result": r["outcome"]["result"],
            "domain": r["context"]["domain"],
        }
        for r in data
    ]


@pytest.fixture
def temp_data_dir():
    """Create a temporary directory for test data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


# ============================================================================
# Markers
# ============================================================================


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line("markers", "e2e: marks tests as end-to-end integration tests")
    config.addinivalue_line("markers", "databricks: marks tests requiring Databricks connection")
