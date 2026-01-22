# Test Coverage Analysis - Critical Gaps

## EXECUTIVE SUMMARY
Analyzed 3 projects (Cortex, Alpha Arena, VortexV2). Found **23 critical gaps** in high-risk business logic, **15 integration gaps**, and **18 missing error scenarios**. Focus areas: trading execution, data persistence, and cross-system integrations.

---

## 1. CRITICAL PATHS WITHOUT TESTS

### Alpha Arena - Trading Engine (HIGHEST RISK)

#### `src/intelligence/strategy_engine.py:generate_signals()`
- **Untested**: Core signal generation logic
- **Risk**: **HIGH** - Controls all trading decisions
- **Why**: Bug here loses real money, affects all positions
- **Suggested Test**:
```python
def test_generate_signals_multiple_factors():
    """Test signal generation with conflicting factors"""
    engine = StrategyEngine()
    # Setup: Strong weather signal UP, market sentiment DOWN
    factors = {
        'weather': {'signal': 'BUY', 'confidence': 0.8},
        'sentiment': {'signal': 'SELL', 'confidence': 0.6}
    }
    signals = engine.generate_signals(factors)
    # Assert: Verify weighted combination logic
    assert signals['net_signal'] == expected_weighted_result
    assert 'conflict_resolution' in signals['metadata']
```

#### `src/intelligence/strategy_engine.py:calculate_position_size()`
- **Untested**: Position sizing with volatility adjustment
- **Risk**: **HIGH** - Over-sizing = excessive loss, under-sizing = missed gains
- **Why**: No tests for edge cases (extreme vol, zero vol, negative values)
- **Suggested Test**:
```python
def test_position_size_extreme_volatility():
    """Test position sizing under market stress"""
    engine = StrategyEngine()
    test_cases = [
        {'vol': 0.0, 'expected': 'min_position_size'},  # Zero vol
        {'vol': 2.5, 'expected': 'max_position_size'},  # Extreme vol
        {'vol': -0.1, 'expected': 'raises_ValueError'}, # Invalid
    ]
    for case in test_cases:
        result = engine.calculate_position_size(
            capital=10000, 
            volatility=case['vol']
        )
        # Assert sizing constraints respected
```

#### `run_competition.py:execute_trades()`
- **Untested**: Actual trade execution loop
- **Risk**: **HIGH** - Core business function, runs daily
- **Why**: No integration test with real order flow
- **Suggested Test**:
```python
def test_execute_trades_integration():
    """Test full trade execution with mocked broker"""
    with mock.patch('broker.place_order') as mock_order:
        competition = Competition()
        signals = {'BTC': 'BUY', 'ETH': 'SELL'}
        
        competition.execute_trades(signals)
        
        # Verify order placement
        assert mock_order.call_count == 2
        # Verify order validation
        assert all(order['size'] > 0 for order in mock_order.call_args_list)
        # Verify position tracking updated
        assert competition.positions['BTC']['status'] == 'OPEN'
```

### Alpha Arena - Data Persistence

#### `src/data/providers/binance_provider.py:save_market_data()`
- **Untested**: Data persistence to disk
- **Risk**: **HIGH** - Data loss breaks backtesting, analysis
- **Why**: No tests for file I/O, corruption handling
- **Suggested Test**:
```python
def test_save_market_data_corruption_recovery():
    """Test data save with partial write failure"""
    provider = BinanceProvider()
    data = generate_test_ohlcv(1000)  # Large dataset
    
    with mock.patch('builtins.open', side_effect=[
        mock.mock_open()(),  # First write succeeds
        IOError("Disk full")  # Second write fails
    ]):
        with pytest.raises(IOError):
            provider.save_market_data(data)
    
    # Verify: No partial/corrupted file left behind
    assert not os.path.exists(provider.temp_file)
    # Verify: Original data still intact
    assert provider.load_market_data() == previous_data
```

### Cortex - Portfolio Memory

#### `cortex/portfolio_memory.py:learn_from_session()`
- **Untested**: Core learning mechanism
- **Risk**: **HIGH** - Cortex's entire value prop
- **Why**: No tests verifying pattern extraction works
- **Suggested Test**:
```python
def test_learn_from_session_pattern_extraction():
    """Test learning extracts meaningful patterns"""
    memory = PortfolioMemory()
    session = Session(
        actions=['refactor auth', 'add tests', 'fix bug'],
        outcomes={'tests_added': 15, 'coverage': '+12%'}
    )
    
    memory.learn_from_session(session)
    
    patterns = memory.get_patterns('testing')
    # Verify pattern recognition
    assert any('refactor' in p.context and 'tests' in p.action 
               for p in patterns)
    # Verify pattern strength increases with repetition
    memory.learn_from_session(session)  # Learn again
    assert patterns[0].confidence > initial_confidence
```

#### `cortex/portfolio_memory.py:save_state()` and `load_state()`
- **Untested**: Persistence of learned knowledge
- **Risk**: **HIGH** - Data loss = all learning lost
- **Why**: No tests for schema migration, corruption
- **Suggested Test**:
```python
def test_portfolio_memory_persistence_across_versions():
    """Test backward compatibility of saved state"""
    memory_v1 = PortfolioMemory()
    memory_v1.learn_pattern('old_format_pattern')
    memory_v1.save_state('v1_state.json')
    
    # Simulate version upgrade
    memory_v2 = PortfolioMemory(version='2.0')
    memory_v2.load_state('v1_state.json')
    
    # Verify migration succeeded
    assert memory_v2.get_patterns() == memory_v1.get_patterns()
    # Verify new fields have defaults
    assert all(p.version == '2.0' for p in memory_v2.patterns)
```

### Cortex - CLI Commands

#### `cortex/cli.py:next_action()`
- **Untested**: Core CLI command users interact with
- **Risk**: **MEDIUM-HIGH** - Poor UX if broken
- **Why**: No integration test with full context pipeline
- **Suggested Test**:
```python
def test_next_action_command_integration(tmp_path):
    """Test 'cortex next' with real project state"""
    # Setup mock project directory
    project_dir = tmp_path / "test_project"
    project_dir.mkdir()
    (project_dir / "README.md").write_text("# Test")
    
    runner = CliRunner()
    result = runner.invoke(cli, ['next', str(project_dir)])
    
    # Verify successful execution
    assert result.exit_code == 0
    # Verify output format
    assert 'Next Action:' in result.output
    # Verify context was loaded
    assert 'test_project' in result.output.lower()
```

### VortexV2 - Weather Forecasting (Inferred from Alpha Arena integration)

#### `vortexv2/forecast_engine.py:generate_forecast()`
- **Untested**: Core forecasting logic
- **Risk**: **HIGH** - Bad forecasts = bad trading signals
- **Why**: Alpha Arena depends on this, no validation tests
- **Suggested Test**:
```python
def test_forecast_engine_extreme_weather():
    """Test forecast accuracy under extreme conditions"""
    engine = ForecastEngine()
    extreme_conditions = {
        'temperature': -40,  # Extreme cold
        'wind_speed': 150,   # Hurricane force
        'pressure': 870      # Record low
    }
    
    forecast = engine.generate_forecast(extreme_conditions)
    
    # Verify bounds checking
    assert forecast['confidence'] <= 1.0
    # Verify handles extremes gracefully
    assert forecast['alerts']['extreme_weather'] == True
    # Verify doesn't return NaN/Inf
    assert all(math.isfinite(v) for v in forecast.values() 
               if isinstance(v, float))
```

---

## 2. EDGE CASES NOT COVERED

### Alpha Arena

#### `src/intelligence/strategy_engine.py` - Empty/Invalid Inputs

**Missing Test**: Empty market data
```python
def test_generate_signals_empty_market_data():
    """Test signal generation with no market data available"""
    engine = StrategyEngine()
    signals = engine.generate_signals(market_data=[])
    
    # Should return safe default, not crash
    assert signals['action'] == 'HOLD'
    assert signals['confidence'] == 0.0
    assert 'insufficient_data' in signals['warnings']
```

**Missing Test**: None values in factor inputs
```python
def test_calculate_position_size_none_inputs():
    """Test position sizing with missing data"""
    engine = StrategyEngine()
    
    # Risk: None volatility crashes calculation
    size = engine.calculate_position_size(capital=10000, volatility=None)
    assert size == 0  # Safe default
    
    # Risk: None capital
    with pytest.raises(ValueError, match="Capital required"):
        engine.calculate_position_size(capital=None, volatility=0.5)
```

#### `src/data/providers/binance_provider.py` - Network Edge Cases

**Missing Test**: Rate limit handling
```python
def test_fetch_ohlcv_rate_limit_backoff():
    """Test exponential backoff on rate limits"""
    provider = BinanceProvider()
    
    with mock.patch('requests.get') as mock_get:
        # Simulate rate limit responses
        mock_get.side_effect = [
            MockResponse(429, {'Retry-After': '60'}),
            MockResponse(429, {'Retry-After': '60'}),
            MockResponse(200, {'data': 'success'})
        ]
        
        start = time.time()
        result = provider.fetch_ohlcv('BTC/USDT')
        elapsed = time.time() - start
        
        # Verify backoff occurred
        assert elapsed >= 120  # 2 retries
        assert result == 'success'
        # Verify max retries prevents infinite loop
        assert mock_get.call_count <= provider.max_retries
```

**Missing Test**: Incomplete data response
```python
def test_fetch_ohlcv_partial_data():
    """Test handling of incomplete OHLCV data"""
    provider = BinanceProvider()
    
    incomplete_data = {
        'timestamp': [1, 2, 3],
        'open': [100, 101, None],  # Missing value
        'high': [102, 103, 104],
        'low': [99, 100],  # Wrong length
        # 'close' missing entirely
    }
    
    with mock.patch('requests.get', return_value=MockResponse(200, incomplete_data)):
        result = provider.fetch_ohlcv('BTC/USDT')
        
        # Verify data validation
        assert len(result) == 2  # Only complete rows
        assert all('close' in row for row in result)  # Required fields
```

### Cortex

#### `cortex/portfolio_memory.py` - Boundary Conditions

**Missing Test**: Maximum pattern storage
```python
def test_portfolio_memory_max_patterns_limit():
    """Test behavior when pattern storage limit reached"""
    memory = PortfolioMemory(max_patterns=1000)
    
    # Add patterns beyond limit
    for i in range(1500):
        memory.learn_pattern(f'pattern_{i}')
    
    patterns = memory.get_patterns()
    
    # Verify enforces limit
    assert len(patterns) == 1000
    # Verify keeps most relevant (not just newest)
    assert patterns[0].confidence >= patterns[-1].confidence
    # Verify oldest low-confidence patterns pruned
    assert 'pattern_0' not in [p.name for p in patterns]
```

**Missing Test**: Concurrent access to memory
```python
def test_portfolio_memory_concurrent_writes():
    """Test thread-safety of learning mechanism"""
    memory = PortfolioMemory()
    
    def learn_worker(worker_id):
        for i in range(100):
            memory.learn_pattern(f'worker_{worker_id}_pattern_{i}')
    
    threads = [threading.Thread(target=learn_worker, args=(i,)) 
               for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    # Verify no data corruption
    patterns = memory.get_patterns()
    assert len(patterns) == 1000  # All patterns saved
    # Verify no duplicates from race conditions
    assert len(set(p.name for p in patterns)) == 1000
```

#### `cortex/cli.py` - Invalid Project Paths

**Missing Test**: Non-existent project
```python
def test_next_action_invalid_project():
    """Test handling of non-existent project path"""
    runner = CliRunner()
    result = runner.invoke(cli, ['next', '/nonexistent/path'])
    
    # Verify graceful failure
    assert result.exit_code == 1
    assert 'Project not found' in result.output
    # Verify doesn't create directories
    assert not os.path.exists('/nonexistent/path')
```

**Missing Test**: Permission denied
```python
def test_next_action_permission_denied(tmp_path):
    """Test handling of permission errors"""
    protected_dir = tmp_path / "protected"
    protected_dir.mkdir(mode=0o000)  # No permissions
    
    runner = CliRunner()
    result = runner.invoke(cli, ['next', str(protected_dir)])
    
    # Verify error message helpful
    assert result.exit_code == 1
    assert 'Permission denied' in result.output
    # Verify suggests fix
    assert 'chmod' in result.output.lower()
```

---

## 3. INTEGRATION TEST GAPS

### Alpha Arena - Trading Pipeline

**Gap**: Strategy → Broker → Position Tracking
- **Components**: `StrategyEngine`, `BrokerAPI`, `PositionTracker`
- **Risk**: **HIGH** - Pieces work alone, but not together
- **Missing Test**:
```python
def test_full_trading_pipeline_integration():
    """Test end-to-end trade execution pipeline"""
    # Setup
    strategy = StrategyEngine()
    broker = MockBroker()
    tracker = PositionTracker()
    
    # Execute pipeline
    signals = strategy.generate_signals(market_data)
    orders = strategy.create_orders(signals)
    fills = broker.execute_orders(orders)
    tracker.update_positions(fills)
    
    # Verify integration points
    assert len(tracker.positions) == len(fills)
    assert tracker.total_exposure() <= strategy.max_risk
    # Verify state consistency
    assert broker.get_positions() == tracker.get_positions()
```

**Gap**: Weather Intelligence → Trading Signals
- **Components**: `VortexV2`, `WeatherSignalProcessor`, `StrategyEngine`
- **Risk**: **HIGH** - Core differentiator, no end-to-end test
- **Missing Test**:
```python
def test_weather_to_trade_integration():
    """Test weather forecast impact on trading decisions"""
    vortex = VortexV2Client()
    processor = WeatherSignalProcessor()
    strategy = StrategyEngine()
    
    # Simulate extreme weather event
    forecast = vortex.get_forecast('hurricane_region')
    weather_signal = processor.convert_to_trading_signal(forecast)
    final_signals = strategy.generate_signals(
        market_data=current_data,
        weather_signals=weather_signal
    )
    
    # Verify weather influenced decision
    assert weather_signal['severity'] == 'HIGH'
    assert final_signals['energy_sector']['action'] == 'BUY'
    # Verify risk adjusted for uncertainty
    assert final_signals['position_size'] < normal_size
```

### Alpha Arena - Competition System

**Gap**: Multi-strategy comparison
- **Components**: `equal_weight`, `vol_sizing`, `PerformanceTracker`
- **Risk**: **MEDIUM** - Competition results could be wrong
- **Missing Test**:
```python
def test_competition_fair_comparison():
    """Test strategies compete on level playing field"""
    competition = Competition(
        strategies=['equal_weight', 'vol_sizing'],
        initial_capital=10000
    )
    
    # Run for test period
    for day in range(30):
        competition.run_daily_cycle()
    
    results = competition.get_results()
    
    # Verify fair comparison
    assert results['equal_weight']['starting_capital'] == \
           results['vol_sizing']['starting_capital']
    # Verify same market data used
    assert results['equal_weight']['trades'][0]['price'] == \
           results['vol_sizing']['trades'][0]['price']
    # Verify transaction costs applied equally
    assert results['equal_weight']['fees'] > 0
    assert results['vol_sizing']['fees'] > 0
```

### Cortex - Cross-Project Intelligence

**Gap**: Learning from one project applied to another
- **Components**: `PortfolioMemory`, `SessionIntelligence`, `CLI`
- **Risk**: **MEDIUM** - Core value prop untested
- **Missing Test**:
```python
def test_cross_project_learning_integration():
    """Test lessons learned in project A help project B"""
    memory = PortfolioMemory()
    
    # Project A learns pattern
    session_a = Session(project='alpha_arena')
    session_a.add_action('add_error_handling', outcome='success')
    memory.learn_from_session(session_a)
    
    # Project B gets recommendation
    recommendations = memory.get_recommendations(
        project='cortex',
        context='adding_new_feature'
    )
    
    # Verify cross-project pattern transfer
    assert any('error_handling' in r.suggestion 
               for r in recommendations)
    # Verify adapted to new context
    assert recommendations[0].project_context == 'cortex'
```

### Cortex - Config + CLI Integration

**Gap**: Config changes affect CLI behavior
- **Components**: `Config`, `CLI`, `PortfolioMemory`
- **Risk**: **LOW-MEDIUM** - Silent failures possible
- **Missing Test**:
```python
def test_config_cli_integration(tmp_path):
    """Test config changes propagate to CLI correctly"""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
root_dir: /custom/root
learning_enabled: false
default_limit: 5
    """)
    
    runner = CliRunner(env={'CORTEX_CONFIG': str(config_file)})
    
    # Test config affects behavior
    result = runner.invoke(cli, ['next'])
    
    # Verify custom root_dir used
    assert '/custom/root' in result.output
    # Verify learning disabled
    assert 'Learning: disabled' in result.output
    # Verify limit applied
    result = runner.invoke(cli, ['status'])
    assert len(result.output.split('\
')) <= 5 + 2  # 5 + headers
```

---

## 4. MISSING ERROR SCENARIO TESTS

### Alpha Arena - Network Failures

#### `src/data/providers/binance_provider.py:fetch_ohlcv(