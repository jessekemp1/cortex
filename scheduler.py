import os
#!/usr/bin/env python3
"""
Scheduler - Cron-style scheduling for daily briefings

Supports:
- Cron-style schedule expressions
- One-time scheduling
- Recurring daily/weekly briefings
- Email delivery (optional)
"""

import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

# Import briefing module
sys.path.insert(0, str(Path(__file__).parent))
from briefing import format_briefing, format_briefing_json, generate_daily_briefing


@dataclass
class ScheduleConfig:
    """Schedule configuration."""

    cron_expression: str
    output_format: str = "text"
    output_file: Optional[str] = None
    email_to: Optional[str] = None
    enabled: bool = True


class BriefingScheduler:
    """Schedule daily briefings using cron or other scheduling mechanisms."""

    def __init__(self, root_dir: Optional[Path] = None):
        if root_dir is None:
            root_dir = Path(os.environ.get("CORTEX_ROOT_DIR", str(Path.cwd())))
        self.root_dir = root_dir

        # Config file location
        self.config_dir = root_dir / "cortex"
        self.config_file = self.config_dir / "briefing_schedule.json"

    def schedule_briefing(
        self,
        cron_expression: str = "0 8 * * *",
        output_format: str = "text",
        output_file: Optional[str] = None,
        email_to: Optional[str] = None,
    ) -> bool:
        """
        Schedule a daily briefing.

        Args:
            cron_expression: Cron-style schedule (default: "0 8 * * *" = daily at 8am)
            output_format: Output format ("text" or "json")
            output_file: Optional file to write output to
            email_to: Optional email address to send briefing to

        Returns:
            True if scheduled successfully
        """
        config = ScheduleConfig(
            cron_expression=cron_expression,
            output_format=output_format,
            output_file=output_file,
            email_to=email_to,
            enabled=True,
        )

        # Save configuration
        self._save_config(config)

        # Try to install cron job
        if self._is_cron_available():
            return self._install_cron_job(config)
        else:
            print("Warning: cron not available. Configuration saved but not scheduled.")
            print("You can manually run: cortex briefing")
            return False

    def run_briefing(self, config: Optional[ScheduleConfig] = None) -> bool:
        """
        Run briefing according to configuration.

        Args:
            config: Schedule configuration (loads from file if None)

        Returns:
            True if briefing ran successfully
        """
        if config is None:
            config = self._load_config()
            if config is None:
                print("No schedule configuration found.")
                return False

        try:
            # Generate briefing
            briefing = generate_daily_briefing(self.root_dir)

            # Format output
            if config.output_format == "json":
                output = format_briefing_json(briefing)
            else:
                output = format_briefing(briefing, use_color=False)

            # Write to file if configured
            if config.output_file:
                output_path = Path(config.output_file)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text(output)
                print(f"Briefing written to: {output_path}")

            # Send email if configured
            if config.email_to:
                self._send_email(config.email_to, output, briefing.generated_at)

            # Always print to stdout
            print(output)

            return True

        except Exception as e:
            print(f"Error running briefing: {e}", file=sys.stderr)
            return False

    def unschedule_briefing(self) -> bool:
        """
        Remove scheduled briefing.

        Returns:
            True if unscheduled successfully
        """
        # Remove cron job if exists
        if self._is_cron_available():
            self._remove_cron_job()

        # Remove config file
        if self.config_file.exists():
            self.config_file.unlink()

        print("Briefing schedule removed.")
        return True

    def get_schedule(self) -> Optional[ScheduleConfig]:
        """
        Get current schedule configuration.

        Returns:
            ScheduleConfig or None if not scheduled
        """
        return self._load_config()

    def _save_config(self, config: ScheduleConfig):
        """Save configuration to file."""
        self.config_dir.mkdir(parents=True, exist_ok=True)

        config_data = {
            "cron_expression": config.cron_expression,
            "output_format": config.output_format,
            "output_file": config.output_file,
            "email_to": config.email_to,
            "enabled": config.enabled,
        }

        self.config_file.write_text(json.dumps(config_data, indent=2))

    def _load_config(self) -> Optional[ScheduleConfig]:
        """Load configuration from file."""
        if not self.config_file.exists():
            return None

        try:
            config_data = json.loads(self.config_file.read_text())
            return ScheduleConfig(**config_data)
        except Exception as e:
            print(f"Warning: Could not load config: {e}", file=sys.stderr)
            return None

    def _is_cron_available(self) -> bool:
        """Check if cron is available on the system."""
        try:
            result = subprocess.run(["which", "crontab"], capture_output=True, timeout=2)
            return result.returncode == 0
        except Exception:
            return False

    def _install_cron_job(self, config: ScheduleConfig) -> bool:
        """
        Install cron job for briefing.

        Args:
            config: Schedule configuration

        Returns:
            True if installed successfully
        """
        try:
            # Build cron command
            cortex_cli = Path(__file__).parent / "cli.py"
            cmd = f"cd {self.root_dir} && python3 {cortex_cli} briefing"

            if config.output_format == "json":
                cmd += " --format=json"

            if config.output_file:
                cmd += f" > {config.output_file}"

            cron_line = f"{config.cron_expression} {cmd}"

            # Get current crontab
            result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)

            current_crontab = result.stdout if result.returncode == 0 else ""

            # Remove existing cortex briefing lines
            lines = [line for line in current_crontab.split("\n") if "cortex briefing" not in line]

            # Add new line
            lines.append("# Cortex Daily Briefing")
            lines.append(cron_line)

            # Install new crontab
            new_crontab = "\n".join(lines)
            process = subprocess.Popen(
                ["crontab", "-"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            stdout, stderr = process.communicate(input=new_crontab)

            if process.returncode != 0:
                print(f"Warning: Could not install cron job: {stderr}", file=sys.stderr)
                return False

            print(f"Briefing scheduled: {config.cron_expression}")
            return True

        except Exception as e:
            print(f"Warning: Could not install cron job: {e}", file=sys.stderr)
            return False

    def _remove_cron_job(self) -> bool:
        """
        Remove cron job for briefing.

        Returns:
            True if removed successfully
        """
        try:
            # Get current crontab
            result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)

            if result.returncode != 0:
                return True  # No crontab exists

            current_crontab = result.stdout

            # Remove cortex briefing lines
            lines = [
                line
                for line in current_crontab.split("\n")
                if "cortex briefing" not in line and "Cortex Daily Briefing" not in line
            ]

            # Install new crontab
            new_crontab = "\n".join(lines)
            process = subprocess.Popen(
                ["crontab", "-"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            stdout, stderr = process.communicate(input=new_crontab)

            return process.returncode == 0

        except Exception as e:
            print(f"Warning: Could not remove cron job: {e}", file=sys.stderr)
            return False

    def _send_email(self, to_address: str, content: str, date: datetime):
        """
        Send briefing via email.

        Args:
            to_address: Email address to send to
            content: Briefing content
            date: Briefing date
        """
        try:
            import smtplib
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText

            # Create message
            msg = MIMEMultipart()
            msg["From"] = "cortex@localhost"
            msg["To"] = to_address
            msg["Subject"] = f"Daily Briefing - {date.strftime('%B %d, %Y')}"

            # Add content
            msg.attach(MIMEText(content, "plain"))

            # Send via local sendmail or SMTP
            # Note: This requires sendmail or SMTP configuration
            server = smtplib.SMTP("localhost")
            server.send_message(msg)
            server.quit()

            print(f"Briefing sent to: {to_address}")

        except Exception as e:
            print(f"Warning: Could not send email: {e}", file=sys.stderr)


def parse_cron_expression(expression: str) -> dict:
    """
    Parse cron expression and return human-readable description.

    Args:
        expression: Cron expression (e.g., "0 8 * * *")

    Returns:
        Dictionary with parsed components
    """
    parts = expression.split()

    if len(parts) != 5:
        raise ValueError("Invalid cron expression. Expected 5 fields.")

    minute, hour, day, month, weekday = parts

    # Common patterns
    if expression == "0 8 * * *":
        description = "Daily at 8:00 AM"
    elif expression == "0 9 * * 1":
        description = "Every Monday at 9:00 AM"
    elif expression == "0 17 * * 5":
        description = "Every Friday at 5:00 PM"
    elif expression.startswith("0 ") and expression.endswith(" * * *"):
        description = f"Daily at {hour}:00"
    else:
        description = f"Custom: {expression}"

    return {
        "minute": minute,
        "hour": hour,
        "day": day,
        "month": month,
        "weekday": weekday,
        "description": description,
    }


if __name__ == "__main__":
    # Test scheduler
    import argparse

    parser = argparse.ArgumentParser(description="Cortex Briefing Scheduler")
    parser.add_argument(
        "--schedule",
        type=str,
        help="Schedule briefing with cron expression (e.g., '0 8 * * *')",
    )
    parser.add_argument("--unschedule", action="store_true", help="Remove scheduled briefing")
    parser.add_argument("--run", action="store_true", help="Run briefing now")
    parser.add_argument("--status", action="store_true", help="Show schedule status")
    parser.add_argument("--output-file", type=str, help="File to write briefing to")

    args = parser.parse_args()

    scheduler = BriefingScheduler()

    if args.schedule:
        scheduler.schedule_briefing(cron_expression=args.schedule, output_file=args.output_file)
    elif args.unschedule:
        scheduler.unschedule_briefing()
    elif args.run:
        scheduler.run_briefing()
    elif args.status:
        config = scheduler.get_schedule()
        if config:
            parsed = parse_cron_expression(config.cron_expression)
            print(f"Schedule: {parsed['description']}")
            print(f"Cron: {config.cron_expression}")
            print(f"Format: {config.output_format}")
            if config.output_file:
                print(f"Output: {config.output_file}")
            if config.email_to:
                print(f"Email: {config.email_to}")
            print(f"Enabled: {config.enabled}")
        else:
            print("No schedule configured.")
    else:
        parser.print_help()
