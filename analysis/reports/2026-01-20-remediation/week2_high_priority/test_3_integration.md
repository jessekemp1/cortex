# test_3_integration

# Integration Tests for Trading Pipeline

## Implementation Overview

I'll create a comprehensive integration test suite for the Strategy → Broker → Position Tracking flow, including weather intelligence integration and multi-strategy competition testing.

## File Structure

```
alpha_arena/tests/integration/
├── __init__.py
├── conftest.py                    # Shared fixtures
├── test_trading_pipeline.py       # Full pipeline tests
├── test_weather_integration.py    # Weather → Trading integration
├── test_multi_strategy.py         # Competition fairness tests
├── test_error_recovery.py         # Error handling tests
├── mocks/
│   ├── __init__.py
│   ├── mock_broker.py
│   ├── mock_market_data.py
│   └── mock_weather_service.py
├── fixtures/
│   ├── __init__.py
│   ├── market_data.py
│   ├── weather_data.py
│   └── strategy_configs.py
└── generators/
    ├── __init__.py
    ├── order_generator.py
    ├── price_generator.py
    └── signal_generator.py
```

## Implementation

### 1. Core Test Configuration (`conftest.py`)

```python
# alpha_arena/tests/integration/conftest.py
"""
Shared fixtures and configuration for integration tests.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock
import logging

# Configure logging for tests
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


# ============================================================================
# Event Loop Configuration
# ============================================================================

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ============================================================================
# Database Fixtures
# ============================================================================

@pytest.fixture(scope="function")
async def test_database():
    """Create a fresh test database for each test."""
    from alpha_arena.infrastructure.database import Database
    
    db = Database(connection_string="sqlite:///:memory:")
    await db.initialize()
    await db.create_tables()
    
    yield db
    
    await db.cleanup()


@pytest.fixture(scope="function")
async def position_repository(test_database):
    """Create position repository with test database."""
    from alpha_arena.infrastructure.repositories import PositionRepository
    
    repo = PositionRepository(database=test_database)
    yield repo


@pytest.fixture(scope="function")
async def order_repository(test_database):
    """Create order repository with test database."""
    from alpha_arena.infrastructure.repositories import OrderRepository
    
    repo = OrderRepository(database=test_database)
    yield repo


# ============================================================================
# Mock Service Fixtures
# ============================================================================

@pytest.fixture
def mock_broker():
    """Create mock broker for testing."""
    from tests.integration.mocks.mock_broker import MockBroker
    
    broker = MockBroker()
    yield broker
    broker.reset()


@pytest.fixture
def mock_market_data():
    """Create mock market data service."""
    from tests.integration.mocks.mock_market_data import MockMarketDataService
    
    service = MockMarketDataService()
    yield service
    service.reset()


@pytest.fixture
def mock_weather_service():
    """Create mock weather service."""
    from tests.integration.mocks.mock_weather_service import MockWeatherService
    
    service = MockWeatherService()
    yield service
    service.reset()


# ============================================================================
# Strategy Fixtures
# ============================================================================

@pytest.fixture
def sample_strategy_config():
    """Return sample strategy configuration."""
    return {
        "strategy_id": "test_strategy_001",
        "name": "Test Momentum Strategy",
        "type": "momentum",
        "parameters": {
            "lookback_period": 20,
            "entry_threshold": 0.02,
            "exit_threshold": -0.01,
            "max_position_size": Decimal("10000"),
            "risk_limit": Decimal("0.02"),
        },
        "universe": ["AAPL", "GOOGL", "MSFT", "AMZN"],
        "enabled": True,
    }


@pytest.fixture
def multiple_strategy_configs():
    """Return multiple strategy configurations for competition tests."""
    return [
        {
            "strategy_id": f"strategy_{i:03d}",
            "name": f"Test Strategy {i}",
            "type": "momentum" if i % 2 == 0 else "mean_reversion",
            "parameters": {
                "lookback_period": 10 + i * 5,
                "entry_threshold": 0.01 + i * 0.005,
                "max_position_size": Decimal("10000"),
            },
            "universe": ["AAPL", "GOOGL", "MSFT"],
            "enabled": True,
        }
        for i in range(5)
    ]


# ============================================================================
# Market Data Fixtures
# ============================================================================

@pytest.fixture
def sample_market_data():
    """Return sample market data for testing."""
    from tests.integration.fixtures.market_data import generate_sample_market_data
    
    return generate_sample_market_data(
        symbols=["AAPL", "GOOGL", "MSFT", "AMZN"],
        days=30,
        base_prices={"AAPL": 150, "GOOGL": 2800, "MSFT": 380, "AMZN": 175},
    )


@pytest.fixture
def realtime_price_feed(mock_market_data):
    """Create a simulated realtime price feed."""
    from tests.integration.generators.price_generator import RealtimePriceGenerator
    
    generator = RealtimePriceGenerator(
        base_service=mock_market_data,
        update_interval=0.1,  # 100ms for fast tests
    )
    yield generator
    generator.stop()


# ============================================================================
# Trading Pipeline Fixtures
# ============================================================================

@pytest.fixture
async def trading_pipeline(
    mock_broker,
    mock_market_data,
    position_repository,
    order_repository,
    sample_strategy_config,
):
    """Create a fully configured trading pipeline for testing."""
    from alpha_arena.core.trading import TradingPipeline
    from alpha_arena.core.strategies import StrategyFactory
    from alpha_arena.core.position_tracking import PositionTracker
    from alpha_arena.core.risk import RiskManager
    
    # Create strategy
    strategy = StrategyFactory.create(sample_strategy_config)
    
    # Create position tracker
    position_tracker = PositionTracker(
        repository=position_repository,
        broker=mock_broker,
    )
    
    # Create risk manager
    risk_manager = RiskManager(
        max_position_size=Decimal("100000"),
        max_daily_loss=Decimal("5000"),
        max_drawdown=Decimal("0.10"),
    )
    
    # Create pipeline
    pipeline = TradingPipeline(
        strategy=strategy,
        broker=mock_broker,
        market_data=mock_market_data,
        position_tracker=position_tracker,
        risk_manager=risk_manager,
        order_repository=order_repository,
    )
    
    await pipeline.initialize()
    
    yield pipeline
    
    await pipeline.shutdown()


@pytest.fixture
async def multi_strategy_pipeline(
    mock_broker,
    mock_market_data,
    test_database,
    multiple_strategy_configs,
):
    """Create pipeline with multiple competing strategies."""
    from alpha_arena.core.trading import MultiStrategyPipeline
    from alpha_arena.core.strategies import StrategyFactory
    
    strategies = [
        StrategyFactory.create(config)
        for config in multiple_strategy_configs
    ]
    
    pipeline = MultiStrategyPipeline(
        strategies=strategies,
        broker=mock_broker,
        market_data=mock_market_data,
        database=test_database,
        fairness_mode="round_robin",
    )
    
    await pipeline.initialize()
    
    yield pipeline
    
    await pipeline.shutdown()


# ============================================================================
# Weather Integration Fixtures
# ============================================================================

@pytest.fixture
def weather_enhanced_pipeline(
    trading_pipeline,
    mock_weather_service,
):
    """Create trading pipeline with weather intelligence integration."""
    from alpha_arena.features.weather import WeatherIntelligenceModule
    
    weather_module = WeatherIntelligenceModule(
        weather_service=mock_weather_service,
        affected_sectors=["energy", "agriculture", "retail"],
    )
    
    trading_pipeline.add_intelligence_module(weather_module)
    
    return trading_pipeline


# ============================================================================
# Test Utilities
# ============================================================================

@pytest.fixture
def assert_eventually():
    """Helper to assert conditions that may take time to become true."""
    async def _assert_eventually(
        condition_func,
        timeout: float = 5.0,
        interval: float = 0.1,
        message: str = "Condition not met within timeout",
    ):
        start_time = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - start_time < timeout:
            if await condition_func() if asyncio.iscoroutinefunction(condition_func) else condition_func():
                return True
            await asyncio.sleep(interval)
        raise AssertionError(message)
    
    return _assert_eventually


@pytest.fixture
def capture_events():
    """Helper to capture events from the trading pipeline."""
    class EventCapture:
        def __init__(self):
            self.events = []
            self._handlers = {}
        
        def handler(self, event_type: str):
            def decorator(func):
                self._handlers[event_type] = func
                return func
            return decorator
        
        async def capture(self, event):
            self.events.append(event)
            handler = self._handlers.get(type(event).__name__)
            if handler:
                await handler(event) if asyncio.iscoroutinefunction(handler) else handler(event)
        
        def get_events(self, event_type: str = None):
            if event_type:
                return [e for e in self.events if type(e).__name__ == event_type]
            return self.events
        
        def clear(self):
            self.events.clear()
    
    return EventCapture()
```

### 2. Mock Broker Implementation

```python
# alpha_arena/tests/integration/mocks/mock_broker.py
"""
Mock broker for integration testing.
Simulates order execution, fills, and position management.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Callable, Any
from uuid import uuid4
import random
import logging

logger = logging.getLogger(__name__)


class OrderStatus(Enum):
    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"


@dataclass
class Order:
    order_id: str
    strategy_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: Decimal
    limit_price: Optional[Decimal] = None
    stop_price: Optional[Decimal] = None
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: Decimal = Decimal("0")
    average_fill_price: Optional[Decimal] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    fills: List["Fill"] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Fill:
    fill_id: str
    order_id: str
    quantity: Decimal
    price: Decimal
    timestamp: datetime
    commission: Decimal = Decimal("0")


@dataclass
class Position:
    symbol: str
    quantity: Decimal
    average_cost: Decimal
    market_value: Decimal
    unrealized_pnl: Decimal
    realized_pnl: Decimal = Decimal("0")


class MockBroker:
    """
    Mock broker that simulates realistic order execution behavior.
    
    Features:
    - Configurable fill latency
    - Partial fills
    - Slippage simulation
    - Commission calculation
    - Order rejection scenarios
    - Position tracking
    """
    
    def __init__(
        self,
        fill_latency_ms: float = 50,
        slippage_bps: float = 5,
        commission_per_share: Decimal = Decimal("0.005"),
        partial_fill_probability: float = 0.1,
        rejection_probability: float = 0.01,
    ):
        self.fill_latency_ms = fill_latency_ms
        self.slippage_bps = slippage_bps
        self.commission_per_share = commission_per_share
        self.partial_fill_probability = partial_fill_probability
        self.rejection_probability = rejection_probability
        
        # State
        self._orders: Dict[str, Order] = {}
        self._positions: Dict[str, Position] = {}
        self._current_prices: Dict[str, Decimal] = {}
        self._cash_balance: Decimal = Decimal("1000000")
        
        # Event handlers
        self._on_fill: List[Callable] = []
        self._on_order_update: List[Callable] = []
        
        # Control
        self._running = False
        self._execution_task: Optional[asyncio.Task] = None
        
        # Test controls
        self._force_rejection = False
        self._force_partial_fill = False
        self._execution_delay_override: Optional[float] = None
        
    # =========================================================================
    # Public API
    # =========================================================================
    
    async def connect(self) -> bool:
        """Connect to the broker (simulated)."""
        logger.info("MockBroker: Connecting...")
        await asyncio.sleep(0.1)  # Simulate connection time
        self._running = True
        self._execution_task = asyncio.create_task(self._execution_loop())
        logger.info("MockBroker: Connected")
        return True
    
    async def disconnect(self) -> None:
        """Disconnect from the broker."""
        logger.info("MockBroker: Disconnecting...")
        self._running = False
        if self._execution_task:
            self._execution_task.cancel()
            try:
                await self._execution_task
            except asyncio.CancelledError:
                pass
        logger.info("MockBroker: Disconnected")
    
    async def submit_order(
        self,
        strategy_id: str,
        symbol: str,
        side: OrderSide,
        quantity: Decimal,
        order_type: OrderType = OrderType.MARKET,
        limit_price: Optional[Decimal] = None,
        stop_price: Optional[Decimal] = None,
        metadata