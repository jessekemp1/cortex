# Cortex Enhancement Plan - Complete Implementation

**Created:** 2025-12-24
**Status:** Planning
**Approach:** Batch API + Hybrid ML for time estimates, Full integration suite

---

## Overview

Enhance Cortex Intelligence Stack with:
1. **Machine Learning** - Intelligent time estimates using Batch API + local ML
2. **Notifications** - Slack webhooks + Email alerts
3. **GitHub Actions** - Automated metric tracking on commits
4. **VS Code Extension** - IDE integration
5. **Visualization Dashboard** - Web UI (deferred to Phase 2)

**Total Estimated Time:** 40-60 hours (8-12 days)

---

## Phase 1: ML Time Estimates (12-16 hours)

### Priority: HIGH
### Approach: Hybrid (Batch API → Traditional ML)

### Part 1.1: Batch API Historical Analysis (4-6 hours)

**Goal:** Use Batch API to analyze git history and generate training data

**Tasks:**
1. **Create batch request builder** (`cortex/ml/batch_analyzer.py`)
   - Scan git history for completed work
   - Extract: commit message, files changed, time between commits
   - Build batch requests: "Estimate time for: {commit_msg}, files: {files}, actual_time: {time}"
   - Target: 500-1000 historical commits

2. **Submit to Batch API**
   - Use existing `batch/batch_api_client.py`
   - Submit batch job with all historical commits
   - Wait 24h for results
   - Cost estimate: ~$50 for 1000 commits @ 50% savings

3. **Process batch results** (`cortex/ml/batch_processor.py`)
   - Parse Batch API responses
   - Extract: estimated_time, reasoning, confidence
   - Create training dataset: `ml/data/time_estimates_training.jsonl`
   - Format: `{task_description, features, estimated_minutes, reasoning}`

**Deliverables:**
- `ml/batch_analyzer.py` - Batch request builder
- `ml/batch_processor.py` - Result processor
- `ml/data/time_estimates_training.jsonl` - Training dataset
- `ml/scripts/run_batch_analysis.py` - One-click batch submission

---

### Part 1.2: Feature Engineering (2-3 hours)

**Goal:** Extract features from tasks for ML model

**Tasks:**
1. **Create feature extractor** (`cortex/ml/feature_extractor.py`)
   - Text features: word count, keyword presence (refactor, migrate, add, fix)
   - Code features: estimated file count, lines changed
   - Context features: project complexity score, tech stack
   - Historical features: similar task average time

2. **Feature pipeline**
   - TfidfVectorizer for task descriptions
   - StandardScaler for numeric features
   - Combine into feature matrix

**Deliverables:**
- `ml/feature_extractor.py` - Feature extraction
- `ml/feature_pipeline.pkl` - Serialized pipeline

---

### Part 1.3: ML Model Training (2-3 hours)

**Goal:** Train local ML model using Batch API generated data

**Tasks:**
1. **Model selection and training** (`cortex/ml/time_estimator.py`)
   - Try: RandomForestRegressor, GradientBoostingRegressor, XGBRegressor
   - Cross-validation with 80/20 split
   - Hyperparameter tuning with GridSearchCV
   - Target: MAE < 15 minutes, R² > 0.7

2. **Model evaluation**
   - Test on holdout set
   - Compare vs heuristic baseline
   - Generate evaluation report

3. **Model serialization**
   - Save best model to `ml/models/time_estimator.pkl`
   - Save feature pipeline
   - Version tracking

**Deliverables:**
- `ml/time_estimator.py` - ML model trainer
- `ml/models/time_estimator.pkl` - Trained model
- `ml/evaluation_report.json` - Performance metrics
- `ml/scripts/train_model.py` - Training script

---

### Part 1.4: Integration with Planner (2-3 hours)

**Goal:** Use ML model for plan step time estimates

**Tasks:**
1. **Update Planner class** (`intelligence/planning/planner.py`)
   - Add `use_ml_estimates=True` parameter
   - Load ML model on initialization
   - Use model predictions instead of heuristics
   - Fall back to heuristics if model fails

2. **Confidence scoring**
   - Return confidence score with each estimate
   - Flag low-confidence estimates
   - Suggest manual review for uncertain estimates

3. **Continuous learning**
   - Log actual vs predicted times
   - Periodic retraining trigger (weekly)
   - Feedback loop to Batch API for refinement

**Deliverables:**
- Updated `planner.py` with ML integration
- `ml/continuous_learner.py` - Feedback loop
- Tests for ML-based planning

---

### Part 1.5: Batch API Refresh Pipeline (2 hours)

**Goal:** Weekly refresh of ML model with new data

**Tasks:**
1. **Automated refresh script** (`ml/scripts/weekly_refresh.sh`)
   - Scan for new commits since last run
   - Submit to Batch API
   - Retrain model when results arrive
   - Deploy new model

2. **Cron job setup**
   - Weekly execution
   - Slack notification on completion
   - Error handling and retry

**Deliverables:**
- `ml/scripts/weekly_refresh.sh` - Automated refresh
- Cron job configuration
- Documentation

---

## Phase 2: Notifications (8-10 hours)

### Priority: HIGH

### Part 2.1: Slack Integration (3-4 hours)

**Tasks:**
1. **Slack webhook client** (`notifications/slack_client.py`)
   - Send messages to webhook URL
   - Format alerts with rich blocks
   - Support attachments and emoji
   - Rate limiting and retry logic

2. **Alert formatter** (`notifications/formatters.py`)
   - Format Layer 3 alerts for Slack
   - Color coding: 🔴 Critical, 🟡 Warning, 🟢 Info
   - Include project, metric, trend, recommendation
   - Add action buttons (if using Slack app)

3. **Configuration**
   - Add `SLACK_WEBHOOK_URL` to config
   - Per-project webhook settings
   - Alert filtering (only send critical+warning)

4. **Integration points**
   - AlertGenerator → Slack when critical alert
   - PlanExecutor → Slack when plan completed
   - Weekly summary of metrics and recommendations

**Deliverables:**
- `notifications/slack_client.py`
- `notifications/formatters.py`
- Configuration in `config.py`
- Tests

---

### Part 2.2: Email Integration (3-4 hours)

**Tasks:**
1. **Email client** (`notifications/email_client.py`)
   - SMTP connection with TLS
   - HTML email templates
   - Attachment support
   - Queue and batch sending

2. **Email templates** (`notifications/templates/`)
   - `critical_alert.html` - Critical alert email
   - `weekly_summary.html` - Weekly metrics digest
   - `plan_complete.html` - Plan completion notification
   - Use Jinja2 for templating

3. **Configuration**
   - SMTP settings (server, port, credentials)
   - Email recipients per project
   - Notification preferences

4. **Daily/weekly digests**
   - Aggregate metrics and alerts
   - Send summary email
   - Cron job setup

**Deliverables:**
- `notifications/email_client.py`
- Email templates
- Configuration
- Digest scheduler

---

### Part 2.3: Unified Notification System (2 hours)

**Tasks:**
1. **Notification router** (`notifications/router.py`)
   - Route alerts to appropriate channels
   - Support multiple destinations (Slack + Email)
   - Priority-based routing
   - Deduplication

2. **Integration with Layer 3**
   - AlertGenerator calls NotificationRouter
   - Configurable per alert severity
   - Async sending (don't block)

**Deliverables:**
- `notifications/router.py`
- Updated AlertGenerator
- Tests

---

## Phase 3: GitHub Actions Integration (6-8 hours)

### Priority: MEDIUM

### Part 3.1: Metric Collector Action (3-4 hours)

**Tasks:**
1. **GitHub Action workflow** (`.github/workflows/cortex-metrics.yml`)
   - Trigger: on push, pull_request
   - Run pytest with coverage
   - Run linters (pylint, mypy)
   - Collect metrics

2. **Metrics submission script** (`scripts/submit_metrics_to_cortex.py`)
   - Read coverage report
   - Read linter output
   - Call Cortex API to track metrics
   - POST to MetricTracker

3. **Cortex API endpoint**
   - Add REST endpoint to bridge.py
   - POST /api/metrics/track
   - Authentication with API key
   - Rate limiting

**Deliverables:**
- `.github/workflows/cortex-metrics.yml`
- `scripts/submit_metrics_to_cortex.py`
- API endpoint in bridge.py
- Documentation

---

### Part 3.2: PR Recommendations (3-4 hours)

**Tasks:**
1. **PR comment action** (`.github/workflows/cortex-pr-check.yml`)
   - Trigger: on pull_request
   - Run Cortex analysis on PR
   - Generate recommendations
   - Post as PR comment

2. **PR analyzer** (`github/pr_analyzer.py`)
   - Fetch PR diff
   - Analyze changed files
   - Get recommendations from Layer 4
   - Format as markdown comment

3. **GitHub API integration**
   - Use GitHub API to post comments
   - Update status checks
   - Link to Cortex dashboard

**Deliverables:**
- `.github/workflows/cortex-pr-check.yml`
- `github/pr_analyzer.py`
- GitHub API integration
- Example PR with recommendations

---

## Phase 4: VS Code Extension (10-14 hours)

### Priority: MEDIUM

### Part 4.1: Extension Setup (2-3 hours)

**Tasks:**
1. **Create extension project**
   - Use `yo code` generator
   - TypeScript + WebView
   - Configure build and packaging

2. **Project structure**
   ```
   cortex-vscode/
   ├── src/
   │   ├── extension.ts
   │   ├── cortexClient.ts
   │   ├── views/
   │   └── commands/
   ├── media/
   ├── package.json
   └── README.md
   ```

**Deliverables:**
- Extension project scaffolding
- Build configuration

---

### Part 4.2: Cortex Client (3-4 hours)

**Tasks:**
1. **API client** (`src/cortexClient.ts`)
   - Connect to Cortex bridge.py API
   - Get recommendations for current project
   - Get active alerts
   - Get plans and steps

2. **Configuration**
   - VS Code settings: cortex.apiUrl, cortex.apiKey
   - Auto-detect project root
   - Connection status indicator

**Deliverables:**
- `cortexClient.ts` - API client
- Configuration schema
- Connection tests

---

### Part 4.3: UI Views (3-4 hours)

**Tasks:**
1. **Recommendations sidebar** (`src/views/recommendationsView.ts`)
   - TreeView of recommendations
   - Color-coded by priority
   - Click to see details
   - "Start Plan" button

2. **Alerts panel** (`src/views/alertsView.ts`)
   - Show active alerts
   - Critical/Warning indicators
   - Trend information

3. **Plans view** (`src/views/plansView.ts`)
   - List active plans
   - Show progress
   - Mark steps complete
   - Start next step

**Deliverables:**
- Recommendations view
- Alerts view
- Plans view
- CSS styling

---

### Part 4.4: Commands & Integration (2-3 hours)

**Tasks:**
1. **Commands**
   - `cortex.refresh` - Refresh recommendations
   - `cortex.createPlan` - Create plan from recommendations
   - `cortex.completeStep` - Mark step complete
   - `cortex.viewMetrics` - Open metrics dashboard

2. **Status bar**
   - Show alert count
   - Click to open panel
   - Health indicator

3. **Code actions**
   - Right-click file → "Get Cortex recommendation"
   - Quick fix suggestions from Layer 4

**Deliverables:**
- Command palette integration
- Status bar widget
- Code actions
- Keyboard shortcuts

---

## Phase 5: Visualization Dashboard (10-12 hours) - DEFERRED

Will implement after core features are complete.

---

## Implementation Order

### Sprint 1: ML Foundation (Week 1)
1. Day 1-2: Batch API historical analysis
2. Day 3: Feature engineering
3. Day 4: Model training
4. Day 5: Integration with Planner

### Sprint 2: Notifications (Week 2)
1. Day 1-2: Slack integration
2. Day 3: Email integration
3. Day 4: Unified notification system

### Sprint 3: GitHub & VS Code (Week 2-3)
1. Day 5: GitHub Actions - Metrics
2. Day 6: GitHub Actions - PR checks
3. Day 7-8: VS Code extension setup & client
4. Day 9-10: VS Code UI views and commands

---

## Dependencies & Prerequisites

### Required:
- Anthropic API key with Batch API access
- Slack workspace with webhook permissions
- SMTP server for email (or SendGrid account)
- GitHub repository with Actions enabled
- VS Code extension development setup

### Optional:
- XGBoost installed (`pip install xgboost`)
- SendGrid API (alternative to SMTP)
- Slack App (for interactive buttons)

---

## Success Criteria

### Phase 1 (ML):
- ✓ ML model achieves MAE < 15 minutes on test set
- ✓ Planner uses ML estimates by default
- ✓ Weekly refresh pipeline working
- ✓ Batch API integration tested with real data

### Phase 2 (Notifications):
- ✓ Critical alerts sent to Slack within 1 minute
- ✓ Weekly email digest delivered every Monday
- ✓ Plan completion notifications working
- ✓ Zero notification failures (with retry)

### Phase 3 (GitHub):
- ✓ Metrics automatically tracked on every commit
- ✓ PR recommendations posted within 2 minutes
- ✓ Status checks passing/failing correctly
- ✓ No false positives in recommendations

### Phase 4 (VS Code):
- ✓ Extension loads in < 2 seconds
- ✓ Recommendations refresh in < 1 second
- ✓ All views functional
- ✓ Published to VS Code Marketplace

---

## Risk Mitigation

### Risk 1: Batch API results not useful
- **Mitigation:** Start with small batch (50 commits) to validate quality
- **Fallback:** Use traditional ML only if Batch API fails

### Risk 2: ML model accuracy poor
- **Mitigation:** Keep heuristic fallback, show confidence scores
- **Fallback:** Gradual rollout, allow users to disable ML

### Risk 3: Notification spam
- **Mitigation:** Smart filtering, rate limiting, digest mode
- **Fallback:** User preferences to disable/customize

### Risk 4: VS Code extension complexity
- **Mitigation:** Start with read-only views, add interactions later
- **Fallback:** Web dashboard alternative

---

## Cost Estimate

### Batch API:
- Initial analysis: 1000 commits × $0.015/request × 50% = **$7.50**
- Weekly refresh: 50 commits/week × $0.015 × 50% × 52 weeks = **$19.50/year**

### Infrastructure:
- Email: $0 (use existing SMTP) or SendGrid free tier
- Slack: $0 (webhooks are free)
- GitHub Actions: Free for public repos, $0.008/minute for private
- VS Code: $0 (free to publish)

**Total First Year:** ~$30 for Batch API

---

## Next Steps

1. **Review and approve** this plan
2. **Set up Batch API access** - Verify API key has batch permissions
3. **Create Cortex project tracking** - Use Layer 5 to track this plan!
4. **Start Sprint 1** - Begin with Batch API historical analysis

---

**Ready to start implementation?** Let's use Cortex to manage this plan! 🚀
