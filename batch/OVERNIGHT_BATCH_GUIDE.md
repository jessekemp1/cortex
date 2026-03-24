# Overnight Batch Implementation - Layers 3-4

## Overview

This guide helps you submit Layers 3-4 implementation as an overnight batch job using the Anthropic Batch API.

**Benefits:**
- Runs while you sleep (no manual work)
- Uses Opus for high-quality implementation
- Automatic code application and testing
- 50% cost reduction (batch pricing)
- Full monitoring and reporting

**Timeline:**
- Submit batch: 5 minutes
- Processing: 12-24 hours (overnight)
- Results: Automatic code application
- Review: 30 minutes (morning)

---

## Quick Start

### Step 1: Generate Batch Specification

```bash
cd /path/to/cortex

# Generate batch spec (creates layer3_4_batch.json)
python batch/layer3_4_batch_spec.py
```

**Output:**
```
✅ Saved batch spec to cortex/batch/layer3_4_batch.json
   Total requests: 8
   Layer 3 requests: 4
   Layer 4 requests: 4
```

### Step 2: Submit Batch

```bash
# Set API key (if not already set)
export ANTHROPIC_API_KEY='your-key-here'

# Submit batch
python batch/submit_layer3_4_batch.py
```

**Interactive prompts:**
```
📊 Batch breakdown:
   Layer 3 (Warning System): 4 tasks
     - layer3_metric_tracker
     - layer3_trend_analyzer
     - layer3_alert_generator
     - layer3_inject_integration

   Layer 4 (Smart Recommendations): 4 tasks
     - layer4_file_selector
     - layer4_smart_generator
     - layer4_engine_integration
     - layer3_4_cli_docs

💰 Estimated cost:
   8 requests × ~$1.35 = ~$10.80
   (Assumes Opus with max tokens; actual cost likely lower)

⏱️  Expected completion: 24 hours (batch API SLA)

Submit batch? (yes/no):
```

Type `yes` and press Enter.

**Output:**
```
✅ Batch submitted successfully!
   Batch ID: batch_abc123xyz

📁 Batch info saved to:
   ~/.cortex/batches/batch_abc123xyz.json
```

### Step 3: Monitor Overnight (Recommended)

```bash
# Start overnight monitoring (runs in background)
python batch/monitor_batch_overnight.py batch_abc123xyz
```

**What it does:**
- Checks status every 30 minutes
- Downloads results when complete
- Applies code changes automatically
- Runs tests to verify
- Creates implementation report

**Terminal output:**
```
[2025-12-22 23:00:00] CORTEX LAYERS 3-4 - OVERNIGHT BATCH MONITORING
[2025-12-22 23:00:00] Batch ID: batch_abc123xyz
[2025-12-22 23:00:00] Check interval: 30 minutes
[2025-12-22 23:00:00] Output directory: ~/.cortex/batches/batch_abc123xyz

[2025-12-22 23:00:00] Check #1: Retrieving batch status...
[2025-12-22 23:00:00]   Status: in_progress
[2025-12-22 23:00:00]   Processing: 8
[2025-12-22 23:00:00]   Completed: 0
[2025-12-22 23:00:00]   ⏳ Still processing... Next check in 30 minutes
```

**Leave it running overnight.** It will:
1. Check every 30 minutes
2. Download results when complete
3. Apply code changes
4. Run tests
5. Create summary report

---

## Alternative: Manual Monitoring

If you don't want to leave the script running, check status manually:

```bash
# Quick status check
python batch/check_batch_status.py batch_abc123xyz
```

**Output:**
```
BATCH STATUS: batch_abc123xyz
Status: in_progress
Created: 2025-12-22T23:00:00Z

Request Counts:
  Total: 8
  Processing: 5
  Succeeded: 3
  Errored: 0

Progress: [███████████░░░░░░░░░] 37.5%

⏳ Batch is still processing...
   Expected completion: 24 hours from submission (API SLA)
```

When complete, run the monitor script once to download and apply results:

```bash
python batch/monitor_batch_overnight.py batch_abc123xyz
```

---

## Morning Review

When you wake up, check the results:

### 1. Check Summary Report

```bash
cat ~/.cortex/batches/batch_abc123xyz/IMPLEMENTATION_REPORT.md
```

**Report includes:**
- Files created/modified
- Task success/failure status
- Test results
- Next steps checklist

### 2. Review Generated Code

```bash
# View created files
ls -la cortex/intelligence/monitoring/
ls -la cortex/intelligence/recommendations/

# Check a file
cat cortex/intelligence/monitoring/metric_tracker.py
```

### 3. Run Tests

```bash
cd /path/to/cortex

# Run all intelligence tests
pytest intelligence/ -v

# Run specific layer tests
pytest intelligence/monitoring/ -v
pytest intelligence/recommendations/ -v
```

### 4. Test Features

```bash
# Test Layer 3: Metric tracking
python -m cortex.cli track

# Test Layer 3: Alerts
python -m cortex.cli alerts

# Test Layer 4: Smart recommendations
python -m cortex.cli next --limit=3

# Test context injection
cd /path/to/cortex
echo "test prompt" | .claude/hooks/inject_context.py
```

### 5. Commit Changes

If everything looks good:

```bash
git add intelligence/monitoring/ intelligence/recommendations/ .claude/hooks/inject_context.py recommendation_engine.py
git commit -m "feat: implement Layers 3-4 (Warning System + Smart Recommendations)"
```

---

## Batch Tasks Breakdown

### Layer 3: Warning System

| Task ID | Description | Lines | Model | Est Time |
|---------|-------------|-------|-------|----------|
| layer3_metric_tracker | SQLite-based metric tracking | ~300 | Opus | 2h |
| layer3_trend_analyzer | Statistical trend analysis | ~250 | Opus | 2h |
| layer3_alert_generator | Alert rules and formatting | ~200 | Opus | 1.5h |
| layer3_inject_integration | Integrate with inject_context.py | ~50 | Sonnet | 30min |

**Total Layer 3**: ~800 lines, ~6 hours equivalent work

### Layer 4: Smart Recommendations

| Task ID | Description | Lines | Model | Est Time |
|---------|-------------|-------|-------|----------|
| layer4_file_selector | File selection algorithms | ~200 | Opus | 1.5h |
| layer4_smart_generator | Smart recommendation generator | ~400 | Opus | 3h |
| layer4_engine_integration | Integrate with recommendation_engine.py | ~100 | Sonnet | 1h |
| layer3_4_cli_docs | CLI commands and documentation | N/A | Sonnet | 1h |

**Total Layer 4**: ~700 lines, ~6.5 hours equivalent work

**Grand Total**: ~1500 lines, ~12.5 hours equivalent work

---

## Cost Breakdown

### Batch Pricing (50% discount)

**Per Request:**
- Input tokens: ~10,000 × $7.50/M = $0.075
- Output tokens: ~16,000 × $37.50/M = $0.60
- **Total per request**: ~$0.675

**Total Batch:**
- 8 requests × $0.675 = **~$5.40**

**vs. Real-Time Pricing:**
- 8 requests × $1.35 = ~$10.80
- **Savings: $5.40 (50%)**

**vs. Manual Implementation:**
- 12.5 hours × $100/hr = $1,250
- **Savings: $1,244.60 (99.6%)**

---

## Troubleshooting

### Batch Stuck in Processing

If batch is still processing after 24 hours:

```bash
# Check status
python batch/check_batch_status.py batch_abc123xyz

# If status shows 'ended' but monitor didn't catch it:
python batch/monitor_batch_overnight.py batch_abc123xyz
```

### API Key Issues

```bash
# Verify API key is set
echo $ANTHROPIC_API_KEY

# Set API key
export ANTHROPIC_API_KEY='your-key-here'

# Add to ~/.zshrc for persistence
echo 'export ANTHROPIC_API_KEY="your-key-here"' >> ~/.zshrc
```

### Code Application Errors

If automatic code application fails:

1. Check the response files in `~/.cortex/batches/batch_abc123xyz/`
2. Manually extract code blocks from `*_response.txt` files
3. Apply code manually to target files

### Test Failures

If tests fail after applying code:

1. Review test output in the implementation report
2. Check generated code for syntax errors
3. Run specific failing tests with: `pytest path/to/test.py -v`
4. Fix issues manually or re-run specific batch tasks

---

## Advanced: Resubmit Individual Tasks

If a specific task failed or needs adjustment:

```python
# Create a new batch with just one task
from batch.layer3_4_batch_spec import create_layer3_requests
from batch.batch_api_client import BatchAPIClient

# Get just the metric_tracker task
requests = create_layer3_requests()
metric_tracker = [r for r in requests if r.custom_id == "layer3_metric_tracker"]

# Submit
client = BatchAPIClient()
batch_id = client.submit_batch(metric_tracker, description="Retry metric_tracker")
print(f"Resubmitted: {batch_id}")
```

---

## FAQ

**Q: How long does batch processing take?**
A: Typically 12-24 hours. Anthropic's SLA is 24 hours.

**Q: Can I cancel a batch?**
A: Yes, but not through this script yet. Use the Anthropic API dashboard.

**Q: What if I lose the batch ID?**
A: Check `~/.cortex/batches/*.json` for submitted batches.

**Q: Can I modify the tasks?**
A: Yes! Edit `batch/layer3_4_batch_spec.py` and regenerate.

**Q: What model is used?**
A: Opus 4.5 for implementation tasks, Sonnet 4.5 for integration/docs.

**Q: Can I run this during the day?**
A: Yes, but it will still take 12-24 hours to process.

---

## Next Steps After Completion

1. **Test thoroughly** - Run all test suites
2. **Review code quality** - Check generated code meets standards
3. **Update docs** - Finalize documentation
4. **Test features** - Try `cortex alerts`, `cortex next`, etc.
5. **Gather feedback** - Use features and iterate

**Expected result:** Fully functional Layers 3-4 with minimal manual work!
