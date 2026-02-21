#!/usr/bin/env python3
"""
Monitor batch job overnight and apply results when complete.

This script:
1. Checks batch status every 30 minutes
2. Downloads results when complete
3. Applies code changes to files
4. Runs tests to verify
5. Creates summary report
"""

import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

# Add cortex to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from batch.batch_api_client import BatchAPIClient


def log(message: str):
    """Log message with timestamp."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")


def extract_code_blocks(response_text: str) -> list[tuple[str, str]]:
    """
    Extract code blocks from Claude's response.

    Returns:
        List of (language, code) tuples
    """
    pattern = r"```(\w+)?\n(.*?)```"
    matches = re.findall(pattern, response_text, re.DOTALL)
    return [(lang or "python", code.strip()) for lang, code in matches]


def apply_code_changes(results: list, output_dir: Path):
    """
    Apply code changes from batch results.

    Args:
        results: List of BatchResult objects
        output_dir: Directory to write files
    """
    log("Applying code changes...")

    file_mapping = {
        "layer3_metric_tracker": "intelligence/monitoring/metric_tracker.py",
        "layer3_trend_analyzer": "intelligence/monitoring/trend_analyzer.py",
        "layer3_alert_generator": "intelligence/monitoring/alert_generator.py",
        "layer3_inject_integration": ".claude/hooks/inject_context.py",
        "layer4_file_selector": "intelligence/recommendations/file_selector.py",
        "layer4_smart_generator": "intelligence/recommendations/smart_generator.py",
        "layer4_engine_integration": "recommendation_engine.py",
    }

    created_files = []
    modified_files = []

    for result in results:
        if result.status != "succeeded":
            log(f"  ⚠️  Skipping {result.custom_id} (status: {result.status})")
            continue

        # Get response content
        # result.result is a Pydantic model, not a dict
        if hasattr(result.result, "message"):
            content = result.result.message.content
        else:
            log(f"  ⚠️  No message in {result.custom_id}")
            continue

        if not content:
            log(f"  ⚠️  No content in {result.custom_id}")
            continue

        # Extract text from content blocks
        response_text = ""
        for block in content:
            if hasattr(block, "type") and block.type == "text":
                response_text += block.text

        # Extract code blocks
        code_blocks = extract_code_blocks(response_text)

        if not code_blocks:
            log(f"  ⚠️  No code blocks in {result.custom_id}")
            # Save full response for manual review
            debug_file = output_dir / f"{result.custom_id}_response.txt"
            debug_file.write_text(response_text)
            log(f"     Saved response to {debug_file}")
            continue

        # Get target file path
        target_file = file_mapping.get(result.custom_id)

        if not target_file:
            # For docs/CLI tasks, extract from response or use default
            if result.custom_id == "layer3_4_cli_docs":
                # This task creates multiple files, extract them from response
                log(f"  📝 Processing multi-file task: {result.custom_id}")
                # Save full response for manual processing
                doc_file = output_dir / f"{result.custom_id}_docs.md"
                doc_file.write_text(response_text)
                log(f"     Saved documentation to {doc_file}")
                continue
            else:
                log(f"  ⚠️  Unknown task: {result.custom_id}")
                continue

        # Write the largest code block to target file
        largest_block = max(code_blocks, key=lambda x: len(x[1]))
        code = largest_block[1]

        # Determine full path
        if target_file.startswith(".claude"):
            full_path = Path(os.environ.get("CORTEX_ROOT_DIR", str(Path.cwd()))) / target_file
        else:
            full_path = Path("~/projects/cortex") / target_file

        # Create parent directory if needed
        full_path.parent.mkdir(parents=True, exist_ok=True)

        # Check if file exists
        existed = full_path.exists()

        # Write file
        full_path.write_text(code)

        if existed:
            modified_files.append(str(full_path.relative_to(Path(os.environ.get("CORTEX_ROOT_DIR", str(Path.cwd()))))))
            log(f"  ✅ Modified: {full_path.relative_to(Path(os.environ.get("CORTEX_ROOT_DIR", str(Path.cwd()))))}")
        else:
            created_files.append(str(full_path.relative_to(Path(os.environ.get("CORTEX_ROOT_DIR", str(Path.cwd()))))))
            log(f"  ✅ Created: {full_path.relative_to(Path(os.environ.get("CORTEX_ROOT_DIR", str(Path.cwd()))))}")

    log(f"Applied changes: {len(created_files)} created, {len(modified_files)} modified")

    return created_files, modified_files


def run_tests(test_path: str = "intelligence/") -> bool:
    """
    Run tests to verify implementation.

    Returns:
        True if tests pass, False otherwise
    """
    log("Running tests...")

    import subprocess

    try:
        result = subprocess.run(
            ["pytest", test_path, "-v", "--tb=short"],
            cwd="~/projects/cortex",
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode == 0:
            log("  ✅ All tests passed")
            return True
        else:
            log("  ⚠️  Some tests failed")
            log(f"     Output: {result.stdout[-500:]}")  # Last 500 chars
            return False

    except subprocess.TimeoutExpired:
        log("  ⚠️  Tests timed out")
        return False
    except Exception as e:
        log(f"  ⚠️  Error running tests: {e}")
        return False


def create_summary_report(
    batch_id: str,
    results: list,
    created_files: list,
    modified_files: list,
    output_dir: Path,
):
    """Create summary report of batch results."""

    report = f"""# Layers 3-4 Implementation - Batch Results

**Batch ID**: {batch_id}
**Completed**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## Summary

- Total tasks: {len(results)}
- Successful: {sum(1 for r in results if r.status == "succeeded")}
- Failed: {sum(1 for r in results if r.status != "succeeded")}
- Files created: {len(created_files)}
- Files modified: {len(modified_files)}

## Files Created

{chr(10).join(f"- {f}" for f in created_files) if created_files else "None"}

## Files Modified

{chr(10).join(f"- {f}" for f in modified_files) if modified_files else "None"}

## Task Results

"""

    for result in results:
        status_icon = "✅" if result.status == "succeeded" else "❌"
        report += f"### {status_icon} {result.custom_id}\n\n"
        report += f"**Status**: {result.status}\n\n"

        if result.status != "succeeded":
            # Show error if available
            if hasattr(result.result, "error"):
                error = result.result.error
                error_msg = error.message if hasattr(error, "message") else str(error)
                report += f"**Error**: {error_msg}\n\n"

    report += """
## Next Steps

1. **Review Files**: Check the generated code for quality
2. **Run Tests**: `pytest intelligence/ -v`
3. **Test Integration**: Try commands like `cortex alerts`, `cortex next`
4. **Update Documentation**: Review and finalize docs
5. **Commit Changes**: `git add . && git commit -m "feat: implement Layers 3-4"`

## Testing Checklist

- [ ] Layer 3: Metric tracking works (`cortex track`)
- [ ] Layer 3: Alerts generated (`cortex alerts`)
- [ ] Layer 3: Alerts shown in context (`echo "test" | .claude/hooks/inject_context.py`)
- [ ] Layer 4: Smart recommendations include files (`cortex next`)
- [ ] Layer 4: Recommendations include steps
- [ ] Integration: All layers work together
- [ ] Performance: Context injection < 500ms

"""

    report_path = output_dir / "IMPLEMENTATION_REPORT.md"
    report_path.write_text(report)

    log(f"Summary report saved to: {report_path}")

    return report_path


def monitor_batch(batch_id: str, check_interval: int = 1800):
    """
    Monitor batch job overnight.

    Args:
        batch_id: Batch ID to monitor
        check_interval: Seconds between checks (default: 30 minutes)
    """
    log("=" * 60)
    log("CORTEX LAYERS 3-4 - OVERNIGHT BATCH MONITORING")
    log("=" * 60)
    log(f"Batch ID: {batch_id}")
    log(f"Check interval: {check_interval // 60} minutes")
    print()

    # Initialize client
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        log("❌ Error: ANTHROPIC_API_KEY not set")
        sys.exit(1)

    client = BatchAPIClient(api_key=api_key)

    # Output directory
    output_dir = Path.home() / ".cortex" / "batches" / batch_id
    output_dir.mkdir(parents=True, exist_ok=True)

    log(f"Output directory: {output_dir}")
    print()

    # Monitor loop
    check_count = 0
    while True:
        check_count += 1
        log(f"Check #{check_count}: Retrieving batch status...")

        try:
            # Check status
            status = client.get_batch_status(batch_id)

            log(f"  Status: {status['status']}")
            log(f"  Processing: {status.get('request_counts', {}).get('processing', 0)}")
            log(f"  Completed: {status.get('request_counts', {}).get('succeeded', 0)}")
            log(f"  Failed: {status.get('request_counts', {}).get('errored', 0)}")

            # Save status
            status_file = output_dir / f"status_{check_count}.json"
            status_file.write_text(json.dumps(status, indent=2))

            # Check if complete
            if status["status"] in ["ended", "completed"]:
                print()
                log("🎉 Batch complete! Downloading results...")

                # Download results
                results = client._retrieve_batch_results(batch_id)
                log(f"  Downloaded {len(results)} results")

                # Save raw results
                results_file = output_dir / "results.json"
                results_data = [
                    {
                        "custom_id": r.custom_id,
                        "status": r.status,
                        "result": (
                            r.result.model_dump()
                            if hasattr(r.result, "model_dump")
                            else (r.result.dict() if hasattr(r.result, "dict") else r.result)
                        ),
                    }
                    for r in results
                ]
                results_file.write_text(json.dumps(results_data, indent=2))
                log(f"  Saved to: {results_file}")
                print()

                # Apply code changes
                created_files, modified_files = apply_code_changes(results, output_dir)
                print()

                # Run tests
                tests_passed = run_tests()
                print()

                # Create summary report
                report_path = create_summary_report(
                    batch_id, results, created_files, modified_files, output_dir
                )
                print()

                # Final summary
                log("=" * 60)
                log("BATCH PROCESSING COMPLETE")
                log("=" * 60)
                log(f"✅ Results downloaded: {len(results)} tasks")
                log(f"✅ Files created: {len(created_files)}")
                log(f"✅ Files modified: {len(modified_files)}")
                log(
                    f"{'✅' if tests_passed else '⚠️ '} Tests: {'passed' if tests_passed else 'some failures'}"
                )
                log(f"✅ Report: {report_path}")
                print()
                log("Next: Review the implementation report and test the features!")
                print()

                break

            elif status["status"] in ["failed", "expired", "canceled", "canceling"]:
                log(f"❌ Batch {status['status']}")
                log("   Check the Anthropic API dashboard for details")
                break

            else:
                # Still processing, wait and check again
                log(f"  ⏳ Still processing... Next check in {check_interval // 60} minutes")
                print()
                time.sleep(check_interval)

        except KeyboardInterrupt:
            print()
            log("⚠️  Monitoring interrupted by user")
            log(f"   Batch {batch_id} is still running")
            log(f"   Resume monitoring with: python batch/monitor_batch_overnight.py {batch_id}")
            break

        except Exception as e:
            log(f"❌ Error checking batch status: {e}")
            import traceback

            traceback.print_exc()
            print()
            log(f"  Retrying in {check_interval // 60} minutes...")
            print()
            time.sleep(check_interval)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python monitor_batch_overnight.py <batch_id>")
        sys.exit(1)

    batch_id = sys.argv[1]
    monitor_batch(batch_id)
