"""
CortexDBx: Intelligence Layer for Databricks.

Outcome-based learning: track context + strategy + result, calibrate confidence,
surface recommendations. Runs on Databricks (Delta/Unity Catalog) or locally for dev.
"""

__version__ = "0.1.0"

from cortexdbx.synthetic.generator import SyntheticDataGenerator, DOMAIN_CONFIGS
from cortexdbx.calibration.engine import CalibrationEngine, CalibrationState

__all__ = [
    "__version__",
    "SyntheticDataGenerator",
    "DOMAIN_CONFIGS",
    "CalibrationEngine",
    "CalibrationState",
]
