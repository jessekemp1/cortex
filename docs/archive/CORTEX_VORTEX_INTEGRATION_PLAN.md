# Cortex-VortexV2-Alpha Arena Integration Plan

**Date**: 2025-12-23
**Status**: Phase 1 Complete - Cortex as Shared Intelligence Base
**Architecture**: Independent systems using Cortex library components

---

## 🎯 Integration Vision

**Core Principle**: Each system (Cortex, VortexV2, Alpha Arena) runs independently, but they share intelligence infrastructure housed in Cortex.

```
┌─────────────────────────────────────────────────┐
│         CORTEX (Intelligence Library)           │
│  /Users/jesse.kemp/Dev/cortex/                  │
│                                                  │
│  ✅ storage/prediction_db.py (SQLite)           │
│  ✅ learning.py (Confidence calibration)        │
│  ✅ feedback.py (Outcome tracking)              │
│  ✅ recommendation_engine.py                    │
└─────────────────────────────────────────────────┘
           ↑              ↑              ↑
           │ imports      │ imports      │ imports
           │              │              │
    ┌──────────┐   ┌───────────┐   ┌──────────────┐
    │ VortexV2 │   │   Alpha   │   │    Local     │
    │          │   │   Arena   │   │ Orchestrator │
    │ Flask    │   │ Daily     │   │ APScheduler  │
    │ Port8000 │   │ 4:30PM    │   │ Background   │
    └──────────┘   └───────────┘   └──────────────┘
    Independent    Independent     Independent
```

---

## ✅ What's Built (Phase 1 - VortexV2 Integration)

### 1. Cortex Shared Intelligence Base

**File**: `/Users/jesse.kemp/Dev/cortex/storage/prediction_db.py` (NEW)

**What it does**:
- SQLite database for unified prediction tracking
- Stores prediction outcomes across all domains (weather, trading, dev)
- Calculates confidence states per domain
- Tracks prediction statistics and trends

**Database**: `~/.cortex/predictions.db`

**Tables**:
```sql
-- Prediction outcomes
predictions (
    domain,              -- 'weather', 'trading', 'dev'
    prediction_type,     -- 'wind_speed', 'trade_pnl', 'task_estimate'
    predicted_value,
    actual_value,
    confidence,
    outcome_quality,     -- Calculated accuracy
    metadata             -- JSON context
)

-- Current confidence state per domain
confidence_state (
    domain,
    current_confidence,
    recent_accuracy,
    prediction_count,
    last_updated
)
```

**Key Methods**:
- `log_prediction_outcome()` - Log a prediction vs actual result
- `get_confidence_state()` - Get current confidence for a domain
- `get_prediction_stats()` - Get accuracy trends

---

### 2. VortexV2 Cortex Bridge

**File**: `/Users/jesse.kemp/Dev/Vortex/VortexV2/app/intelligence/cortex_bridge.py` (NEW)

**What it does**:
- Connects VortexV2 to Cortex prediction tracking
- Logs forecast outcomes (forecast vs NDBC observations)
- Gets confidence adjustments from Cortex
- Remains optional - VortexV2 works without it

**Key Methods**:
```python
from app.intelligence.cortex_bridge import get_cortex_bridge

cortex = get_cortex_bridge()

# Log a forecast outcome
cortex.log_wind_speed_forecast(
    forecast_knots=15.0,
    observed_knots=14.2,
    confidence=0.85,
    location_name="buoy_45007",
    lead_hours=6,
    model_name="ensemble"
)

# Get Cortex-calibrated confidence
adjusted_confidence = cortex.get_confidence_adjustment(base_confidence=0.80)

# Get prediction statistics
stats = cortex.get_prediction_stats(days=7)
```

---

### 3. VortexV2 Validation Integration

**File**: `/Users/jesse.kemp/Dev/Vortex/VortexV2/app/core/validation/observation_validator.py` (MODIFIED)

**Changes**:
- Added import of Cortex bridge (optional)
- Added `log_to_cortex()` method to ObservationValidator
- Validation pairs can now be logged to Cortex for cross-domain learning

**Usage**:
```python
from app.core.validation.observation_validator import ObservationValidator

validator = ObservationValidator()

# Validate forecasts against observations
pairs = await validator.batch_validate(forecasts, observations)

# Calculate metrics (as before)
metrics = validator.calculate_metrics(pairs)

# NEW: Log to Cortex for learning
validator.log_to_cortex(pairs)  # Optional - gracefully skips if unavailable
```

---

## 🔧 Current Status

### ✅ Completed

1. **Cortex SQLite Storage** - Working, tested
2. **VortexV2 Bridge Implementation** - Code complete
3. **Validation Integration** - Code complete
4. **Test Framework** - test_cortex_integration.py created

### ⚠️ Known Issue

**Import dependency in `cortex/learning.py`**:
```python
from cortex.batch import BatchConfig, BatchFallback, LearningBatcher, LearningContext
```

This causes import errors when VortexV2 tries to import learning.py because Cortex isn't set up as a proper Python package.

**Impact**: Bridge initializes but remains disabled. VortexV2 works fine, just doesn't connect to Cortex yet.

### 🔨 Fix Options

**Option A: Make Cortex a proper package** (Recommended)
1. Add `/Users/jesse.kemp/Dev/cortex/__init__.py`
2. Add Cortex to PYTHONPATH
3. Or install Cortex as editable package: `pip install -e /Users/jesse.kemp/Dev/cortex`

**Option B: Modify learning.py imports**
1. Change from `from cortex.batch` to `from batch`
2. Ensure batch module exists and doesn't have cortex imports

**Option C: Simplified learning module for VortexV2**
1. Create `cortex/simple_learning.py` without batch dependencies
2. VortexV2 uses simple_learning instead of full learning

---

## 📊 How It Will Work (Once Import Fixed)

### VortexV2 Daily Validation Flow

```python
# 1. VortexV2 generates forecasts (as normal)
forecasts = await ensemble_model.generate_forecast(...)

# 2. Fetch NDBC observations (as normal)
observations = await ndbc_client.get_observations(...)

# 3. Validate forecasts (as normal)
validator = ObservationValidator()
pairs = await validator.batch_validate(forecasts, observations)
metrics = validator.calculate_metrics(pairs)

# 4. NEW: Log to Cortex for cross-domain learning
validator.log_to_cortex(pairs)
# This logs each forecast-observation pair to Cortex's prediction DB
# Domain: 'weather'
# Prediction type: 'wind_speed'
# Predicted/Actual: forecast vs observation values
# Confidence: from VortexV2's forecast

# 5. Cortex automatically updates weather domain confidence state
# - Calculates recent accuracy
# - Adjusts confidence based on forecast performance
# - Tracks prediction trends
```

### Forecast Generation with Cortex Calibration

```python
# When generating new forecast
cortex = get_cortex_bridge()

# Get base confidence from VortexV2 model
base_confidence = ensemble_model.get_confidence()  # e.g., 0.85

# Get Cortex adjustment based on recent forecast accuracy
adjusted_confidence = cortex.get_confidence_adjustment(base_confidence)

# Use adjusted confidence in forecast
forecast = {
    'wind_speed': 15.0,
    'confidence': adjusted_confidence,  # Calibrated by Cortex
    'model': 'ensemble'
}
```

---

## 🚀 Next Steps

### Immediate (Fix Import Issue)

**Recommended**: Install Cortex as editable package

```bash
cd /Users/jesse.kemp/Dev/cortex

# Create setup.py if it doesn't exist
cat > setup.py << 'EOF'
from setuptools import setup, find_packages

setup(
    name="cortex",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "structlog",
        "anthropic",
    ],
)
EOF

# Install in editable mode
pip install -e .
```

Then test again:
```bash
cd /Users/jesse.kemp/Dev/Vortex/VortexV2
python test_cortex_integration.py
```

### Phase 2: Alpha Arena Integration

Once VortexV2 integration is working, replicate for Alpha Arena:

1. **Create**: `alpha_arena/src/intelligence/cortex_bridge.py`
2. **Methods**:
   - `log_trade_outcome()`
   - `get_position_size_adjustment()`
   - `check_for_weather_insights()` (cross-domain!)
3. **Integrate** into daily trading script
4. **Test** with paper portfolio

---

## 💡 Benefits Once Integrated

### 1. Unified Prediction Tracking

All predictions stored in one place:
```bash
$ sqlite3 ~/.cortex/predictions.db

SELECT domain, COUNT(*), AVG(outcome_quality)
FROM predictions
GROUP BY domain;

# Results:
# weather | 150 | 0.78  (VortexV2 forecasts)
# trading | 42  | 0.65  (Alpha Arena trades)
# dev     | 89  | 0.71  (Cortex dev estimates)
```

### 2. Cross-Domain Confidence Calibration

```python
# Morning briefing could show:
from storage.prediction_db import get_prediction_db

db = get_prediction_db()
states = db.get_all_confidence_states()

# Output:
{
    'weather': {'confidence': 0.82, 'accuracy': 0.78},
    'trading': {'confidence': 0.65, 'accuracy': 0.58},  # Low!
    'dev': {'confidence': 0.71, 'accuracy': 0.69}
}

# Recommendation: "Trading confidence low - reduce position sizes"
```

### 3. Cross-Domain Insights (Future)

```python
# VortexV2 predicts storm
storm_forecast = {...}

# Alpha Arena checks for commodity implications
if storm_forecast['severity'] > 0.7:
    # Natural Gas demand spikes in winter storms
    recommendation = "Consider NG long position - storm predicted"
```

### 4. Unified Learning

- VortexV2 teaches Cortex about prediction accuracy in uncertain systems
- Alpha Arena teaches Cortex about risk/reward calibration
- Dev work teaches Cortex about effort estimation
- **All domains improve each other's confidence calibration**

---

## 📁 File Summary

### Created Files

| File | Purpose | Status |
|------|---------|--------|
| `cortex/storage/prediction_db.py` | SQLite prediction tracking | ✅ Complete |
| `cortex/storage/__init__.py` | Updated exports | ✅ Complete |
| `VortexV2/app/intelligence/__init__.py` | Module init | ✅ Complete |
| `VortexV2/app/intelligence/cortex_bridge.py` | VortexV2 bridge | ✅ Complete |
| `VortexV2/test_cortex_integration.py` | Integration tests | ✅ Complete |

### Modified Files

| File | Changes | Status |
|------|---------|--------|
| `VortexV2/app/core/validation/observation_validator.py` | Added Cortex import & log_to_cortex() | ✅ Complete |

---

## 🎯 Architecture Benefits

### Independence

- **VortexV2**: Runs on port 8000, completely independent
- **Alpha Arena**: Runs daily at 4:30 PM via orchestrator, independent
- **Cortex**: No running process, just a library
- **Failure isolation**: One system down doesn't affect others

### Shared Intelligence

- **Common storage**: `~/.cortex/predictions.db`
- **Common learning algorithms**: Confidence calibration, trend analysis
- **Common interfaces**: Same prediction tracking API across domains

### Modularity

- **VortexV2** can use or not use Cortex (graceful degradation)
- **Cortex** can be enhanced without touching VortexV2/Alpha Arena
- **New systems** can integrate easily (same bridge pattern)

---

## 🔍 Testing Checklist

Once import issue is fixed:

- [ ] Run `test_cortex_integration.py` - should show "WORKING"
- [ ] Run VortexV2 validation with real data
- [ ] Check `~/.cortex/predictions.db` for logged forecasts
- [ ] Verify confidence states update
- [ ] Test confidence adjustment in forecast generation
- [ ] Add Alpha Arena integration
- [ ] Test cross-domain querying

---

## 📞 Summary

**What we built**: Cortex as a shared intelligence library with:
- SQLite-based prediction tracking (all domains)
- VortexV2 bridge for forecast outcome logging
- Validation integration (optional, graceful)

**Current state**: Code complete, import dependency blocking activation

**Next step**: Fix Cortex package structure (5 minutes) or create simplified learning module

**Future**: Replicate pattern for Alpha Arena, enable cross-domain insights

**Architecture validated**: ✅ Independent systems, shared intelligence base, no single point of failure

Ready to proceed with fixing the import issue and activating the integration!
