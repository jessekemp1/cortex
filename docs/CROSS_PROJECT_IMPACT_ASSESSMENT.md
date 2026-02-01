# Cross-Project Impact Assessment
## AI Engineering Improvements Applied to VortexV2 and Alpha Arena

**Created:** 2026-02-01
**Version:** 1.0
**Based On:** `/Users/jesse.kemp/Dev/cortex/docs/AI_ENGINEERING_IMPROVEMENTS_PRD.md`

---

## Executive Summary

This assessment evaluates how the 8 AI Engineering improvements planned for Cortex should be applied to VortexV2 (weather forecasting) and Alpha Arena (trading). Key findings:

- **VortexV2**: Limited direct LLM usage but HIGH opportunity for data quality, evaluation, and defensive patterns
- **Alpha Arena**: Active LLM prompting requiring prompt versioning, evaluation, and feedback collection
- **Both**: Strong integration opportunities through enhanced Cortex bridge

---

## VortexV2 Impact Analysis

### Current State

**Architecture Overview:**
- **Weather forecasting API** with ensemble models (ECMWF, GFS, HRRR, LSTM, bias correction)
- **Cortex Integration:** `/Users/jesse.kemp/Dev/Vortex/VortexV2/app/intelligence/cortex_bridge.py`
  - Logs forecast outcomes (wind speed, wave height) to Cortex
  - Retrieves confidence calibration from Cortex
  - Tracks prediction statistics across weather domain
- **Data Pipeline:** GRIB files → preprocessing → model ensemble → API responses
- **Validation System:** Confidence calibration, horizon analysis, quantile validation
- **Explainability:** SailorInterpreter translates technical metrics to actionable language

**Current AI/LLM Usage:**
- **MINIMAL direct LLM usage** - No Claude/Anthropic calls found in core forecasting
- **Human-facing explanations** via SailorInterpreter (rule-based, not LLM)
- **Cortex bridge** for cross-domain learning (prediction tracking only)

**Data Characteristics:**
- GRIB weather data (ECMWF, GFS, HRRR)
- NDBC observation data (ground truth)
- Forecast-observation pairs for validation
- High data quality requirements (physical constraints)

### Applicable Improvements

| Improvement | Applicability | Integration Point | Priority | Rationale |
|-------------|---------------|-------------------|----------|-----------|
| **1. Hybrid Retrieval** | N/A | None | N/A | No pattern retrieval needs - weather is physics-based |
| **2. AI-as-a-Judge** | Medium | Validation pipeline | P2 | Could evaluate forecast explanations for clarity |
| **3. Implicit Feedback** | High | API responses, UI interactions | P1 | Track which forecasts users trust/follow |
| **4. Prompt Versioning** | Low | SailorInterpreter (if LLM-ified) | P2 | Only if explanations move to LLM |
| **5. Three-Tier Memory** | N/A | None | N/A | Forecast data has clear time hierarchy already |
| **6. Lost-in-Middle** | N/A | None | N/A | No long context prompts |
| **7. Data Quality** | **HIGH** | GRIB validation, NDBC ingestion | **P0** | Critical for forecast accuracy |
| **8. Defensive Prompting** | Medium | API error responses | P2 | If adding LLM-generated explanations |

### Recommended Actions

#### Priority 0: Data Quality Framework (Immediate)

**Why:** VortexV2's accuracy depends on clean GRIB and NDBC data. Current validation is ad-hoc.

**Implementation:**
```python
# New file: /Users/jesse.kemp/Dev/Vortex/VortexV2/app/core/validation/data_quality.py

from cortex.intelligence.quality.data_quality import QualityDimensions, DataQualityTracker

class WeatherDataQualityTracker(DataQualityTracker):
    """Weather-specific data quality tracking"""

    def assess_grib_file(self, grib_data: GRIBData) -> QualityDimensions:
        return QualityDimensions(
            completeness=self._check_grib_completeness(grib_data),  # All variables present
            consistency=self._check_physical_constraints(grib_data),  # Wind speed < 200 knots
            accuracy=self._compare_with_ndbc(grib_data),  # vs. observations
            timeliness=self._check_forecast_freshness(grib_data),  # < 6 hours old
            uniqueness=self._check_duplicate_forecasts(grib_data),  # No duplicate runs
            validity=self._check_grib_format(grib_data),  # Valid GRIB2
        )

    def assess_ndbc_observation(self, obs: NDCBObservation) -> QualityDimensions:
        """Quality check for NDBC buoy observations"""
        ...
```

**Integration Points:**
- `/Users/jesse.kemp/Dev/Vortex/VortexV2/app/core/weather/grib_loader.py` - Add quality checks
- `/Users/jesse.kemp/Dev/Vortex/VortexV2/app/core/validation/pipeline.py` - Quality gates before validation
- Cortex bridge - Report data quality to Cortex for cross-domain trends

**Success Metrics:**
- 100% of GRIB files scored on 6 dimensions
- Quality score > 0.7 for all production forecasts
- Reject < 5% of GRIB files due to quality issues

---

#### Priority 1: Implicit Feedback Collection

**Why:** VortexV2 has no way to know which forecasts sailors trust. Dashboard interactions reveal confidence.

**Current Gap:** VortexV2 serves forecasts via API + Streamlit UI but doesn't track:
- Which forecasts get viewed/clicked
- Which routes get committed to
- When users request alternative scenarios (hedge signal)
- Time-to-action (fast commit = high trust)

**Implementation:**
```python
# New file: /Users/jesse.kemp/Dev/Vortex/VortexV2/app/intelligence/implicit_feedback.py

from cortex.intelligence.feedback.implicit_collector import ImplicitFeedbackCollector

class VortexImplicitCollector(ImplicitFeedbackCollector):
    """Track sailor interactions with forecasts"""

    def track_forecast_displayed(self, forecast_id: str, forecast: Dict):
        """Track when a forecast is shown to user"""
        self.pending_recommendations[forecast_id] = {
            "forecast": forecast,
            "shown_at": datetime.now(),
            "location": forecast.get("location"),
            "lead_hours": forecast.get("lead_hours"),
            "confidence": forecast.get("confidence"),
        }

    def track_route_committed(self, route_id: str, forecast_id: str):
        """User committed to a route = high confidence in forecast"""
        if forecast_id in self.pending_recommendations:
            self._log_follow(forecast_id, similarity=1.0, action="route_commit")

    def track_hedge_requested(self, forecast_id: str, alternative: str):
        """User requested Plan B = low confidence in forecast"""
        if forecast_id in self.pending_recommendations:
            self._log_override(forecast_id, action="hedge", alternative=alternative)
```

**Integration Points:**
- `/Users/jesse.kemp/Dev/Vortex/VortexV2/ui/app.py` - Track UI interactions
- `/Users/jesse.kemp/Dev/Vortex/VortexV2/app/api/v2/navigation.py` - Track route commits
- Cortex bridge - Feed signals to Cortex for calibration

**Success Metrics:**
- 50+ implicit signals per day (vs. 0 explicit feedback)
- Follow detection accuracy > 80%
- Correlation between confidence and follow rate > 0.6

---

#### Priority 2: AI-as-a-Judge for Explanations

**Why:** SailorInterpreter generates explanations. LLM-as-judge can validate clarity before serving.

**Current State:** SailorInterpreter uses rules to translate:
```python
# /Users/jesse.kemp/Dev/Vortex/VortexV2/app/core/explanation/interpreter.py
confidence=0.82 → "High confidence - Commit to plan"
```

**Future with LLM Explanations:**
If VortexV2 adds LLM-generated explanations (richer context), AI-as-a-judge validates:
- Is it clear to sailors?
- Is it actionable?
- Does it accurately reflect the confidence score?

**Implementation (when needed):**
```python
from cortex.intelligence.evaluation.quality_judge import QualityJudge

judge = QualityJudge()
explanation = "Wind will be 18-22 knots from 220°. High confidence - commit to plan."
score = await judge.evaluate_recommendation(
    rec={"explanation": explanation, "confidence": 0.82},
    context={"domain": "weather", "audience": "sailors"}
)
# Criteria: clarity, actionability, accuracy, technical_correctness
```

---

## Alpha Arena Impact Analysis

### Current State

**Architecture Overview:**
- **Trading competition platform** with multiple AI models (Claude, Grok, Ollama)
- **Cortex Integration:** `/Users/jesse.kemp/Dev/alpha_arena/src/intelligence/cortex_bridge.py`
  - Records trade outcomes to Cortex memory
  - Queries similar historical setups
  - Learns anti-patterns from failures
  - Stores success patterns
- **Intelligence Stack:**
  - Forecasting: ARIMA, LSTM, Prophet, ensemble
  - Nowcasting: Regime detection, anomaly detection, liquidity analysis
  - Macro: Economic analysis, policy analysis, geopolitical
  - Patterns: Pattern detection, fractal analysis, seasonality
  - Risk: Portfolio optimization, risk management
- **LLM Usage:** ACTIVE - Claude and Grok models generate trade signals via prompts

**Current AI/LLM Usage:**
- **Heavy LLM usage** - `/Users/jesse.kemp/Dev/alpha_arena/src/models/api_model.py`
- **AnthropicModel** and **XAIModel** generate trade signals
- **Prompts:** Inline strings in `_format_prompt()` method
- **No prompt versioning** - prompts scattered in code
- **No evaluation** - signals parsed but quality not measured
- **Explicit feedback only** - trade outcomes logged after close

**Data Characteristics:**
- Market data (OHLCV) from exchanges
- Economic indicators (FRED)
- Trade outcomes (PnL, duration, reasoning)
- Pattern matches from Cortex memory

### Applicable Improvements

| Improvement | Applicability | Integration Point | Priority | Rationale |
|-------------|---------------|-------------------|----------|-----------|
| **1. Hybrid Retrieval** | **HIGH** | Cortex bridge pattern queries | **P0** | Semantic + keyword matching for trade setups |
| **2. AI-as-a-Judge** | **HIGH** | Trade signal quality evaluation | **P0** | Validate signal quality before execution |
| **3. Implicit Feedback** | **HIGH** | Model health tracking, execution outcomes | **P1** | Track which signals get followed/ignored |
| **4. Prompt Versioning** | **HIGH** | `api_model.py`, `ollama_model.py` | **P0** | A/B test different prompting strategies |
| **5. Three-Tier Memory** | Medium | Historical trades | P2 | Recent trades more relevant than old |
| **6. Lost-in-Middle** | Medium | Market context prompts | P2 | If prompts include long market history |
| **7. Data Quality** | **HIGH** | Market data validation | **P1** | Bad data = bad trades |
| **8. Defensive Prompting** | **HIGH** | LLM signal generation | **P0** | Prevent hallucinated/out-of-scope signals |

### Recommended Actions

#### Priority 0: Prompt Versioning System

**Why:** Alpha Arena has inline prompts in `api_model.py` with no versioning or A/B testing capability.

**Current State:**
```python
# /Users/jesse.kemp/Dev/alpha_arena/src/models/api_model.py
def _format_prompt(self, market_data: Dict, portfolio: Portfolio) -> str:
    # Inline prompt string - no versioning
    prompt = f"""
    Analyze this market data and provide a trading signal...
    Price: {market_data['price']}
    ...
    """
    return prompt
```

**Implementation:**
```
alpha_arena/src/prompts/
  __init__.py
  base.py              # PromptTemplate from Cortex
  registry.py          # Prompt registry
  versions/
    v1/
      trade_signal.yaml       # Current prompt
      risk_assessment.yaml
    v2/
      trade_signal.yaml       # A/B test variant (more conservative)
```

**Example Template:**
```yaml
# alpha_arena/src/prompts/versions/v1/trade_signal.yaml
name: trade_signal_generation
version: "1.0.0"
description: "Generate BUY/SELL/HOLD signal from market data"
template: |
  You are an expert crypto trader analyzing {symbol}.

  Current Market State:
  - Price: {price}
  - 24h Change: {change_pct}%
  - Volume: {volume}
  - Regime: {regime}

  Portfolio State:
  - Cash: {cash}
  - Holdings: {holdings}

  Generate a trading signal in this format:
  ACTION: [BUY/SELL/HOLD]
  SYMBOL: {symbol}
  SIZE: [percentage of portfolio]
  REASONING: [your analysis in 1-2 sentences]

  Be conservative. Only trade when you have high confidence.

variables:
  - symbol
  - price
  - change_pct
  - volume
  - regime
  - cash
  - holdings
metadata:
  author: "alpha_arena_team"
  created: "2026-02-01"
  metrics:
    usage_count: 0
    avg_quality_score: null
    win_rate: null
```

**Integration:**
```python
# Modified /Users/jesse.kemp/Dev/alpha_arena/src/models/api_model.py
from ..prompts import PromptRegistry

class AnthropicModel(BaseTradingModel):
    def __init__(self, name: str, model: str, api_key: str, temperature: float = 0.7):
        super().__init__(name, temperature)
        self.prompt_registry = PromptRegistry()
        self.signal_prompt = self.prompt_registry.get_prompt("trade_signal_generation", version="1.0.0")

    def _format_prompt(self, market_data: Dict, portfolio: Portfolio) -> str:
        return self.signal_prompt.render(
            symbol=market_data["symbol"],
            price=market_data["price"],
            change_pct=market_data["change_pct"],
            volume=market_data["volume"],
            regime=market_data.get("regime", "unknown"),
            cash=portfolio.cash,
            holdings=portfolio.holdings,
        )
```

**Success Metrics:**
- 100% of prompts migrated to YAML templates
- A/B test win rate: v2 vs v1 prompts
- Prompt quality tracking enabled

---

#### Priority 0: AI-as-a-Judge Evaluation

**Why:** Alpha Arena generates trade signals but doesn't validate quality before execution.

**Current Gap:** Signal quality only known AFTER trade closes (days/weeks later).

**Implementation:**
```python
# New file: /Users/jesse.kemp/Dev/alpha_arena/src/intelligence/evaluation/signal_judge.py

from cortex.intelligence.evaluation.quality_judge import QualityJudge

class TradeSignalJudge(QualityJudge):
    """Evaluate trade signal quality before execution"""

    EVALUATION_CRITERIA = {
        "reasoning_clarity": "Is the reasoning clear and specific?",
        "risk_assessment": "Does it acknowledge risks?",
        "actionability": "Is the signal specific enough to execute?",
        "market_context": "Does it reference current market conditions?",
    }

    async def evaluate_signal(self, signal: TradeSignal, market_data: Dict) -> SignalScore:
        """Evaluate a trade signal before execution"""
        prompt = f"""
        Evaluate this trade signal on a scale of 1-10:

        Signal:
        - Action: {signal.action}
        - Symbol: {signal.symbol}
        - Reasoning: {signal.reasoning}

        Market Context:
        - Price: {market_data['price']}
        - Regime: {market_data.get('regime')}

        Rate on these criteria:
        - Reasoning clarity (1-10)
        - Risk assessment (1-10)
        - Actionability (1-10)
        - Market context (1-10)

        Return JSON: {{"reasoning_clarity": X, "risk_assessment": Y, ...}}
        """

        response = await self.client.messages.create(
            model="claude-3-5-haiku-20241022",  # Fast + cheap
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
        )

        return self._parse_scores(response)
```

**Integration:**
```python
# Modified /Users/jesse.kemp/Dev/alpha_arena/src/engine.py

async def run_single_cycle(self):
    # ... existing code ...

    # Evaluate signal before execution
    if signal:
        score = await self.signal_judge.evaluate_signal(signal, market_data)

        # Only execute high-quality signals
        if score.overall_score < 6.0:
            logger.warning("low_quality_signal_rejected",
                          model=model.name,
                          score=score.overall_score,
                          reasoning=signal.reasoning)
            continue

        # Store evaluation for learning
        await self.db.store_signal_evaluation(signal.id, score)
```

**Success Metrics:**
- Correlation with trade outcomes > 0.7
- Evaluation latency < 500ms
- Low-quality signals rejected before execution

---

#### Priority 0: Hybrid Retrieval for Pattern Matching

**Why:** Alpha Arena queries Cortex for similar trades but uses simple keyword matching.

**Current Implementation:**
```python
# /Users/jesse.kemp/Dev/alpha_arena/src/intelligence/cortex_bridge.py:131
similarity = self._calculate_similarity(reasoning, trade.get("reasoning", ""))
# Simple Jaccard similarity - misses semantic matches
```

**Gap:** Misses semantically similar trades:
- "Breakout above resistance" vs. "Price breaking key level" = LOW similarity (keyword)
- But semantically SAME pattern

**Implementation:**
```python
# Modified /Users/jesse.kemp/Dev/alpha_arena/src/intelligence/cortex_bridge.py

from cortex.intelligence.memory.hybrid_retriever import HybridRetriever

class CortexBridge:
    def __init__(self):
        # ... existing code ...
        self.hybrid_retriever = HybridRetriever(
            patterns=self._load_trade_patterns(),
            embeddings_client=get_embeddings_client()
        )

    def query_similar_setups(self, symbol: str, action: str, reasoning: str, limit: int = 20):
        """Query with hybrid BM25 + embedding search"""

        # Hybrid search (keyword + semantic)
        similar_trades = self.hybrid_retriever.search(
            query=f"{action} {symbol} {reasoning}",
            limit=limit,
            alpha=0.5  # Equal weight to BM25 and embeddings
        )

        # Enrich with outcomes
        for trade, similarity in similar_trades:
            trade["similarity"] = similarity
            # ... existing outcome calculation ...
```

**Success Metrics:**
- Recall@5 improves from 40% → 60%+
- Semantic matches: "breakout" finds "price breaking level"
- Search latency < 100ms (cached embeddings)

---

#### Priority 0: Defensive Prompting

**Why:** LLM-generated trade signals can hallucinate or go out of scope.

**Current Risk:**
- Signal says "BUY 200% of portfolio" (impossible)
- Reasoning is vague: "Looks good"
- Suggests trading assets not in portfolio

**Implementation:**
```python
# Modified /Users/jesse.kemp/Dev/alpha_arena/src/models/api_model.py

class AnthropicModel(BaseTradingModel):

    # Input validation
    INPUT_VALIDATORS = [
        MaxLengthValidator(max_chars=5000),
        InjectionDetector(),  # Detect prompt injection in market data
    ]

    # Output validation
    OUTPUT_VALIDATORS = [
        SignalFormatValidator(),  # Must have ACTION, SYMBOL, SIZE, REASONING
        PositionSizeValidator(max_pct=20),  # Size <= 20% of portfolio
        ReasoningLengthValidator(min_words=10),  # Reasoning must be detailed
        SymbolValidator(allowed_symbols=EXCHANGE_SYMBOLS),  # Only trade listed assets
    ]

    async def analyze_market(self, market_data: Dict, portfolio: Portfolio):
        # Validate input
        market_data = self._validate_input(market_data)

        # Add defensive guardrails to prompt
        prompt = self._format_prompt_with_guardrails(market_data, portfolio)

        # Get response
        response = await self._query_model(prompt)

        # Validate output
        signal = self.signal_parser.parse_response(response)
        if signal:
            signal = self._validate_output(signal, portfolio)

        return signal

    def _format_prompt_with_guardrails(self, market_data: Dict, portfolio: Portfolio) -> str:
        base_prompt = self.signal_prompt.render(...)

        guardrails = """
        [GUARDRAILS]
        - Only trade symbols from the approved list
        - Position size MUST be <= 20% of portfolio
        - Provide detailed reasoning (minimum 10 words)
        - Do not hallucinate prices or data
        - Format: ACTION: [BUY/SELL/HOLD], SYMBOL: [symbol], SIZE: [X%], REASONING: [detailed]

        """

        return guardrails + base_prompt
```

**Success Metrics:**
- Injection attempts blocked: 100%
- Out-of-scope signals caught: >90%
- Invalid signal format rate: <5%

---

#### Priority 1: Implicit Feedback Collection

**Why:** Alpha Arena only logs explicit outcomes (trade P&L). Misses implicit signals.

**Current Gap:**
- Model suggests BUY, but circuit breaker prevents execution → IGNORED (implicit negative feedback)
- Model confidence = 0.9 but execution shows 0.3 → OVERRIDE (calibration issue)
- Winning signal from Model A gets copied by Model B → FOLLOW (implicit validation)

**Implementation:**
```python
# New file: /Users/jesse.kemp/Dev/alpha_arena/src/intelligence/feedback/implicit_collector.py

from cortex.intelligence.feedback.implicit_collector import ImplicitFeedbackCollector

class TradingImplicitCollector(ImplicitFeedbackCollector):
    """Track implicit feedback from model behavior"""

    def track_signal_generated(self, signal_id: str, signal: TradeSignal, model: str):
        """Track when a model generates a signal"""
        self.pending_recommendations[signal_id] = {
            "signal": signal,
            "model": model,
            "shown_at": datetime.now(),
            "executed": False,
        }

    def track_signal_executed(self, signal_id: str):
        """Signal was executed = FOLLOW"""
        if signal_id in self.pending_recommendations:
            self._log_follow(signal_id, similarity=1.0, action="execute")

    def track_circuit_breaker_block(self, signal_id: str, reason: str):
        """Signal blocked by circuit breaker = IGNORE (implicit negative)"""
        if signal_id in self.pending_recommendations:
            self._log_ignore(signal_id, reason=reason)

    def track_confidence_override(self, signal_id: str, original: float, adjusted: float):
        """Confidence adjusted = OVERRIDE"""
        if signal_id in self.pending_recommendations:
            self._log_override(signal_id,
                              original_confidence=original,
                              adjusted_confidence=adjusted)
```

**Integration Points:**
- `/Users/jesse.kemp/Dev/alpha_arena/src/trading/executor.py` - Track execution/rejection
- `/Users/jesse.kemp/Dev/alpha_arena/src/engine.py` - Track signal generation
- Cortex bridge - Feed to Cortex for model calibration

**Success Metrics:**
- 100+ implicit signals per day
- Follow detection accuracy > 80%
- Circuit breaker blocks correlate with low-quality signals

---

#### Priority 1: Data Quality Framework

**Why:** Bad market data leads to bad trades. No systematic quality tracking.

**Implementation:**
```python
# New file: /Users/jesse.kemp/Dev/alpha_arena/src/intelligence/data/quality_tracker.py

from cortex.intelligence.quality.data_quality import QualityDimensions, DataQualityTracker

class MarketDataQualityTracker(DataQualityTracker):
    """Track quality of market data (OHLCV, indicators, etc.)"""

    def assess_ohlcv(self, ohlcv: pd.DataFrame, symbol: str) -> QualityDimensions:
        return QualityDimensions(
            completeness=self._check_no_gaps(ohlcv),  # No missing candles
            consistency=self._check_ohlc_relationships(ohlcv),  # high >= low, etc.
            accuracy=self._cross_validate_exchanges(ohlcv),  # vs. other exchanges
            timeliness=self._check_data_freshness(ohlcv),  # < 5 min old
            uniqueness=self._check_duplicate_candles(ohlcv),  # No duplicates
            validity=self._check_price_sanity(ohlcv),  # Prices > 0, realistic
        )

    def assess_indicator(self, indicator: Indicator, symbol: str) -> QualityDimensions:
        """Quality check for derived indicators (RSI, MACD, etc.)"""
        ...
```

**Integration:**
```python
# /Users/jesse.kemp/Dev/alpha_arena/src/intelligence/data/data_aggregator.py

class DataAggregator:
    def __init__(self, exchange: str):
        self.quality_tracker = MarketDataQualityTracker()
        # ... existing code ...

    async def get_ohlcv(self, symbol: str, timeframe: str, limit: int):
        data = await self.market_client.fetch_ohlcv(symbol, timeframe, limit)

        # Quality check
        quality = self.quality_tracker.assess_ohlcv(data, symbol)

        if quality.overall_score() < 0.6:
            logger.error("low_quality_market_data",
                        symbol=symbol,
                        quality_score=quality.overall_score())
            # Fallback or reject

        return data
```

**Success Metrics:**
- 100% of market data scored
- Quality score > 0.7 for production data
- Bad data rejected before model ingestion

---

#### Priority 2: Three-Tier Memory (Optional)

**Why:** Recent trades more relevant than old ones. But Alpha Arena already has time-based filtering.

**Current State:** Cortex bridge stores all trades in JSONL files. No automatic promotion/demotion.

**If Implemented:**
- Short-term: Last 24 hours of trades (in-memory)
- Working: Last 30 days (SQLite)
- Long-term: All historical trades (JSONL)

**Value:** Faster pattern queries, automatic relevance weighting.

**Defer to:** After P0/P1 improvements validated.

---

## Integration Roadmap

### Phase 1: Foundation (Week 1-2)

**Goal:** Deploy data quality and defensive prompting to both projects.

```
VortexV2:
  ├─ Data Quality Framework (weather-specific)
  │  └─ GRIB quality checks
  │  └─ NDBC observation validation
  └─ Defensive prompting (if adding LLM explanations)

Alpha Arena:
  ├─ Data Quality Framework (market-specific)
  │  └─ OHLCV validation
  │  └─ Indicator sanity checks
  ├─ Defensive Prompting
  │  └─ Signal validation
  │  └─ Guardrails in prompts
  └─ Prompt Versioning System
     └─ Migrate inline prompts to YAML
     └─ A/B testing setup
```

**Deliverables:**
- `cortex/intelligence/quality/data_quality.py` (shared)
- `Vortex/VortexV2/app/core/validation/data_quality.py` (weather-specific)
- `alpha_arena/src/intelligence/data/quality_tracker.py` (market-specific)
- `alpha_arena/src/prompts/` directory structure
- Quality dashboards in both projects

---

### Phase 2: Evaluation & Feedback (Week 3-4)

**Goal:** Add AI-as-a-judge and implicit feedback collection.

```
VortexV2:
  └─ Implicit Feedback Collection
     └─ Track forecast views
     └─ Track route commits
     └─ Track hedge requests

Alpha Arena:
  ├─ AI-as-a-Judge Evaluation
  │  └─ Signal quality scoring
  │  └─ Pre-execution validation
  ├─ Implicit Feedback Collection
  │  └─ Track signal execution/rejection
  │  └─ Track circuit breaker blocks
  └─ Hybrid Retrieval
     └─ BM25 + embedding search for patterns
```

**Deliverables:**
- `cortex/intelligence/evaluation/quality_judge.py` (shared)
- `cortex/intelligence/feedback/implicit_collector.py` (shared)
- `cortex/intelligence/memory/hybrid_retriever.py` (shared)
- `Vortex/VortexV2/app/intelligence/implicit_feedback.py`
- `alpha_arena/src/intelligence/evaluation/signal_judge.py`
- `alpha_arena/src/intelligence/feedback/implicit_collector.py`

---

### Phase 3: Optimization (Week 5-6)

**Goal:** Context optimization and advanced memory (optional).

```
Both Projects:
  ├─ Three-Tier Memory (if needed)
  │  └─ Short-term, working, long-term separation
  └─ Lost-in-Middle Optimization (if using long contexts)
     └─ Position-aware context ordering
```

**Deliverables:**
- `cortex/intelligence/memory/tiered_memory.py` (shared)
- `cortex/intelligence/context_optimizer.py` (shared)
- Integration into both project bridges

---

### Cortex Bridge Enhancements

Both projects already integrate with Cortex via bridges. Enhancements needed:

**VortexV2 Bridge Enhancements:**
```python
# /Users/jesse.kemp/Dev/Vortex/VortexV2/app/intelligence/cortex_bridge.py

class VortexCortexBridge:
    # Add:
    def log_data_quality(self, data_type: str, quality: QualityDimensions):
        """Log data quality metrics to Cortex"""

    def log_implicit_feedback(self, forecast_id: str, action: str, metadata: Dict):
        """Log implicit user feedback"""

    def get_forecast_patterns(self, conditions: Dict) -> List[Pattern]:
        """Query Cortex for similar weather patterns (hybrid retrieval)"""
```

**Alpha Arena Bridge Enhancements:**
```python
# /Users/jesse.kemp/Dev/alpha_arena/src/intelligence/cortex_bridge.py

class CortexBridge:
    # Add:
    def log_signal_quality(self, signal_id: str, quality: SignalScore):
        """Log AI-as-judge signal quality scores"""

    def log_implicit_feedback(self, signal_id: str, action: str, metadata: Dict):
        """Log implicit model feedback"""

    def query_similar_setups_hybrid(self, symbol: str, reasoning: str) -> List[Dict]:
        """Use hybrid retrieval for pattern matching"""
```

---

## Success Metrics Summary

### VortexV2 Success Metrics

| Metric | Baseline | Target | Timeline |
|--------|----------|--------|----------|
| Data quality coverage | 0% | 100% | Week 2 |
| GRIB quality score | N/A | >0.7 | Week 2 |
| Implicit feedback signals/day | 0 | 50+ | Week 4 |
| Follow detection accuracy | N/A | >80% | Week 4 |

### Alpha Arena Success Metrics

| Metric | Baseline | Target | Timeline |
|--------|----------|--------|----------|
| Prompts in YAML templates | 0% | 100% | Week 2 |
| Signal quality evaluation | 0% | 100% | Week 3 |
| AI-judge correlation with outcomes | N/A | >0.7 | Week 4 |
| Pattern search recall@5 | ~40% | >60% | Week 4 |
| Implicit feedback signals/day | ~5 | 100+ | Week 4 |
| Data quality coverage | 0% | 100% | Week 2 |

---

## Dependencies & Blockers

### Shared Dependencies
- Cortex improvements must be implemented first (foundation)
- Embeddings client must exist for hybrid retrieval
- Claude API access for AI-as-a-judge

### VortexV2-Specific
- None (self-contained)

### Alpha Arena-Specific
- Prompt migration requires testing (don't break existing behavior)
- AI-as-judge adds latency - must be < 500ms

---

## Risk Assessment

### High Risk
- **Alpha Arena prompt migration:** Could break existing signal generation
  - Mitigation: A/B test with rollback capability
- **AI-as-judge latency:** Could slow down trading loop
  - Mitigation: Use Haiku (fast model), cache evaluations

### Medium Risk
- **Data quality false positives:** May reject valid data
  - Mitigation: Start with warnings only, tune thresholds
- **Implicit feedback noise:** May misclassify actions
  - Mitigation: Require multiple signals for confidence

### Low Risk
- **VortexV2 has minimal LLM usage:** Lower risk of prompt issues
- **Hybrid retrieval is additive:** Fallback to keyword search if embeddings fail

---

## Conclusion

**VortexV2** benefits most from:
1. Data Quality Framework (P0) - weather data must be pristine
2. Implicit Feedback Collection (P1) - learn which forecasts sailors trust

**Alpha Arena** benefits most from:
1. Prompt Versioning (P0) - control + A/B test LLM strategies
2. AI-as-a-Judge (P0) - validate signals before execution
3. Hybrid Retrieval (P0) - semantic pattern matching
4. Defensive Prompting (P0) - prevent hallucinations
5. Implicit Feedback (P1) - calibrate model confidence

**Integration Strategy:**
- Implement shared improvements in Cortex first
- VortexV2 and Alpha Arena inherit via bridges
- Each project adds domain-specific extensions

**Next Steps:**
1. Review this assessment with stakeholders
2. Prioritize Phase 1 (Data Quality + Defensive Prompting)
3. Create implementation tickets in `/Users/jesse.kemp/Dev/cortex/docs/`
4. Begin Alpha Arena prompt migration (highest value)

---

**Document Status:** Ready for Review
**Recommended Review Date:** 2026-02-03
**Next Review:** After Phase 1 completion
