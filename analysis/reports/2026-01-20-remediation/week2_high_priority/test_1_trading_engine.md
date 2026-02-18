# test_1_trading_engine

# Comprehensive Test Suite for Alpha Arena Trading Engine

## Executive Summary

I'll create a complete test suite for the critical trading functions that currently have no tests. This includes unit tests, integration tests, mock fixtures, and a coverage configuration.

## Implementation Plan

### 1. Directory Structure

```
alpha_arena/tests/
├── __init__.py
├── conftest.py                    # Shared fixtures
├── test_strategy_engine.py        # Tests for generate_signals, calculate_position_size
├── test_execute_trades.py         # Tests for execute_trades
├── test_integration.py            # Integration tests
├── mocks/
│   ├── __init__.py
│   ├── mock_broker.py
│   └── mock_market_data.py
└── fixtures/
    ├── __init__.py
    └── sample_data.py
```

### 2. Complete Implementation

#### File: `alpha_arena/tests/conftest.py`

```python
"""
Shared pytest fixtures for Alpha Arena trading engine tests.
"""
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import MagicMock, AsyncMock
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field


# ============================================================================
# Data Classes for Test Objects
# ============================================================================

@dataclass
class MockPosition:
    """Represents a trading position."""
    symbol: str
    quantity: float
    entry_price: float
    current_price: float
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0

    def __post_init__(self):
        self.unrealized_pnl = (self.current_price - self.entry_price) * self.quantity


@dataclass
class MockOrder:
    """Represents a trading order."""
    order_id: str
    symbol: str
    side: str  # 'buy' or 'sell'
    quantity: float
    order_type: str  # 'market', 'limit', 'stop'
    price: Optional[float] = None
    status: str = 'pending'
    filled_quantity: float = 0.0
    filled_price: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class MockPortfolio:
    """Represents portfolio state."""
    cash: float
    positions: Dict[str, MockPosition] = field(default_factory=dict)
    total_value: float = 0.0

    def __post_init__(self):
        positions_value = sum(p.quantity * p.current_price for p in self.positions.values())
        self.total_value = self.cash + positions_value


# ============================================================================
# Market Data Fixtures
# ============================================================================

@pytest.fixture
def sample_ohlcv_data() -> pd.DataFrame:
    """Generate sample OHLCV data for testing."""
    np.random.seed(42)
    dates = pd.date_range(start='2024-01-01', periods=100, freq='D')

    # Generate realistic price movement
    initial_price = 100.0
    returns = np.random.normal(0.001, 0.02, 100)
    prices = initial_price * np.cumprod(1 + returns)

    df = pd.DataFrame({
        'timestamp': dates,
        'open': prices * (1 + np.random.uniform(-0.01, 0.01, 100)),
        'high': prices * (1 + np.random.uniform(0, 0.02, 100)),
        'low': prices * (1 - np.random.uniform(0, 0.02, 100)),
        'close': prices,
        'volume': np.random.uniform(1000000, 5000000, 100)
    })
    df.set_index('timestamp', inplace=True)
    return df


@pytest.fixture
def multi_asset_data() -> Dict[str, pd.DataFrame]:
    """Generate OHLCV data for multiple assets."""
    np.random.seed(42)
    dates = pd.date_range(start='2024-01-01', periods=100, freq='D')

    assets = {}
    for symbol, initial_price in [('AAPL', 150), ('GOOGL', 140), ('MSFT', 380), ('TSLA', 250)]:
        returns = np.random.normal(0.001, 0.025, 100)
        prices = initial_price * np.cumprod(1 + returns)

        assets[symbol] = pd.DataFrame({
            'timestamp': dates,
            'open': prices * (1 + np.random.uniform(-0.01, 0.01, 100)),
            'high': prices * (1 + np.random.uniform(0, 0.02, 100)),
            'low': prices * (1 - np.random.uniform(0, 0.02, 100)),
            'close': prices,
            'volume': np.random.uniform(1000000, 10000000, 100)
        }).set_index('timestamp')

    return assets


@pytest.fixture
def empty_ohlcv_data() -> pd.DataFrame:
    """Empty DataFrame with correct schema."""
    return pd.DataFrame(columns=['open', 'high', 'low', 'close', 'volume'])


@pytest.fixture
def invalid_ohlcv_data() -> pd.DataFrame:
    """DataFrame with invalid/corrupt data."""
    return pd.DataFrame({
        'open': [np.nan, -100, float('inf'), 100],
        'high': [100, np.nan, 100, -50],
        'low': [90, 90, np.nan, 200],  # low > high is invalid
        'close': [95, 95, 95, np.nan],
        'volume': [-1000, 1000, 1000, 1000]
    })


@pytest.fixture
def extreme_volatility_data() -> pd.DataFrame:
    """Data with extreme price movements for edge case testing."""
    np.random.seed(42)
    dates = pd.date_range(start='2024-01-01', periods=50, freq='D')

    # Create data with extreme moves
    prices = [100]
    for i in range(49):
        if i % 10 == 0:
            # Extreme move every 10 days
            change = np.random.choice([-0.5, 0.5])  # ±50% moves
        else:
            change = np.random.normal(0, 0.05)
        prices.append(prices[-1] * (1 + change))

    prices = np.array(prices)

    return pd.DataFrame({
        'timestamp': dates,
        'open': prices * 0.99,
        'high': prices * 1.02,
        'low': prices * 0.98,
        'close': prices,
        'volume': np.random.uniform(1000000, 5000000, 50)
    }).set_index('timestamp')


# ============================================================================
# Factor/Signal Fixtures
# ============================================================================

@pytest.fixture
def sample_factors() -> Dict[str, pd.Series]:
    """Generate sample factor values for testing."""
    np.random.seed(42)
    dates = pd.date_range(start='2024-01-01', periods=100, freq='D')

    return {
        'momentum': pd.Series(np.random.uniform(-1, 1, 100), index=dates),
        'value': pd.Series(np.random.uniform(-1, 1, 100), index=dates),
        'quality': pd.Series(np.random.uniform(-1, 1, 100), index=dates),
        'volatility': pd.Series(np.random.uniform(0, 1, 100), index=dates),
    }


@pytest.fixture
def conflicting_factors() -> Dict[str, pd.Series]:
    """Factors that give conflicting signals."""
    np.random.seed(42)
    dates = pd.date_range(start='2024-01-01', periods=100, freq='D')

    return {
        'momentum': pd.Series([0.8] * 100, index=dates),      # Strong buy
        'value': pd.Series([-0.9] * 100, index=dates),        # Strong sell
        'quality': pd.Series([0.5] * 100, index=dates),       # Moderate buy
        'sentiment': pd.Series([-0.3] * 100, index=dates),    # Weak sell
    }


@pytest.fixture
def extreme_factor_values() -> Dict[str, pd.Series]:
    """Edge case factor values."""
    dates = pd.date_range(start='2024-01-01', periods=10, freq='D')

    return {
        'zero_factor': pd.Series([0.0] * 10, index=dates),
        'max_factor': pd.Series([1.0] * 10, index=dates),
        'min_factor': pd.Series([-1.0] * 10, index=dates),
        'nan_factor': pd.Series([np.nan] * 10, index=dates),
        'inf_factor': pd.Series([float('inf')] * 10, index=dates),
    }


# ============================================================================
# Portfolio/Position Fixtures
# ============================================================================

@pytest.fixture
def sample_portfolio() -> MockPortfolio:
    """Sample portfolio with existing positions."""
    positions = {
        'AAPL': MockPosition('AAPL', 100, 150.0, 155.0),
        'GOOGL': MockPosition('GOOGL', 50, 140.0, 138.0),
    }
    return MockPortfolio(cash=50000.0, positions=positions)


@pytest.fixture
def empty_portfolio() -> MockPortfolio:
    """Empty portfolio with only cash."""
    return MockPortfolio(cash=100000.0, positions={})


@pytest.fixture
def margin_portfolio() -> MockPortfolio:
    """Portfolio near margin limits."""
    positions = {
        'AAPL': MockPosition('AAPL', 500, 150.0, 145.0),  # Losing position
        'MSFT': MockPosition('MSFT', 200, 380.0, 370.0),  # Losing position
    }
    return MockPortfolio(cash=5000.0, positions=positions)  # Low cash


# ============================================================================
# Risk Parameters Fixtures
# ============================================================================

@pytest.fixture
def default_risk_params() -> Dict[str, Any]:
    """Default risk management parameters."""
    return {
        'max_position_size': 0.10,      # 10% max per position
        'max_portfolio_risk': 0.02,     # 2% max portfolio risk
        'max_drawdown': 0.15,           # 15% max drawdown
        'volatility_target': 0.15,      # 15% annual volatility target
        'min_position_size': 100,       # Minimum $100 position
        'max_leverage': 1.0,            # No leverage
        'stop_loss_pct': 0.05,          # 5% stop loss
    }


@pytest.fixture
def aggressive_risk_params() -> Dict[str, Any]:
    """Aggressive risk parameters for testing limits."""
    return {
        'max_position_size': 0.25,
        'max_portfolio_risk': 0.05,
        'max_drawdown': 0.30,
        'volatility_target': 0.30,
        'min_position_size': 50,
        'max_leverage': 2.0,
        'stop_loss_pct': 0.10,
    }


@pytest.fixture
def conservative_risk_params() -> Dict[str, Any]:
    """Conservative risk parameters."""
    return {
        'max_position_size': 0.05,
        'max_portfolio_risk': 0.01,
        'max_drawdown': 0.05,
        'volatility_target': 0.08,
        'min_position_size': 500,
        'max_leverage': 0.5,
        'stop_loss_pct': 0.02,
    }


# ============================================================================
# Mock Broker Fixture
# ============================================================================

@pytest.fixture
def mock_broker():
    """Create a mock broker for testing trade execution."""
    broker = MagicMock()

    # Track orders
    broker.orders = []
    broker.order_counter = 0

    def submit_order(symbol, side, quantity, order_type='market', price=None):
        broker.order_counter += 1
        order = MockOrder(
            order_id=f"ORD-{broker.order_counter:06d}",
            symbol=symbol,
            side=side,
            quantity=quantity,
            order_type=order_type,
            price=price,
            status='filled' if order_type == 'market' else 'pending',
            filled_quantity=quantity if order_type == 'market' else 0,
            filled_price=price or 100.0  # Default fill price
        )
        broker.orders.append(order)
        return order

    def cancel_order(order_id):
        for order in broker.orders:
            if order.order_id == order_id and order.status == 'pending':
                order.status = 'cancelled'
                return True
        return False

    def get_position(symbol):
        return MockPosition(symbol, 0, 0, 0)

    def get_account_value():
        return 100000.0

    def get_buying_power():
        return 50000.0

    broker.submit_order = MagicMock(side_effect=submit_order)
    broker.cancel_order = MagicMock(side_effect=cancel_order)
    broker.get_position = MagicMock(side_effect=get_position)
    broker.get_account_value = MagicMock(side_effect=get_account_value)
    broker.get_buying_power = MagicMock(side_effect=get_buying_power)
    broker.is_market_open = MagicMock(return_value=True)

    return broker


@pytest.fixture
def failing_broker():
    """Broker that fails on operations for error handling tests."""
    broker = MagicMock()
    broker.submit_order = MagicMock(side_effect=ConnectionError("Broker connection lost"))
    broker.cancel_order = MagicMock(side_effect=TimeoutError("Request timed out"))
    broker.get_position = MagicMock(side_effect=ValueError("Invalid symbol"))
    broker.is_market_open = MagicMock(return_value=False)
    return broker


# ============================================================================
# Configuration Fixtures
# ============================================================================

@pytest.fixture
def strategy_config() -> Dict[str, Any]:
    """Default strategy configuration."""
    return {
        'name': 'TestStrategy',
        'universe': ['AAPL', 'GOOGL', 'MSFT', 'TSLA'],
        'rebalance_frequency': 'daily',
        'factor_weights': {
            'momentum': 0.3,
            'value': 0.3,
            'quality': 0.2,
            'volatility': 0.2,
        },
        'signal_threshold': 0.1,
        'lookback_period': 20,
    }
```

#### File: `alpha_arena/tests/mocks/mock_broker.py`

```python
"""
Mock broker implementation for testing trade execution.
"""
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import uuid


class OrderStatus(Enum):
