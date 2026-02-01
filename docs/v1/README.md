# Cortex v1 Documentation
## Canonical Reference for Implementation

**Last Updated:** 2026-01-29

---

## Overview

This directory contains the v1 documentation for Cortex and CortexDBx, rebuilt from a critical assessment of prior papers and research.

```
docs/v1/
├── README.md              # This file - index and assessment summary
├── CORTEX_CORE.md         # General Cortex: vision, architecture, roadmap
└── CORTEXDBX_MVP.md       # CortexDBx: full MVP implementation guide
```

---

## Document Summary

### CORTEX_CORE.md

**Purpose:** Canonical reference for the Cortex Intelligence Layer pattern.

**Contents:**
- What Cortex is (and isn't)
- Core concepts: Outcome, Context, Strategy, Confidence
- Three-engine architecture: Observer, Orientation Core, Broker
- Learning loop implementation
- Deployment variants: Personal, Team, Enterprise
- Current state and technical debt
- Iteration roadmap
- Design principles

**Use when:** Understanding the overall Cortex vision, evaluating architecture decisions, onboarding new contributors.

### CORTEXDBX_MVP.md

**Purpose:** Complete implementation guide for CortexDBx on Databricks.

**Contents:**
- MVP scope: 6 validated use cases
- Delta table schema (7 tables, full DDL)
- Synthetic data generator (Python, domain-specific configs)
- Calibration engine (Beta-Binomial, validation metrics)
- Agent team architecture (orchestrator + 6 domain agents)
- Dashboard application (Streamlit/Databricks Apps)
- Python SDK (`log_outcome()`, `recommend()`, `get_confidence()`)
- Deployment checklist and validation steps
- Job configurations

**Use when:** Building CortexDBx, generating test data, deploying to Databricks.

---

## Assessment Summary

### What Was Assessed

| Document | Location | Status |
|----------|----------|--------|
| cortex-dbx-prd.md | ~/Dev/Docs/papers/ | Superseded |
| cortex-manifesto-v3.md | ~/Dev/Docs/papers/ | Superseded |
| cortex-dbx-use-cases.md | ~/Dev/Docs/papers/ | Superseded |
| cortex-databricks-enterprise.md | ~/Dev/Docs/papers/ | Superseded |
| cortex-architecture-v2.md | ~/Dev/Docs/papers/ | Superseded |
| cortex-vs-palantir-assessment.md | ~/Dev/Docs/papers/ | Superseded |
| cortex-for-ai-operators.md | ~/Dev/Docs/papers/ | Incorporated |
| docs/cortexdbx/aPRD.md | cortex repo | Referenced |
| docs/cortexdbx/TECHNICAL_PAPER.md | cortex repo | Referenced |
| docs/cortexdbx/AUDIT.md | cortex repo | Key input |

### Critical Issues Found and Resolved

| Issue | Resolution |
|-------|------------|
| **Inconsistent terminology** | Standardized on Observer/Orientation Core/Broker |
| **No concrete data model** | Full DDL for 7 Delta tables |
| **Vaporware use cases (50)** | Narrowed to 6 validated, buildable cases |
| **Marketing over engineering** | Technical specs with code, not rhetoric |
| **Unrealistic NFRs (200ms)** | Per-surface SLOs with realistic targets |
| **SQLite/JSONL at scale** | Delta Lake as primary store |
| **No implementation path** | Complete notebooks, jobs, SDK |
| **Timeline-based roadmap** | Phase-based with exit criteria |

### What's New in v1

1. **Synthetic Data Generator** - Complete Python implementation for all 6 domains with ground truth for calibration validation

2. **Agent Team Architecture** - Orchestrator + domain agents for parallel processing at scale

3. **Python SDK** - Production-ready `CortexDBxClient` with `log_outcome()`, `recommend()`, `get_confidence()`

4. **Calibration Engine** - Beta-Binomial model with Brier score validation

5. **Dashboard Application** - Streamlit code for Databricks Apps deployment

6. **Deployment Checklist** - Step-by-step infrastructure setup and validation

---

## Use Case Selection

From the original 50 use cases, 6 were selected for MVP based on:
- Clear signal sources available in Databricks
- Measurable outcomes (success/failure)
- Realistic synthetic data generation
- Cross-industry relevance

| # | Domain | Use Case | Why Selected |
|---|--------|----------|--------------|
| 1 | Financial Services | Fraud Investigation Prioritization | High volume, clear ROI |
| 2 | Healthcare | Clinical Trial Enrollment | Regulatory credibility |
| 3 | Manufacturing | Maintenance Decisions | Tangible cost savings |
| 4 | Retail | Campaign Effectiveness | CMO-friendly metrics |
| 5 | Security | Incident Response | CISO-friendly, clear playbooks |
| 6 | Supply Chain | Routing Decisions | COO-friendly, measurable |

---

## Implementation Priority

### Phase 1: Foundation (Build First)

1. Delta table schema deployment
2. Synthetic data generator
3. Calibration job
4. Python SDK

**Validation:** 10K+ outcomes, calibration error < 10%

### Phase 2: Intelligence (Build Second)

1. Agent team implementation
2. Recommendation generation
3. Dashboard application

**Validation:** Recommendations generated, dashboard displays data

### Phase 3: Integration (Build Third)

1. Real system table ingestion
2. Webhook alerting
3. Mosaic AI agent tool

**Validation:** Real outcomes tracked, alerts firing, agents using tool

---

## Relationship to Other Documentation

### Supersedes

- All papers in `~/Dev/Docs/papers/cortex-*`
- `docs/cortexdbx/aPRD.md` (v1 is more complete)
- `docs/cortexdbx/TECHNICAL_PAPER.md` (v1 has implementation)

### References

- `docs/cortexdbx/AUDIT.md` - Key input for issue identification
- `docs/cortexdbx/spec/*` - Detailed specs still valid, aligned with v1

### Complements

- `START_HERE.md` - Quick start for existing local Cortex
- `DAILY_QUICK_START.md` - Daily workflow for local use
- `docs/user_guide/*` - End-user documentation

---

## Quick Start

### For Local Cortex Development

```bash
cd /Users/jesse.kemp/Dev/cortex
source venv/bin/activate
./daily_scan.sh
```

### For CortexDBx Implementation

1. Read `CORTEXDBX_MVP.md` Section 2 (Architecture)
2. Deploy schema (Section 2.2)
3. Run synthetic generator (Section 3)
4. Deploy calibration job (Section 4)
5. Validate with checklist (Section 8)

### For Understanding the Vision

1. Read `CORTEX_CORE.md` Section 1-2 (What and Why)
2. Read Section 4 (Learning Loop)
3. Read Section 8 (Design Principles)

---

## File Locations

```
/Users/jesse.kemp/Dev/
├── cortex/                          # Main repo
│   ├── docs/
│   │   ├── v1/                      # THIS DIRECTORY
│   │   │   ├── README.md
│   │   │   ├── CORTEX_CORE.md
│   │   │   └── CORTEXDBX_MVP.md
│   │   ├── cortexdbx/               # Detailed specs
│   │   └── user_guide/              # End-user docs
│   ├── engines/                     # Core implementation
│   └── ...
└── Docs/papers/                     # Original papers (superseded)
```

---

## Glossary

| Term | Definition |
|------|------------|
| **Cortex** | Intelligence Layer pattern - tracks outcomes, calibrates confidence |
| **CortexDBx** | Cortex implementation for Databricks |
| **Outcome** | Structured record: context + strategy + result |
| **Context** | Fingerprint of operational environment |
| **Strategy** | Named approach to a problem class |
| **Confidence** | Bayesian P(success), calibrated from outcomes |
| **Observer** | Component that ingests signals |
| **Orientation Core** | Component that stores and calibrates |
| **Broker** | Component that delivers recommendations |
| **Agent Team** | Orchestrator + domain agents for parallel processing |

---

## Contact

Questions about this documentation: Review the source papers audit in `docs/cortexdbx/AUDIT.md` for rationale behind decisions.
