# CortexDBx MVP: Implementation Guide
## Full Functioning MVP with Synthetic Data and Agent Teams

**Version:** 1.0  
**Status:** Implementation Specification  
**Branch:** `feature/cortex-dbx`

---

## 1. MVP Overview

### 1.1 What We're Building

A **fully functional CortexDBx deployment** that demonstrates the complete learning loop using synthetic data across six validated use cases, scaled via agent teams.

```
+-------------------+     +-------------------+     +-------------------+
|  SYNTHETIC DATA   |     |   CORTEXDBX       |     |   AGENT TEAMS     |
|  GENERATOR        |---->|   CORE SYSTEM     |---->|   (Scaling)       |
|                   |     |                   |     |                   |
| - 6 use cases     |     | - Delta tables    |     | - Domain agents   |
| - 10K+ outcomes   |     | - Learning loop   |     | - Orchestrator    |
| - Realistic dist. |     | - Calibration     |     | - Parallel exec   |
+-------------------+     +-------------------+     +-------------------+
```

### 1.2 Selected Use Cases

| # | Domain | Use Case | Primary Signal Source |
|---|--------|----------|----------------------|
| 1 | Financial Services | Fraud Investigation Prioritization | Transaction patterns, alert history |
| 2 | Healthcare | Clinical Trial Enrollment Optimization | Trial criteria, enrollment outcomes |
| 3 | Manufacturing | Maintenance Decision Optimization | Sensor data, repair history |
| 4 | Retail/Marketing | Campaign Effectiveness | Campaign results, conversion data |
| 5 | Security Operations | Incident Response | Alert logs, playbook outcomes |
| 6 | Supply Chain | Routing Decisions | Delivery outcomes, supplier performance |

### 1.3 Success Criteria

| Metric | Target |
|--------|--------|
| Outcomes ingested | 10,000+ per use case |
| Calibration accuracy | Brier score < 0.25 |
| Recommendation latency | < 2s (dashboard), < 500ms (cached API) |
| Agent team throughput | 100+ outcomes/minute parallel processing |

---

## 2. Architecture

### 2.1 System Components

```
+------------------------------------------------------------------+
|                        DATABRICKS WORKSPACE                       |
+------------------------------------------------------------------+
|                                                                    |
|  +------------------+    +------------------+    +----------------+ |
|  | SYNTHETIC DATA   |    | OBSERVER JOBS    |    | ORIENTATION    | |
|  | GENERATOR        |--->| (Batch/Stream)   |--->| CORE           | |
|  | (Notebooks/Jobs) |    |                  |    | (Calibration)  | |
|  +------------------+    +------------------+    +----------------+ |
|                                                          |         |
|                                                          v         |
|  +------------------+    +------------------+    +----------------+ |
|  | AGENT TEAMS      |<---| BROKER           |<---| OUTCOME GRAPH  | |
|  | (Domain Experts) |    | (Dashboard/API)  |    | (Delta Tables) | |
|  +------------------+    +------------------+    +----------------+ |
|                                                                    |
+------------------------------------------------------------------+
                                   |
                                   v
                    +----------------------------+
                    | UNITY CATALOG GOVERNANCE   |
                    +----------------------------+
```

### 2.2 Delta Table Schema

```sql
-- All tables in: cortex_catalog.cortex_mvp

-- 1. Raw signals from synthetic generator
CREATE TABLE signals_raw (
    signal_id STRING NOT NULL,
    signal_type STRING NOT NULL,        -- 'fraud_alert', 'trial_enrollment', etc.
    domain STRING NOT NULL,             -- 'financial', 'healthcare', etc.
    payload STRING NOT NULL,            -- JSON: domain-specific fields
    source_system STRING,
    created_at TIMESTAMP NOT NULL,
    partition_date DATE GENERATED ALWAYS AS (CAST(created_at AS DATE))
)
USING DELTA
PARTITIONED BY (partition_date, domain)
TBLPROPERTIES ('delta.autoOptimize.optimizeWrite' = 'true');

-- 2. Context entities
CREATE TABLE contexts (
    context_id STRING NOT NULL,
    context_hash STRING NOT NULL,       -- SHA256 fingerprint
    domain STRING NOT NULL,
    factors STRING NOT NULL,            -- JSON array of {key, value}
    first_seen TIMESTAMP NOT NULL,
    last_seen TIMESTAMP NOT NULL,
    occurrence_count BIGINT DEFAULT 1
)
USING DELTA
CLUSTERED BY (context_hash) INTO 32 BUCKETS;

-- 3. Strategy entities
CREATE TABLE strategies (
    strategy_id STRING NOT NULL,
    name STRING NOT NULL,
    description STRING,
    domain STRING NOT NULL,
    category STRING,                    -- 'rewrite', 'escalate', 'reroute', etc.
    created_at TIMESTAMP NOT NULL
)
USING DELTA;

-- 4. Outcome events
CREATE TABLE outcomes (
    outcome_id STRING NOT NULL,
    context_id STRING NOT NULL,
    strategy_id STRING NOT NULL,
    result STRING NOT NULL,             -- 'SUCCESS', 'FAILURE', 'PARTIAL'
    confidence_prior DOUBLE,
    confidence_posterior DOUBLE,
    evidence STRING NOT NULL,           -- JSON: links to source data
    actor STRING,                       -- user or system that recorded
    notes STRING,
    created_at TIMESTAMP NOT NULL,
    partition_date DATE GENERATED ALWAYS AS (CAST(created_at AS DATE))
)
USING DELTA
PARTITIONED BY (partition_date)
CLUSTERED BY (context_id, strategy_id) INTO 64 BUCKETS;

-- 5. Calibrated edges (materialized view)
CREATE TABLE context_strategy_edges (
    context_id STRING NOT NULL,
    strategy_id STRING NOT NULL,
    success_count BIGINT NOT NULL,
    failure_count BIGINT NOT NULL,
    partial_count BIGINT NOT NULL,
    alpha DOUBLE NOT NULL,              -- Beta prior
    beta DOUBLE NOT NULL,               -- Beta prior
    confidence DOUBLE NOT NULL,         -- Current P(success)
    last_updated TIMESTAMP NOT NULL,
    PRIMARY KEY (context_id, strategy_id)
)
USING DELTA;

-- 6. Generated recommendations
CREATE TABLE recommendations (
    recommendation_id STRING NOT NULL,
    context_id STRING NOT NULL,
    strategy_id STRING NOT NULL,
    confidence DOUBLE NOT NULL,
    evidence_summary STRING,            -- JSON: top evidence references
    surface STRING NOT NULL,            -- 'dashboard', 'webhook', 'agent_tool'
    expires_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL
)
USING DELTA;

-- 7. User feedback
CREATE TABLE feedback (
    feedback_id STRING NOT NULL,
    recommendation_id STRING NOT NULL,
    rating STRING NOT NULL,             -- 'thumbs_up', 'thumbs_down', 'neutral'
    outcome_override STRING,            -- Optional: user-reported actual outcome
    actor STRING NOT NULL,
    notes STRING,
    created_at TIMESTAMP NOT NULL
)
USING DELTA;
```

---

## 3. Synthetic Data Generator

### 3.1 Generator Architecture

```python
# cortexdbx/synthetic/generator.py

from dataclasses import dataclass
from typing import List, Dict, Generator
import random
import hashlib
import json
from datetime import datetime, timedelta
import uuid

@dataclass
class SyntheticConfig:
    domain: str
    num_contexts: int
    num_strategies: int
    num_outcomes: int
    success_rate_range: tuple  # (min, max) for strategy success rates
    time_span_days: int
    
@dataclass
class DomainConfig:
    """Domain-specific configuration for realistic data generation."""
    context_factors: List[str]
    strategy_types: List[str]
    outcome_weights: Dict[str, float]  # result -> probability

# Domain configurations for 6 use cases
DOMAIN_CONFIGS = {
    "fraud_investigation": DomainConfig(
        context_factors=[
            "alert_type", "transaction_amount_bucket", "account_age_bucket",
            "swift_code_region", "time_of_day", "device_fingerprint_match",
            "historical_fraud_rate", "velocity_score"
        ],
        strategy_types=[
            "auto_close_low_risk", "escalate_to_analyst", "freeze_account",
            "request_verification", "manual_review_queue", "ml_rescore"
        ],
        outcome_weights={"SUCCESS": 0.70, "FAILURE": 0.20, "PARTIAL": 0.10}
    ),
    
    "clinical_trial": DomainConfig(
        context_factors=[
            "trial_phase", "therapeutic_area", "inclusion_criteria_count",
            "site_location", "patient_demographics", "prior_trial_history",
            "enrollment_velocity", "dropout_rate"
        ],
        strategy_types=[
            "relax_bmi_criteria", "add_recruitment_site", "extend_age_range",
            "modify_exclusion_criteria", "increase_compensation", "digital_outreach"
        ],
        outcome_weights={"SUCCESS": 0.55, "FAILURE": 0.30, "PARTIAL": 0.15}
    ),
    
    "maintenance": DomainConfig(
        context_factors=[
            "equipment_type", "sensor_reading_pattern", "operating_hours",
            "last_maintenance_days", "failure_history", "manufacturer",
            "environmental_conditions", "criticality_level"
        ],
        strategy_types=[
            "replace_bearing", "check_alignment", "lubrication_cycle",
            "full_inspection", "sensor_recalibration", "schedule_shutdown"
        ],
        outcome_weights={"SUCCESS": 0.65, "FAILURE": 0.25, "PARTIAL": 0.10}
    ),
    
    "marketing_campaign": DomainConfig(
        context_factors=[
            "audience_segment", "channel", "creative_type", "offer_type",
            "time_of_year", "competitor_activity", "budget_tier", "campaign_duration"
        ],
        strategy_types=[
            "urgency_messaging", "value_messaging", "social_proof",
            "personalization", "retargeting", "influencer_partnership"
        ],
        outcome_weights={"SUCCESS": 0.45, "FAILURE": 0.35, "PARTIAL": 0.20}
    ),
    
    "security_incident": DomainConfig(
        context_factors=[
            "alert_severity", "attack_vector", "affected_systems",
            "time_to_detection", "attacker_sophistication", "data_sensitivity",
            "business_hours", "prior_incident_similarity"
        ],
        strategy_types=[
            "block_ip", "geo_block_rate_limit", "isolate_system",
            "credential_rotation", "forensic_capture", "executive_notification"
        ],
        outcome_weights={"SUCCESS": 0.60, "FAILURE": 0.25, "PARTIAL": 0.15}
    ),
    
    "supply_chain": DomainConfig(
        context_factors=[
            "product_category", "origin_region", "destination_region",
            "shipping_mode", "weather_conditions", "supplier_tier",
            "demand_urgency", "customs_complexity"
        ],
        strategy_types=[
            "primary_supplier", "backup_supplier", "air_freight_upgrade",
            "split_shipment", "local_warehouse", "expedited_customs"
        ],
        outcome_weights={"SUCCESS": 0.55, "FAILURE": 0.30, "PARTIAL": 0.15}
    )
}

class SyntheticDataGenerator:
    """Generate realistic synthetic data for CortexDBx MVP."""
    
    def __init__(self, domain: str, seed: int = 42):
        self.domain = domain
        self.config = DOMAIN_CONFIGS[domain]
        random.seed(seed)
        
        # Pre-generate strategies with fixed success rates
        self.strategies = self._generate_strategies()
        
    def _generate_strategies(self) -> Dict[str, Dict]:
        """Generate strategies with inherent success rates."""
        strategies = {}
        for i, name in enumerate(self.config.strategy_types):
            # Each strategy has an inherent success rate (what we want to learn)
            base_success_rate = random.uniform(0.3, 0.9)
            strategies[f"strategy_{self.domain}_{i}"] = {
                "strategy_id": f"strategy_{self.domain}_{i}",
                "name": name,
                "domain": self.domain,
                "inherent_success_rate": base_success_rate,
                "category": random.choice(["primary", "fallback", "experimental"])
            }
        return strategies
    
    def _generate_context(self) -> Dict:
        """Generate a random context."""
        factors = []
        for factor_name in self.config.context_factors:
            # Generate realistic values based on factor type
            if "bucket" in factor_name or "tier" in factor_name:
                value = random.choice(["low", "medium", "high"])
            elif "rate" in factor_name or "score" in factor_name:
                value = str(round(random.uniform(0, 1), 2))
            elif "count" in factor_name:
                value = str(random.randint(1, 20))
            elif "days" in factor_name or "hours" in factor_name:
                value = str(random.randint(1, 365))
            else:
                value = f"value_{random.randint(1, 10)}"
            
            factors.append({"key": factor_name, "value": value})
        
        # Create deterministic hash
        factors_str = json.dumps(sorted(factors, key=lambda x: x["key"]))
        context_hash = hashlib.sha256(factors_str.encode()).hexdigest()[:16]
        
        return {
            "context_id": f"ctx_{context_hash}",
            "context_hash": context_hash,
            "domain": self.domain,
            "factors": factors
        }
    
    def _generate_outcome(self, context: Dict, strategy: Dict, 
                          timestamp: datetime) -> Dict:
        """Generate an outcome based on strategy's inherent success rate."""
        # Outcome is probabilistic based on strategy's inherent rate
        inherent_rate = strategy["inherent_success_rate"]
        
        # Add some noise for realism
        effective_rate = inherent_rate + random.gauss(0, 0.1)
        effective_rate = max(0.05, min(0.95, effective_rate))
        
        roll = random.random()
        if roll < effective_rate:
            result = "SUCCESS"
        elif roll < effective_rate + 0.15:
            result = "PARTIAL"
        else:
            result = "FAILURE"
        
        return {
            "outcome_id": str(uuid.uuid4()),
            "context_id": context["context_id"],
            "strategy_id": strategy["strategy_id"],
            "result": result,
            "evidence": json.dumps({
                "source": "synthetic_generator",
                "context_factors": context["factors"][:3],  # Sample
                "strategy_name": strategy["name"]
            }),
            "actor": f"synthetic_user_{random.randint(1, 10)}",
            "created_at": timestamp.isoformat()
        }
    
    def generate_dataset(self, num_outcomes: int, 
                         days_span: int = 90) -> Generator[Dict, None, None]:
        """Generate a complete synthetic dataset."""
        
        # Generate pool of contexts
        num_contexts = min(num_outcomes // 10, 500)  # ~10 outcomes per context
        contexts = [self._generate_context() for _ in range(num_contexts)]
        
        # Generate outcomes over time span
        start_date = datetime.now() - timedelta(days=days_span)
        
        for i in range(num_outcomes):
            # Random timestamp within span
            random_days = random.uniform(0, days_span)
            timestamp = start_date + timedelta(days=random_days)
            
            # Select context and strategy
            context = random.choice(contexts)
            strategy = random.choice(list(self.strategies.values()))
            
            # Generate outcome
            outcome = self._generate_outcome(context, strategy, timestamp)
            
            yield {
                "context": context,
                "strategy": strategy,
                "outcome": outcome
            }
    
    def get_ground_truth(self) -> Dict[str, float]:
        """Return ground truth success rates for validation."""
        return {
            s["strategy_id"]: s["inherent_success_rate"] 
            for s in self.strategies.values()
        }


def generate_all_domains(outcomes_per_domain: int = 10000) -> Dict[str, List]:
    """Generate synthetic data for all 6 use cases."""
    all_data = {}
    
    for domain in DOMAIN_CONFIGS.keys():
        print(f"Generating {outcomes_per_domain} outcomes for {domain}...")
        generator = SyntheticDataGenerator(domain)
        
        data = list(generator.generate_dataset(outcomes_per_domain))
        all_data[domain] = {
            "outcomes": data,
            "ground_truth": generator.get_ground_truth(),
            "strategies": generator.strategies
        }
    
    return all_data
```

### 3.2 Databricks Notebook: Data Generation

```python
# Notebook: 01_generate_synthetic_data

# COMMAND ----------
# %pip install -q pandas

# COMMAND ----------
from pyspark.sql import SparkSession
from pyspark.sql.types import *
import json

# Import generator (assume uploaded to workspace)
# from cortexdbx.synthetic.generator import generate_all_domains, DOMAIN_CONFIGS

# COMMAND ----------
# Configuration
CATALOG = "cortex_catalog"
SCHEMA = "cortex_mvp"
OUTCOMES_PER_DOMAIN = 10000

# COMMAND ----------
# Generate data for all domains
spark.sql(f"CREATE CATALOG IF NOT EXISTS {CATALOG}")
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SCHEMA}")
spark.sql(f"USE {CATALOG}.{SCHEMA}")

# COMMAND ----------
# Generate and write contexts
contexts_data = []
strategies_data = []
outcomes_data = []

for domain, config in DOMAIN_CONFIGS.items():
    generator = SyntheticDataGenerator(domain)
    
    for record in generator.generate_dataset(OUTCOMES_PER_DOMAIN):
        contexts_data.append(record["context"])
        strategies_data.append(record["strategy"])
        outcomes_data.append(record["outcome"])

# COMMAND ----------
# Write to Delta tables
contexts_df = spark.createDataFrame(contexts_data)
contexts_df.write.mode("overwrite").saveAsTable("contexts")

strategies_df = spark.createDataFrame(strategies_data)
strategies_df.write.mode("overwrite").saveAsTable("strategies")

outcomes_df = spark.createDataFrame(outcomes_data)
outcomes_df.write.mode("overwrite").saveAsTable("outcomes")

# COMMAND ----------
# Verify
display(spark.sql("SELECT domain, COUNT(*) as count FROM outcomes GROUP BY domain"))
```

---

## 4. Calibration Engine

### 4.1 Beta-Binomial Calibration

```python
# cortexdbx/calibration/engine.py

from dataclasses import dataclass
from typing import Dict, Tuple
import math

@dataclass
class CalibrationState:
    alpha: float  # Beta prior: successes + prior
    beta: float   # Beta prior: failures + prior
    success_count: int
    failure_count: int
    partial_count: int
    
    @property
    def confidence(self) -> float:
        """Current P(success) estimate."""
        return self.alpha / (self.alpha + self.beta)
    
    @property
    def evidence_count(self) -> int:
        return self.success_count + self.failure_count + self.partial_count
    
    @property
    def uncertainty(self) -> float:
        """Variance of Beta distribution - higher = more uncertain."""
        a, b = self.alpha, self.beta
        return (a * b) / ((a + b) ** 2 * (a + b + 1))


class CalibrationEngine:
    """
    Bayesian calibration using Beta-Binomial model.
    
    Updates confidence per (context, strategy) pair based on outcomes.
    """
    
    def __init__(self, prior_alpha: float = 1.0, prior_beta: float = 1.0):
        """
        Initialize with prior beliefs.
        
        Default: Uniform prior (alpha=1, beta=1) = no prior knowledge
        Informative prior: alpha=2, beta=2 = slight belief in 50% success
        """
        self.prior_alpha = prior_alpha
        self.prior_beta = prior_beta
        self.states: Dict[Tuple[str, str], CalibrationState] = {}
    
    def get_state(self, context_id: str, strategy_id: str) -> CalibrationState:
        """Get or create calibration state for (context, strategy)."""
        key = (context_id, strategy_id)
        if key not in self.states:
            self.states[key] = CalibrationState(
                alpha=self.prior_alpha,
                beta=self.prior_beta,
                success_count=0,
                failure_count=0,
                partial_count=0
            )
        return self.states[key]
    
    def update(self, context_id: str, strategy_id: str, result: str) -> CalibrationState:
        """
        Update calibration based on new outcome.
        
        result: 'SUCCESS' (counts as 1), 'PARTIAL' (counts as 0.5), 'FAILURE' (counts as 0)
        """
        state = self.get_state(context_id, strategy_id)
        
        if result == "SUCCESS":
            state.alpha += 1.0
            state.success_count += 1
        elif result == "PARTIAL":
            state.alpha += 0.5
            state.beta += 0.5
            state.partial_count += 1
        else:  # FAILURE
            state.beta += 1.0
            state.failure_count += 1
        
        return state
    
    def get_confidence(self, context_id: str, strategy_id: str) -> Tuple[float, str]:
        """
        Get current confidence with explanation.
        
        Returns: (confidence, explanation)
        """
        state = self.get_state(context_id, strategy_id)
        
        if state.evidence_count == 0:
            return 0.5, "No historical data"
        
        confidence = state.confidence
        explanation = (
            f"{confidence:.0%} confidence based on {state.evidence_count} outcomes "
            f"({state.success_count} success, {state.failure_count} failure, "
            f"{state.partial_count} partial)"
        )
        
        return confidence, explanation
    
    def evaluate_calibration(self, ground_truth: Dict[str, float]) -> Dict[str, float]:
        """
        Evaluate calibration quality against ground truth.
        
        Returns metrics including Brier score and precision at high confidence.
        """
        predictions = []
        actuals = []
        
        for (ctx, strat), state in self.states.items():
            if strat in ground_truth and state.evidence_count >= 5:
                predictions.append(state.confidence)
                actuals.append(ground_truth[strat])
        
        if not predictions:
            return {"error": "Insufficient data for evaluation"}
        
        # Brier score: mean squared error of probability estimates
        brier = sum((p - a) ** 2 for p, a in zip(predictions, actuals)) / len(predictions)
        
        # Mean absolute error
        mae = sum(abs(p - a) for p, a in zip(predictions, actuals)) / len(predictions)
        
        # Precision at high confidence (>0.8)
        high_conf = [(p, a) for p, a in zip(predictions, actuals) if p > 0.8]
        precision_high = (
            sum(1 for p, a in high_conf if a > 0.6) / len(high_conf)
            if high_conf else None
        )
        
        return {
            "brier_score": brier,
            "mean_absolute_error": mae,
            "precision_at_high_confidence": precision_high,
            "num_evaluated": len(predictions)
        }
```

### 4.2 Databricks Job: Calibration Update

```python
# Notebook: 02_run_calibration

# COMMAND ----------
from pyspark.sql import functions as F
from pyspark.sql.window import Window

# COMMAND ----------
# Read outcomes
outcomes_df = spark.table("outcomes")

# COMMAND ----------
# Aggregate outcomes per (context, strategy)
aggregated = outcomes_df.groupBy("context_id", "strategy_id").agg(
    F.sum(F.when(F.col("result") == "SUCCESS", 1).otherwise(0)).alias("success_count"),
    F.sum(F.when(F.col("result") == "FAILURE", 1).otherwise(0)).alias("failure_count"),
    F.sum(F.when(F.col("result") == "PARTIAL", 1).otherwise(0)).alias("partial_count"),
    F.max("created_at").alias("last_updated")
)

# COMMAND ----------
# Calculate Beta parameters and confidence
PRIOR_ALPHA = 1.0
PRIOR_BETA = 1.0

edges_df = aggregated.withColumn(
    "alpha",
    F.lit(PRIOR_ALPHA) + F.col("success_count") + 0.5 * F.col("partial_count")
).withColumn(
    "beta", 
    F.lit(PRIOR_BETA) + F.col("failure_count") + 0.5 * F.col("partial_count")
).withColumn(
    "confidence",
    F.col("alpha") / (F.col("alpha") + F.col("beta"))
)

# COMMAND ----------
# Write to edges table
edges_df.write.mode("overwrite").saveAsTable("context_strategy_edges")

# COMMAND ----------
# Verify calibration
display(
    spark.sql("""
        SELECT 
            s.domain,
            s.name as strategy_name,
            e.confidence,
            e.success_count,
            e.failure_count,
            e.success_count + e.failure_count + e.partial_count as total_outcomes
        FROM context_strategy_edges e
        JOIN strategies s ON e.strategy_id = s.strategy_id
        ORDER BY e.confidence DESC
        LIMIT 20
    """)
)
```

---

## 5. Agent Team Architecture

### 5.1 Agent Roles

```
+------------------------------------------------------------------+
|                        AGENT ORCHESTRATOR                         |
|  Coordinates work, manages parallelism, aggregates results        |
+------------------------------------------------------------------+
        |              |              |              |
        v              v              v              v
+------------+  +------------+  +------------+  +------------+
| FRAUD      |  | HEALTHCARE |  | MANUFACT.  |  | MARKETING  |
| DOMAIN     |  | DOMAIN     |  | DOMAIN     |  | DOMAIN     |
| AGENT      |  | AGENT      |  | AGENT      |  | AGENT      |
+------------+  +------------+  +------------+  +------------+
        |              |              |              |
        v              v              v              v
+------------------------------------------------------------------+
|                     SHARED OUTCOME GRAPH                          |
|                     (Delta Lake Tables)                           |
+------------------------------------------------------------------+
```

### 5.2 Agent Definitions

```python
# cortexdbx/agents/definitions.py

from dataclasses import dataclass
from typing import List, Dict, Callable
from enum import Enum

class AgentRole(Enum):
    ORCHESTRATOR = "orchestrator"
    DOMAIN_EXPERT = "domain_expert"
    CALIBRATOR = "calibrator"
    RECOMMENDER = "recommender"
    EVALUATOR = "evaluator"

@dataclass
class AgentConfig:
    role: AgentRole
    domain: str  # Which domain this agent handles
    capabilities: List[str]
    prompt_template: str
    tools: List[str]

AGENT_CONFIGS = {
    "orchestrator": AgentConfig(
        role=AgentRole.ORCHESTRATOR,
        domain="all",
        capabilities=[
            "coordinate_domain_agents",
            "aggregate_results",
            "manage_parallelism",
            "handle_failures"
        ],
        prompt_template="""
You are the CortexDBx Orchestrator Agent. Your role is to:
1. Coordinate work across domain-specific agents
2. Ensure parallel processing is efficient
3. Aggregate results from all domains
4. Handle failures gracefully

Current task: {task}
Available domain agents: {agents}
""",
        tools=["spawn_agent", "wait_for_agents", "aggregate_results"]
    ),
    
    "fraud_domain": AgentConfig(
        role=AgentRole.DOMAIN_EXPERT,
        domain="fraud_investigation",
        capabilities=[
            "analyze_fraud_patterns",
            "recommend_investigation_priority",
            "learn_from_resolution_outcomes"
        ],
        prompt_template="""
You are the Fraud Investigation Domain Agent for CortexDBx. Your expertise:
- Transaction pattern analysis
- False positive identification  
- Investigation prioritization

Context: {context}
Historical outcomes available: {outcome_count}
Top strategies by confidence: {top_strategies}

Task: {task}
""",
        tools=["query_outcomes", "update_calibration", "generate_recommendation"]
    ),
    
    "healthcare_domain": AgentConfig(
        role=AgentRole.DOMAIN_EXPERT,
        domain="clinical_trial",
        capabilities=[
            "analyze_enrollment_patterns",
            "recommend_criteria_adjustments",
            "learn_from_trial_outcomes"
        ],
        prompt_template="""
You are the Clinical Trial Domain Agent for CortexDBx. Your expertise:
- Enrollment velocity optimization
- Inclusion/exclusion criteria analysis
- Site performance evaluation

Context: {context}
Historical outcomes available: {outcome_count}
Top strategies by confidence: {top_strategies}

Task: {task}
""",
        tools=["query_outcomes", "update_calibration", "generate_recommendation"]
    ),
    
    # Additional domain agents follow same pattern...
}
```

### 5.3 Orchestrator Implementation

```python
# cortexdbx/agents/orchestrator.py

import asyncio
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor
import logging

logger = logging.getLogger(__name__)

class AgentOrchestrator:
    """
    Coordinates domain agents for parallel processing.
    """
    
    def __init__(self, max_workers: int = 6):
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.domain_agents: Dict[str, DomainAgent] = {}
    
    def register_domain_agent(self, domain: str, agent: 'DomainAgent') -> None:
        """Register a domain-specific agent."""
        self.domain_agents[domain] = agent
        logger.info(f"Registered agent for domain: {domain}")
    
    async def process_batch(self, signals: List[Dict]) -> Dict[str, Any]:
        """
        Process a batch of signals across domain agents in parallel.
        """
        # Group signals by domain
        by_domain = {}
        for signal in signals:
            domain = signal.get("domain", "unknown")
            if domain not in by_domain:
                by_domain[domain] = []
            by_domain[domain].append(signal)
        
        # Process each domain in parallel
        tasks = []
        for domain, domain_signals in by_domain.items():
            if domain in self.domain_agents:
                task = asyncio.create_task(
                    self._process_domain(domain, domain_signals)
                )
                tasks.append(task)
            else:
                logger.warning(f"No agent registered for domain: {domain}")
        
        # Wait for all domains to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Aggregate results
        aggregated = {
            "total_processed": sum(r.get("processed", 0) for r in results if isinstance(r, dict)),
            "total_outcomes": sum(r.get("outcomes", 0) for r in results if isinstance(r, dict)),
            "errors": [str(r) for r in results if isinstance(r, Exception)],
            "by_domain": {
                domain: results[i] 
                for i, domain in enumerate(by_domain.keys())
                if isinstance(results[i], dict)
            }
        }
        
        return aggregated
    
    async def _process_domain(self, domain: str, signals: List[Dict]) -> Dict:
        """Process signals for a single domain."""
        agent = self.domain_agents[domain]
        
        outcomes_created = 0
        recommendations_generated = 0
        
        for signal in signals:
            try:
                # Agent processes signal and creates outcome
                outcome = await agent.process_signal(signal)
                if outcome:
                    outcomes_created += 1
                
                # Agent checks if recommendation is warranted
                recommendation = await agent.check_recommendation(signal)
                if recommendation:
                    recommendations_generated += 1
                    
            except Exception as e:
                logger.error(f"Error processing signal in {domain}: {e}")
        
        return {
            "domain": domain,
            "processed": len(signals),
            "outcomes": outcomes_created,
            "recommendations": recommendations_generated
        }
    
    def run_calibration_sweep(self) -> Dict[str, Any]:
        """
        Run calibration update across all domains.
        """
        results = {}
        
        for domain, agent in self.domain_agents.items():
            try:
                calibration_result = agent.run_calibration()
                results[domain] = calibration_result
            except Exception as e:
                logger.error(f"Calibration failed for {domain}: {e}")
                results[domain] = {"error": str(e)}
        
        return results
    
    def generate_recommendations(self, min_confidence: float = 0.7) -> List[Dict]:
        """
        Generate recommendations across all domains.
        """
        all_recommendations = []
        
        for domain, agent in self.domain_agents.items():
            try:
                domain_recs = agent.generate_recommendations(min_confidence)
                all_recommendations.extend(domain_recs)
            except Exception as e:
                logger.error(f"Recommendation generation failed for {domain}: {e}")
        
        # Sort by confidence descending
        all_recommendations.sort(key=lambda x: x.get("confidence", 0), reverse=True)
        
        return all_recommendations


class DomainAgent:
    """
    Base class for domain-specific agents.
    """
    
    def __init__(self, domain: str, spark_session, catalog: str, schema: str):
        self.domain = domain
        self.spark = spark_session
        self.catalog = catalog
        self.schema = schema
        self.table_prefix = f"{catalog}.{schema}"
    
    async def process_signal(self, signal: Dict) -> Dict:
        """Process a single signal and create outcome."""
        raise NotImplementedError
    
    async def check_recommendation(self, context: Dict) -> Dict:
        """Check if recommendation is warranted for context."""
        raise NotImplementedError
    
    def run_calibration(self) -> Dict:
        """Run calibration update for this domain."""
        raise NotImplementedError
    
    def generate_recommendations(self, min_confidence: float) -> List[Dict]:
        """Generate recommendations above confidence threshold."""
        raise NotImplementedError
```

### 5.4 Databricks Job: Agent Team Execution

```python
# Notebook: 03_run_agent_team

# COMMAND ----------
# Initialize orchestrator
orchestrator = AgentOrchestrator(max_workers=6)

# Register domain agents
for domain in ["fraud_investigation", "clinical_trial", "maintenance", 
               "marketing_campaign", "security_incident", "supply_chain"]:
    agent = DomainAgent(
        domain=domain,
        spark_session=spark,
        catalog="cortex_catalog",
        schema="cortex_mvp"
    )
    orchestrator.register_domain_agent(domain, agent)

# COMMAND ----------
# Load signals to process (could be streaming or batch)
signals_df = spark.table("signals_raw").filter("processed = false").limit(10000)
signals = [row.asDict() for row in signals_df.collect()]

# COMMAND ----------
# Process in parallel via agent team
import asyncio

results = asyncio.run(orchestrator.process_batch(signals))
print(f"Processed {results['total_processed']} signals")
print(f"Created {results['total_outcomes']} outcomes")

# COMMAND ----------
# Run calibration sweep
calibration_results = orchestrator.run_calibration_sweep()
for domain, result in calibration_results.items():
    print(f"{domain}: {result}")

# COMMAND ----------
# Generate recommendations
recommendations = orchestrator.generate_recommendations(min_confidence=0.7)
print(f"Generated {len(recommendations)} recommendations")

# Write to recommendations table
recs_df = spark.createDataFrame(recommendations)
recs_df.write.mode("append").saveAsTable("recommendations")
```

---

## 6. Dashboard Application

### 6.1 Streamlit Dashboard

```python
# cortexdbx/dashboard/app.py

import streamlit as st
from pyspark.sql import SparkSession
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Page config
st.set_page_config(
    page_title="CortexDBx Intelligence Dashboard",
    page_icon="brain",
    layout="wide"
)

# Initialize Spark (for Databricks Apps)
@st.cache_resource
def get_spark():
    return SparkSession.builder.getOrCreate()

spark = get_spark()
CATALOG = "cortex_catalog"
SCHEMA = "cortex_mvp"

# Sidebar - Domain filter
st.sidebar.title("CortexDBx")
domains = ["All"] + [
    "fraud_investigation", "clinical_trial", "maintenance",
    "marketing_campaign", "security_incident", "supply_chain"
]
selected_domain = st.sidebar.selectbox("Domain", domains)

# Main content
st.title("CortexDBx Intelligence Dashboard")

# Metrics row
col1, col2, col3, col4 = st.columns(4)

# Query metrics
domain_filter = "" if selected_domain == "All" else f"WHERE s.domain = '{selected_domain}'"

total_outcomes = spark.sql(f"""
    SELECT COUNT(*) as count FROM {CATALOG}.{SCHEMA}.outcomes o
    JOIN {CATALOG}.{SCHEMA}.strategies s ON o.strategy_id = s.strategy_id
    {domain_filter}
""").collect()[0]["count"]

avg_confidence = spark.sql(f"""
    SELECT AVG(confidence) as avg FROM {CATALOG}.{SCHEMA}.context_strategy_edges e
    JOIN {CATALOG}.{SCHEMA}.strategies s ON e.strategy_id = s.strategy_id
    {domain_filter}
""").collect()[0]["avg"]

high_conf_count = spark.sql(f"""
    SELECT COUNT(*) as count FROM {CATALOG}.{SCHEMA}.context_strategy_edges e
    JOIN {CATALOG}.{SCHEMA}.strategies s ON e.strategy_id = s.strategy_id
    {domain_filter.replace('WHERE', 'WHERE confidence > 0.8 AND' if domain_filter else 'WHERE confidence > 0.8')}
""").collect()[0]["count"]

recent_recs = spark.sql(f"""
    SELECT COUNT(*) as count FROM {CATALOG}.{SCHEMA}.recommendations
    WHERE created_at > current_timestamp() - INTERVAL 24 HOURS
""").collect()[0]["count"]

with col1:
    st.metric("Total Outcomes", f"{total_outcomes:,}")
with col2:
    st.metric("Avg Confidence", f"{avg_confidence:.1%}" if avg_confidence else "N/A")
with col3:
    st.metric("High Confidence Strategies", high_conf_count)
with col4:
    st.metric("Recommendations (24h)", recent_recs)

# Strategy confidence chart
st.subheader("Strategy Confidence by Domain")

confidence_df = spark.sql(f"""
    SELECT 
        s.domain,
        s.name as strategy_name,
        e.confidence,
        e.success_count,
        e.failure_count
    FROM {CATALOG}.{SCHEMA}.context_strategy_edges e
    JOIN {CATALOG}.{SCHEMA}.strategies s ON e.strategy_id = s.strategy_id
    {domain_filter}
    ORDER BY e.confidence DESC
    LIMIT 50
""").toPandas()

if not confidence_df.empty:
    fig = px.bar(
        confidence_df, 
        x="strategy_name", 
        y="confidence",
        color="domain",
        title="Strategy Confidence Rankings"
    )
    fig.add_hline(y=0.8, line_dash="dash", line_color="green", 
                  annotation_text="High Confidence Threshold")
    fig.add_hline(y=0.3, line_dash="dash", line_color="red",
                  annotation_text="Warning Threshold")
    st.plotly_chart(fig, use_container_width=True)

# Top recommendations
st.subheader("Top Recommendations")

recs_df = spark.sql(f"""
    SELECT 
        r.recommendation_id,
        s.domain,
        s.name as strategy_name,
        r.confidence,
        r.evidence_summary,
        r.created_at
    FROM {CATALOG}.{SCHEMA}.recommendations r
    JOIN {CATALOG}.{SCHEMA}.strategies s ON r.strategy_id = s.strategy_id
    WHERE r.confidence > 0.7
    ORDER BY r.confidence DESC, r.created_at DESC
    LIMIT 20
""").toPandas()

if not recs_df.empty:
    st.dataframe(
        recs_df,
        column_config={
            "confidence": st.column_config.ProgressColumn(
                "Confidence",
                min_value=0,
                max_value=1,
                format="%.0%%"
            )
        },
        use_container_width=True
    )

# Calibration health
st.subheader("Calibration Health")

col1, col2 = st.columns(2)

with col1:
    # Confidence distribution
    dist_df = spark.sql(f"""
        SELECT 
            CASE 
                WHEN confidence >= 0.8 THEN 'High (80%+)'
                WHEN confidence >= 0.5 THEN 'Medium (50-80%)'
                ELSE 'Low (<50%)'
            END as bucket,
            COUNT(*) as count
        FROM {CATALOG}.{SCHEMA}.context_strategy_edges
        GROUP BY 1
    """).toPandas()
    
    if not dist_df.empty:
        fig = px.pie(dist_df, values="count", names="bucket",
                     title="Confidence Distribution")
        st.plotly_chart(fig, use_container_width=True)

with col2:
    # Outcomes over time
    time_df = spark.sql(f"""
        SELECT 
            DATE(created_at) as date,
            result,
            COUNT(*) as count
        FROM {CATALOG}.{SCHEMA}.outcomes
        WHERE created_at > current_timestamp() - INTERVAL 30 DAYS
        GROUP BY 1, 2
        ORDER BY 1
    """).toPandas()
    
    if not time_df.empty:
        fig = px.area(time_df, x="date", y="count", color="result",
                      title="Outcomes Over Time (30 Days)")
        st.plotly_chart(fig, use_container_width=True)

# Domain deep-dive
st.subheader("Domain Analysis")

domain_stats = spark.sql(f"""
    SELECT 
        s.domain,
        COUNT(DISTINCT e.context_id) as unique_contexts,
        COUNT(DISTINCT e.strategy_id) as strategies_used,
        AVG(e.confidence) as avg_confidence,
        SUM(e.success_count) as total_successes,
        SUM(e.failure_count) as total_failures
    FROM {CATALOG}.{SCHEMA}.context_strategy_edges e
    JOIN {CATALOG}.{SCHEMA}.strategies s ON e.strategy_id = s.strategy_id
    GROUP BY s.domain
""").toPandas()

if not domain_stats.empty:
    domain_stats["success_rate"] = (
        domain_stats["total_successes"] / 
        (domain_stats["total_successes"] + domain_stats["total_failures"])
    )
    st.dataframe(
        domain_stats,
        column_config={
            "avg_confidence": st.column_config.ProgressColumn(
                "Avg Confidence", min_value=0, max_value=1, format="%.0%%"
            ),
            "success_rate": st.column_config.ProgressColumn(
                "Success Rate", min_value=0, max_value=1, format="%.0%%"
            )
        },
        use_container_width=True
    )
```

---

## 7. Python SDK

### 7.1 SDK Implementation

```python
# cortexdbx/sdk/client.py

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import json
import hashlib
from datetime import datetime
import uuid

@dataclass
class CortexDBxConfig:
    catalog: str = "cortex_catalog"
    schema: str = "cortex_mvp"
    
class CortexDBxClient:
    """
    Python SDK for CortexDBx.
    
    Usage:
        from cortexdbx import CortexDBxClient
        
        cortex = CortexDBxClient()
        
        # Log an outcome
        cortex.log_outcome(
            context={"alert_type": "fraud", "amount": "high"},
            strategy="escalate_to_analyst",
            result="SUCCESS",
            evidence={"alert_id": "ALT-12345"}
        )
        
        # Get recommendations
        recs = cortex.recommend(
            context={"alert_type": "fraud", "amount": "medium"}
        )
    """
    
    def __init__(self, config: CortexDBxConfig = None, spark_session=None):
        self.config = config or CortexDBxConfig()
        self.spark = spark_session or self._get_spark()
        self.table_prefix = f"{self.config.catalog}.{self.config.schema}"
    
    def _get_spark(self):
        """Get or create Spark session."""
        from pyspark.sql import SparkSession
        return SparkSession.builder.getOrCreate()
    
    def _fingerprint_context(self, context: Dict) -> str:
        """Create deterministic fingerprint for context."""
        normalized = json.dumps(sorted(context.items()))
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]
    
    def log_outcome(
        self,
        context: Dict[str, Any],
        strategy: str,
        result: str,
        evidence: Optional[Dict] = None,
        notes: Optional[str] = None
    ) -> str:
        """
        Log an outcome to CortexDBx.
        
        Args:
            context: Dictionary of context factors
            strategy: Name or ID of strategy used
            result: 'SUCCESS', 'FAILURE', or 'PARTIAL'
            evidence: Optional evidence linking to source data
            notes: Optional human notes
            
        Returns:
            outcome_id: ID of created outcome
        """
        context_hash = self._fingerprint_context(context)
        outcome_id = str(uuid.uuid4())
        
        # Ensure context exists
        context_id = self._ensure_context(context, context_hash)
        
        # Ensure strategy exists
        strategy_id = self._ensure_strategy(strategy)
        
        # Insert outcome
        outcome_data = {
            "outcome_id": outcome_id,
            "context_id": context_id,
            "strategy_id": strategy_id,
            "result": result.upper(),
            "evidence": json.dumps(evidence or {}),
            "notes": notes,
            "actor": self._get_current_user(),
            "created_at": datetime.now().isoformat()
        }
        
        df = self.spark.createDataFrame([outcome_data])
        df.write.mode("append").saveAsTable(f"{self.table_prefix}.outcomes")
        
        return outcome_id
    
    def recommend(
        self,
        context: Dict[str, Any],
        min_confidence: float = 0.5,
        limit: int = 5
    ) -> List[Dict]:
        """
        Get recommendations for a context.
        
        Args:
            context: Dictionary of context factors
            min_confidence: Minimum confidence threshold
            limit: Maximum recommendations to return
            
        Returns:
            List of recommendations with confidence and evidence
        """
        context_hash = self._fingerprint_context(context)
        
        # Find similar contexts and their best strategies
        query = f"""
            SELECT 
                s.strategy_id,
                s.name as strategy_name,
                s.description,
                e.confidence,
                e.success_count,
                e.failure_count
            FROM {self.table_prefix}.context_strategy_edges e
            JOIN {self.table_prefix}.contexts c ON e.context_id = c.context_id
            JOIN {self.table_prefix}.strategies s ON e.strategy_id = s.strategy_id
            WHERE c.context_hash = '{context_hash}'
              AND e.confidence >= {min_confidence}
            ORDER BY e.confidence DESC
            LIMIT {limit}
        """
        
        results = self.spark.sql(query).collect()
        
        recommendations = []
        for row in results:
            recommendations.append({
                "strategy_id": row["strategy_id"],
                "strategy_name": row["strategy_name"],
                "description": row["description"],
                "confidence": row["confidence"],
                "evidence_count": row["success_count"] + row["failure_count"],
                "explanation": (
                    f"{row['confidence']:.0%} confidence based on "
                    f"{row['success_count']} successes and {row['failure_count']} failures"
                )
            })
        
        return recommendations
    
    def get_confidence(
        self,
        context: Dict[str, Any],
        strategy: str
    ) -> tuple:
        """
        Get confidence for a specific strategy in a context.
        
        Returns:
            (confidence, explanation)
        """
        context_hash = self._fingerprint_context(context)
        
        query = f"""
            SELECT 
                e.confidence,
                e.success_count,
                e.failure_count
            FROM {self.table_prefix}.context_strategy_edges e
            JOIN {self.table_prefix}.contexts c ON e.context_id = c.context_id
            JOIN {self.table_prefix}.strategies s ON e.strategy_id = s.strategy_id
            WHERE c.context_hash = '{context_hash}'
              AND s.name = '{strategy}'
        """
        
        results = self.spark.sql(query).collect()
        
        if not results:
            return 0.5, "No historical data for this context/strategy"
        
        row = results[0]
        return row["confidence"], (
            f"{row['confidence']:.0%} confidence based on "
            f"{row['success_count']} successes and {row['failure_count']} failures"
        )
    
    def _ensure_context(self, context: Dict, context_hash: str) -> str:
        """Ensure context exists, create if not."""
        # Check if exists
        existing = self.spark.sql(f"""
            SELECT context_id FROM {self.table_prefix}.contexts
            WHERE context_hash = '{context_hash}'
        """).collect()
        
        if existing:
            return existing[0]["context_id"]
        
        # Create new
        context_id = f"ctx_{context_hash}"
        context_data = {
            "context_id": context_id,
            "context_hash": context_hash,
            "domain": context.get("domain", "unknown"),
            "factors": json.dumps([{"key": k, "value": str(v)} for k, v in context.items()]),
            "first_seen": datetime.now().isoformat(),
            "last_seen": datetime.now().isoformat()
        }
        
        df = self.spark.createDataFrame([context_data])
        df.write.mode("append").saveAsTable(f"{self.table_prefix}.contexts")
        
        return context_id
    
    def _ensure_strategy(self, strategy: str) -> str:
        """Ensure strategy exists, create if not."""
        # Check if exists (by name or ID)
        existing = self.spark.sql(f"""
            SELECT strategy_id FROM {self.table_prefix}.strategies
            WHERE name = '{strategy}' OR strategy_id = '{strategy}'
        """).collect()
        
        if existing:
            return existing[0]["strategy_id"]
        
        # Create new
        strategy_id = f"strat_{hashlib.sha256(strategy.encode()).hexdigest()[:8]}"
        strategy_data = {
            "strategy_id": strategy_id,
            "name": strategy,
            "description": None,
            "domain": "unknown",
            "category": "user_defined",
            "created_at": datetime.now().isoformat()
        }
        
        df = self.spark.createDataFrame([strategy_data])
        df.write.mode("append").saveAsTable(f"{self.table_prefix}.strategies")
        
        return strategy_id
    
    def _get_current_user(self) -> str:
        """Get current user identity."""
        try:
            return self.spark.sql("SELECT current_user()").collect()[0][0]
        except:
            return "unknown"


# Convenience function for notebook usage
def log_outcome(context, strategy, result, evidence=None, notes=None):
    """Quick outcome logging for notebooks."""
    client = CortexDBxClient()
    return client.log_outcome(context, strategy, result, evidence, notes)

def recommend(context, min_confidence=0.5):
    """Quick recommendation for notebooks."""
    client = CortexDBxClient()
    return client.recommend(context, min_confidence)
```

---

## 8. Deployment Checklist

### 8.1 Infrastructure Setup

```bash
# 1. Create catalog and schema
databricks unity-catalog catalogs create cortex_catalog
databricks unity-catalog schemas create cortex_catalog.cortex_mvp

# 2. Deploy table schemas (run DDL notebook)
databricks jobs create --json @jobs/create_tables_job.json

# 3. Deploy synthetic data generator
databricks jobs create --json @jobs/generate_synthetic_data_job.json

# 4. Deploy calibration job (scheduled hourly)
databricks jobs create --json @jobs/calibration_job.json

# 5. Deploy agent team job
databricks jobs create --json @jobs/agent_team_job.json

# 6. Deploy dashboard app
databricks apps deploy cortexdbx-dashboard --source-path ./dashboard
```

### 8.2 Validation Steps

| Step | Command | Expected Result |
|------|---------|-----------------|
| 1. Tables exist | `SHOW TABLES IN cortex_catalog.cortex_mvp` | 7 tables listed |
| 2. Synthetic data | `SELECT COUNT(*) FROM outcomes` | 60,000+ rows |
| 3. Calibration | `SELECT COUNT(*) FROM context_strategy_edges` | 1000+ edges |
| 4. Recommendations | `SELECT COUNT(*) FROM recommendations WHERE confidence > 0.7` | 100+ recs |
| 5. Dashboard | Navigate to app URL | Dashboard loads with data |

### 8.3 Performance Benchmarks

| Operation | Target | Measurement |
|-----------|--------|-------------|
| Outcome ingestion | 1000/sec | `time spark.sql("INSERT INTO outcomes SELECT...")` |
| Calibration job | < 5 min | Job run duration |
| Dashboard load | < 3 sec | Browser network timing |
| SDK `recommend()` | < 500ms | Python timing |

---

## 9. Next Steps After MVP

### 9.1 Production Hardening

- [ ] Add row-level security for multi-tenant
- [ ] Implement webhook alerting
- [ ] Add comprehensive logging and monitoring
- [ ] Set up CI/CD for job deployments

### 9.2 Agent Tool Integration

- [ ] Deploy Model Serving endpoint
- [ ] Integrate with Mosaic AI agents
- [ ] Add Genie plugin when API available

### 9.3 Real Data Migration

- [ ] Connect to actual system tables
- [ ] Backfill historical query outcomes
- [ ] Validate calibration against real success rates

---

## Appendix A: Job Configurations

### Calibration Job

```json
{
  "name": "cortexdbx-calibration",
  "schedule": {
    "quartz_cron_expression": "0 0 * * * ?",
    "timezone_id": "UTC"
  },
  "tasks": [
    {
      "task_key": "run_calibration",
      "notebook_task": {
        "notebook_path": "/Repos/cortexdbx/notebooks/02_run_calibration"
      },
      "new_cluster": {
        "spark_version": "14.3.x-scala2.12",
        "node_type_id": "i3.xlarge",
        "num_workers": 2
      }
    }
  ]
}
```

### Agent Team Job

```json
{
  "name": "cortexdbx-agent-team",
  "tasks": [
    {
      "task_key": "run_agents",
      "notebook_task": {
        "notebook_path": "/Repos/cortexdbx/notebooks/03_run_agent_team",
        "base_parameters": {
          "max_signals": "10000"
        }
      },
      "new_cluster": {
        "spark_version": "14.3.x-scala2.12",
        "node_type_id": "i3.2xlarge",
        "num_workers": 4
      }
    }
  ]
}
```

---

## Appendix B: Ground Truth Validation

To validate calibration accuracy:

```python
# Compare learned confidence vs. synthetic ground truth

from cortexdbx.synthetic.generator import SyntheticDataGenerator

# Get ground truth
generator = SyntheticDataGenerator("fraud_investigation")
ground_truth = generator.get_ground_truth()

# Get learned confidence
learned = spark.sql("""
    SELECT strategy_id, confidence
    FROM cortex_catalog.cortex_mvp.context_strategy_edges
""").toPandas()

# Calculate calibration error
errors = []
for _, row in learned.iterrows():
    if row["strategy_id"] in ground_truth:
        true_rate = ground_truth[row["strategy_id"]]
        learned_conf = row["confidence"]
        errors.append(abs(true_rate - learned_conf))

mean_error = sum(errors) / len(errors)
print(f"Mean calibration error: {mean_error:.2%}")
# Target: < 10% mean error after 10K outcomes per strategy
```
