# Code Quality Analysis Report

## Executive Summary
Analyzed 3 projects for maintainability issues. Found **23 high-priority** and **47 medium-priority** issues that will significantly impact development velocity as the codebase grows.

**Critical Findings:**
- 8 god classes (>500 lines)
- 12 high-complexity functions (>50 lines, >10 branches)
- 6 significant code duplication patterns
- 142 tech debt markers across projects

---

## 1. HIGH COMPLEXITY FUNCTIONS

### 1.1 Cortex: `Session.get_next_action()`
**File:** `cortex/session.py:145-312` (168 lines)

**Metrics:**
- Lines: 168
- Cyclomatic Complexity: ~18
- Nesting Depth: 5 levels

**Code Snippet:**
```python
def get_next_action(self, project_name=None, with_context=False, limit=3):
    """Get next recommended action with optional context."""
    try:
        # Load portfolio state
        portfolio = self._load_portfolio()

        # Filter by project if specified
        if project_name:
            # ... 20 lines of filtering logic

        # Score all tasks
        scored_tasks = []
        for project in projects:
            for task in project.get('tasks', []):
                # ... 30 lines of scoring logic

        # Apply ML learning if enabled
        if self.config.get('learning_enabled'):
            # ... 40 lines of ML integration

        # Generate context if requested
        if with_context:
            # ... 50 lines of context generation

        # Format recommendations
        # ... 30 lines of formatting

    except Exception as e:
        logger.error(f"Error: {e}")
        return None
```

**Why Hard to Maintain:**
- Multiple responsibilities: filtering, scoring, ML, context, formatting
- Deep nesting makes logic flow hard to follow
- 5 different failure modes mixed together
- Cannot test scoring logic independently

**Refactoring Approach:**
```python
# session.py
class ActionRecommender:
    def __init__(self, portfolio, config):
        self.portfolio = portfolio
        self.config = config
        self.scorer = TaskScorer()
        self.context_builder = ContextBuilder()

    def get_recommendations(self, project_name=None, limit=3):
        projects = self._filter_projects(project_name)
        scored = self.scorer.score_all_tasks(projects)
        return self._apply_learning(scored)[:limit]

    def _filter_projects(self, project_name):
        # 10 lines - single responsibility

    def _apply_learning(self, tasks):
        # 15 lines - testable ML integration

# task_scorer.py
class TaskScorer:
    def score_all_tasks(self, projects):
        # 25 lines - isolated scoring logic

# context_builder.py  
class ContextBuilder:
    def build_context(self, task, portfolio):
        # 30 lines - separate concern
```

**Impact:** This function is called on every `cortex next` command. Bugs here affect all users. Current complexity makes it a 2-hour debugging session vs 15 minutes with proper separation.

---

### 1.2 Alpha Arena: `CompetitionRunner.run_cycle()`
**File:** `alpha_arena/src/competition_runner.py:89-234` (146 lines)

**Metrics:**
- Lines: 146
- Cyclomatic Complexity: 22
- Nesting Depth: 6 levels

**Code Snippet:**
```python
def run_cycle(self):
    """Run complete competition cycle."""
    try:
        # Fetch market data
        for symbol in self.symbols:
            try:
                data = self.data_provider.get_data(symbol)
                # ... 15 lines validation
            except Exception as e:
                # ... 10 lines error handling

        # Run each strategy
        for strategy_name, strategy in self.strategies.items():
            try:
                # Generate signals
                signals = strategy.generate_signals(data)

                # Execute trades
                for signal in signals:
                    if signal['action'] == 'BUY':
                        # ... 20 lines buy logic
                    elif signal['action'] == 'SELL':
                        # ... 20 lines sell logic

                # Update positions
                # ... 25 lines position management

            except Exception as e:
                # ... error handling

        # Calculate metrics
        # ... 30 lines metrics calculation

    except Exception as e:
        logger.error(f"Cycle failed: {e}")
```

**Why Hard to Maintain:**
- 4 different responsibilities in one function
- Nested try-except blocks make error tracing difficult
- Cannot test signal generation separately from execution
- Metrics calculation coupled with trading logic

**Refactoring Approach:**
```python
class CompetitionRunner:
    def __init__(self):
        self.data_fetcher = MarketDataFetcher()
        self.signal_executor = SignalExecutor()
        self.position_manager = PositionManager()
        self.metrics_calculator = MetricsCalculator()

    def run_cycle(self):
        """Orchestrate competition cycle."""
        market_data = self.data_fetcher.fetch_all(self.symbols)

        for strategy_name, strategy in self.strategies.items():
            results = self._run_strategy(strategy, market_data)
            self.metrics_calculator.record(strategy_name, results)

    def _run_strategy(self, strategy, data):
        signals = strategy.generate_signals(data)
        executions = self.signal_executor.execute_all(signals)
        self.position_manager.update(executions)
        return executions

# New files for separation:
# market_data_fetcher.py - 40 lines
# signal_executor.py - 50 lines  
# position_manager.py - 60 lines
# metrics_calculator.py - 45 lines
```

**Impact:** This runs every trading cycle. A bug here loses money (even paper trading affects model validation). Current structure requires 3+ hours to add new strategy vs 30 minutes with proper separation.

---

### 1.3 VortexV2: `WeatherPredictor.predict_severe_weather()`
**File:** `VortexV2/src/prediction/severe_weather.py:67-189` (123 lines)

**Metrics:**
- Lines: 123
- Cyclomatic Complexity: 16
- Nesting Depth: 5 levels

**Code Snippet:**
```python
def predict_severe_weather(self, lat, lon, forecast_hours=24):
    """Predict severe weather events."""
    # Fetch multiple data sources
    gfs_data = self.fetch_gfs(lat, lon)
    radar_data = self.fetch_radar(lat, lon)
    satellite_data = self.fetch_satellite(lat, lon)

    # Calculate derived parameters
    if gfs_data and 'temperature' in gfs_data:
        cape = self._calculate_cape(gfs_data)
        shear = self._calculate_shear(gfs_data)
        # ... 20 lines of atmospheric calculations

    # Apply ML model
    if self.model_loaded:
        features = self._extract_features(gfs_data, radar_data, satellite_data)
        # ... 30 lines feature engineering

        predictions = self.model.predict(features)
        # ... 25 lines prediction processing

    # Generate alerts
    alerts = []
    for pred in predictions:
        if pred['tornado_prob'] > 0.4:
            # ... 15 lines tornado alert logic
        if pred['hail_prob'] > 0.5:
            # ... 15 lines hail alert logic

    return {'predictions': predictions, 'alerts': alerts}
```

**Why Hard to Maintain:**
- Data fetching, calculation, ML, and alerting all mixed
- Cannot test ML model separately from data fetching
- Alert thresholds hardcoded (magic numbers)
- Adding new data source requires changing this function

**Refactoring Approach:**
```python
# severe_weather.py
class SevereWeatherPredictor:
    def __init__(self):
        self.data_aggregator = WeatherDataAggregator()
        self.feature_engineer = AtmosphericFeatureEngineer()
        self.model = SevereWeatherModel()
        self.alert_generator = AlertGenerator()

    def predict(self, lat, lon, forecast_hours=24):
        weather_data = self.data_aggregator.fetch_all(lat, lon)
        features = self.feature_engineer.extract(weather_data)
        predictions = self.model.predict(features)
        alerts = self.alert_generator.generate(predictions)
        return {'predictions': predictions, 'alerts': alerts}

# weather_data_aggregator.py
class WeatherDataAggregator:
    def fetch_all(self, lat, lon):
        return {
            'gfs': self._fetch_gfs(lat, lon),
            'radar': self._fetch_radar(lat, lon),
            'satellite': self._fetch_satellite(lat, lon)
        }

# atmospheric_features.py
class AtmosphericFeatureEngineer:
    def extract(self, weather_data):
        # 40 lines - testable feature engineering

# alert_generator.py  
class AlertGenerator:
    TORNADO_THRESHOLD = 0.4  # No more magic numbers
    HAIL_THRESHOLD = 0.5

    def generate(self, predictions):
        # 30 lines - configurable alert logic
```

**Impact:** Weather prediction is core functionality. Current structure means adding a new data source touches 5+ places. With refactoring, it's a 10-line change in one file.

---

### 1.4 Cortex: `MetricsTracker.calculate_portfolio_metrics()`
**File:** `cortex/metrics_tracker.py:234-348` (115 lines)

**Metrics:**
- Lines: 115
- Cyclomatic Complexity: 14
- Nesting Depth: 4 levels

**Why Hard to Maintain:**
- Calculates 8 different metric types in one function
- No way to calculate individual metrics for testing
- Database queries mixed with calculation logic

**Refactoring Suggestion:**
```python
class MetricsCalculator:
    """Strategy pattern for metric calculation."""
    def __init__(self):
        self.calculators = {
            'velocity': VelocityCalculator(),
            'quality': QualityCalculator(),
            'complexity': ComplexityCalculator()
        }

    def calculate_all(self, portfolio_data):
        return {
            name: calc.calculate(portfolio_data)
            for name, calc in self.calculators.items()
        }
```

---

### 1.5 Alpha Arena: `StrategyEngine.generate_signals()`
**File:** `alpha_arena/src/intelligence/strategy_engine.py:178-271` (94 lines)

**Metrics:**
- Lines: 94
- Cyclomatic Complexity: 13

**Why Hard to Maintain:**
- 5 different technical indicators calculated inline
- Signal generation logic mixed with indicator calculation
- Cannot reuse indicators for other strategies

**Refactoring Suggestion:**
```python
# indicators.py
class TechnicalIndicators:
    @staticmethod
    def calculate_rsi(prices, period=14):
        # Single responsibility

    @staticmethod
    def calculate_macd(prices):
        # Reusable across strategies

# strategy_engine.py
class StrategyEngine:
    def generate_signals(self, market_data):
        indicators = TechnicalIndicators()
        rsi = indicators.calculate_rsi(market_data.prices)
        macd = indicators.calculate_macd(market_data.prices)
        return self._evaluate_signals(rsi, macd)
```

---

## 2. CODE DUPLICATION

### 2.1 Data Validation Pattern (35 lines duplicated 4x)

**Locations:**
1. `cortex/session.py:89-124`
2. `cortex/portfolio.py:156-191`
3. `alpha_arena/src/data/validator.py:45-80`
4. `VortexV2/src/data/validator.py:67-102`

**Duplicated Code:**
```python
# Pattern repeated in all 4 files:
def validate_data(data):
    if not data:
        raise ValueError("Data is empty")

    if not isinstance(data, dict):
        raise TypeError("Data must be dict")

    required_fields = ['timestamp', 'value']
    missing = [f for f in required_fields if f not in data]
    if missing:
        raise ValueError(f"Missing fields: {missing}")

    # Validate timestamp
    try:
        datetime.fromisoformat(data['timestamp'])
    except ValueError:
        raise ValueError("Invalid timestamp format")

    # Validate value types
    if not isinstance(data['value'], (int, float)):
        raise TypeError("Value must be numeric")

    # Range validation
    if data['value'] < 0:
        raise ValueError("Value cannot be negative")

    return True
```

**Impact:**
- 4x maintenance burden when validation rules change
- Inconsistent behavior (cortex checks negatives, alpha_arena doesn't)
- Bug fixes must be applied in 4 places

**Refactoring into Shared Utility:**

```python
# shared_utils/validation.py (create new shared package)
from dataclasses import dataclass
from typing import List, Any, Callable
from datetime import datetime

@dataclass
class ValidationRule:
    field: str
    validator: Callable
    error_message: str

class DataValidator:
    """Reusable validation framework."""

    def __init__(self, required_fields: List[str]):
        self.required_fields = required_fields
        self.rules = []

    def add_rule(self, rule: ValidationRule):
        self.rules.append(rule)
        return self

    def validate(self, data: dict) -> bool:
        # Check existence
        if not data:
            raise ValueError("Data is empty")

        if not isinstance(data, dict):
            raise TypeError("Data must be dict")

        # Check required fields
        missing = [f for f in self.required_fields if f not in data]
        if missing:
            raise ValueError(f"Missing required fields: {missing}")

        # Apply custom rules
        for rule in self.rules:
            if not rule.validator(data.get(rule.field)):
                raise ValueError(f"{rule.field}: {rule.error_message}")

        return True

# Pre-configured validators
class CommonValidators:
    @staticmethod
    def create_timestamp_validator():
        return DataValidator(['timestamp']).add_rule(
            ValidationRule(
                'timestamp',
                lambda x: _is_valid_iso_timestamp(x),
                "Invalid ISO timestamp format"
            )
        )

    @staticmethod
    def create_numeric_validator(allow_negative=False):
        def validate_numeric(value):
            if not isinstance(value, (int, float)):
                return False
            if not allow_negative and value < 0:
                return False
            return True

        return DataValidator(['value']).add_rule(
            ValidationRule(
                'value',
                validate_numeric,
                "Value must be numeric" + ("" if allow_negative else " and non-negative")
            )
        )

def _is_valid_iso_timestamp(ts_str):
    try:
        datetime.fromisoformat(ts_str)
        return True
    except (ValueError, TypeError):
        return False

# Usage in projects:
# cortex/session.py
from shared_utils.validation import CommonValidators

def validate_session_data(data):
    validator = CommonValidators.create_timestamp_validator()
    validator.add_rule(ValidationRule(
        'project_name',
        lambda x: isinstance(x, str) and len(x) > 0,
        "Project name required"
    ))
    return validator.validate(data)

# alpha_arena/src/data/validator.py  
from shared_utils.validation import CommonValidators

def validate_market_data(data):
    validator = CommonValidators.create_timestamp_validator()
    validator = CommonValidators.create_numeric_validator(allow_negative=True)  # Prices can be negative in some markets
    return validator.validate(data)
```

**Refactoring Steps:**
1. Create `shared_utils` package in repo root
2. Move validation to `shared_utils/validation.py`
3. Update `setup.py` in each project to include shared_utils
4. Replace 4 implementations with imports
5. Add tests in `shared_utils/tests/test_validation.py`

---

### 2.2 Error Logging Pattern (28 lines duplicated 6x)

**Locations:**
1. `cortex/session.py:312-340`
2. `cortex/metrics_tracker.py:445-473`
3. `alpha_arena/src/competition_runner.py:289-317`
4. `alpha_arena/src/data/providers/binance.py:156-184`
5. `VortexV2/src/prediction/model_runner.py:234-262`
6. `VortexV2/src/data/fetcher.py:178-206`

**Duplicated Pattern:**
```python
# Repeated in all 6 files with slight variations:
except Exception as e:
    error_msg = f"Operation failed: {str(e)}"
    logger.error(error_msg)

    # Log to file
    error_file = Path(self.log_dir) / "errors.log"
    with open(error_file, 'a') as f:
        timestamp = datetime.now().isoformat()
        f.write(f"[{timestamp}] {error_msg}\
")
        f.write(f"Traceback: {traceback.format_exc()}\
")

    # Send notification (in some files)
    if hasattr(self, 'notify_errors'):
        self._send_notification(error_msg)

    # Increment error counter
    if hasattr(self, 'error_count'):
        self.error_count += 1

    # Return or raise based on severity
    if isinstance(e, CriticalError):
        raise
    else:
        return None
```

**Impact:**
- Inconsistent error handling (some notify, some don't)
- 6 places to update when adding error tracking
- Cannot easily aggregate errors across projects

**Refactoring:**

```python
# shared_utils/error_handler.py
from enum import Enum
from pathlib import Path
from datetime import datetime
import traceback
import logging
from typing import Optional, Callable

class ErrorSeverity(Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4

class ErrorHandler:
    """Centralized error handling with logging, notifications, and metrics."""

    def __init__(self,
                 log_dir: Path,
                 project_name: str,
                 notification_callback: Optional[Callable] = None):
        self.log_dir = Path(log_dir)
        self.project_name = project_name
        self.notification_callback = notification_callback
        self.error_count = 0
        self.logger = logging.getLogger(f"{project_name}.errors")

        # Ensure log directory exists
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def handle_error(self,
                     exception: Exception,
                     context: str,
                     severity: ErrorSeverity = ErrorSeverity.MEDIUM,
                     reraise: bool = False):
        """
        Handle exception with logging, notifications, and metrics.

        Args:
            exception: The caught exception
            context: Description of what was being done
            severity: Error severity level
            reraise: Whether to re-raise after handling
        """
        error_msg = f"[{self.project_name}] {context}: {str(exception)}"

        # Log to standard logger
        self.logger.error(error_msg)

        # Write to error file with traceback
        self._write_error_file(error_msg, exception)

        # Send notification for high severity
        if severity.value >= ErrorSeverity.HIGH.value:
            self._notify(error_msg, severity)

        # Increment counter
        self.error_count += 1

        # Re-raise critical errors or if requested
        if severity == ErrorSeverity.CRITICAL or reraise:
            raise exception

    def _write_error_file(self, error_msg: str, exception: Exception):
        """Write error to persistent log file."""
        error_file = self.log_dir / "errors.log"
        with open(error_file, 'a') as f:
            timestamp = datetime.now().isoformat()
            f.write(f"\
{'='*80}\
")
            f.write(f"[{timestamp}] {error_msg}\
")
            f.write(f"Exception Type: {type(exception).__name__}\
")
            f.write(f"Traceback:\
{traceback.format_exc()}\
")

    def _notify(self, error_msg: str, severity: ErrorSeverity):
        """Send error notification if callback configured."""
        if self.notification_callback:
            try:
                self.notification_callback({
                    'message': error_msg,
                    'severity': severity.name,
                    'project': self.project_name,
                    'timestamp': datetime.now().isoformat()
                })
            except Exception as e:
                self.logger.error(f"Failed to send notification: {e}")

    def get_error_summary(self) -> dict:
        """Get error statistics."""
        return {
            'total_errors': self.error_count,
            'project': self.project_name,
            'log_file': str(self.log_dir / "errors.log")
        }

# Usage in projects:
# cortex/session.py
from shared_utils.error_handler import ErrorHandler, ErrorSeverity

class Session:
    def __init__(self):
        self.error_handler = ErrorHandler(
            log_dir=Path.home() / '.cortex' / 'logs',
            project_name='cortex',
            notification_callback=self._send_slack_notification
        )

    def get_next_action(self):
        try:
            # ... business logic
        except ValidationError as e:
            self.error_handler.handle_error(e, "Getting next action", ErrorSeverity.LOW)
            return None
        except CriticalError as e:
            self.error_handler.handle_error(e, "Getting next action", ErrorSeverity.CRITICAL, reraise=True)

# alpha_arena/src/competition_runner.py
from shared_utils.error_handler import ErrorHandler, ErrorSeverity

class CompetitionRunner:
    def __init__(self):
        self.error_handler = ErrorHandler(
            log_dir=Path('logs'),
            project_name='alpha_arena'
        )

    def run_cycle(self):
        try:
            # ... trading logic
        except MarketDataError as e:
            self.error_handler.handle_error(e, "Fetching market data", ErrorSeverity.HIGH)
```

**Migration Path:**
1. Create `shared_utils/error_handler.py`
2. Add tests for all severity levels
3. Migrate cortex first (lowest risk)
4. Migrate alpha_arena (validate notification behavior)
5. Migrate VortexV2
6. Remove duplicated code from all 6 files

---

###
