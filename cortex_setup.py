#!/usr/bin/env python3
"""
Cortex Setup Wizard — Interactive onboarding for new users.

Walks a new user through providing the required inputs for
optimal Cortex value, auto-detecting what it can and asking
for what it can't.

Setup Stages:
    1. AUTO-DETECT  → Git projects, Python version, existing configs
    2. ESSENTIALS   → API key, subscription tier
    3. PROJECT      → Primary project identification, goals
    4. PREFERENCES  → Model preferences, budget constraints
    5. VERIFY       → Run health check, show first intelligence query
    6. DEMONSTRATE  → Show what Cortex learned from setup alone

Usage:
    python -m cortex_setup          # Interactive wizard
    cortex setup                    # Via CLI (if installed)
    cortex setup --non-interactive  # Accept defaults, prompt for essentials only
"""

import json
import os
import re
import sqlite3
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class SetupConfig:
    """Configuration collected during setup."""

    # Auto-detected
    git_projects: List[Dict[str, str]] = field(default_factory=list)
    python_version: str = ""
    platform: str = ""
    cortex_dir: str = ""
    existing_config: bool = False

    # Essentials
    anthropic_api_key: str = ""
    subscription_tier: str = "free"  # free, pro, team, enterprise
    monthly_token_allowance: int = 0
    monthly_cost_usd: float = 0.0
    billing_reset_day: int = 1

    # Project
    primary_project: str = ""
    project_goals: List[str] = field(default_factory=list)
    project_description: str = ""

    # Preferences
    preferred_model: str = "sonnet"  # default model for most tasks
    budget_limit_usd: float = 0.0  # 0 = no limit
    batch_enabled: bool = True
    learning_enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": "anthropic",
            "subscription": {
                "tier": self.subscription_tier,
                "monthly_token_allowance": self.monthly_token_allowance,
                "monthly_cost_usd": self.monthly_cost_usd,
                "billing_reset_day": self.billing_reset_day,
            },
            "project": {
                "primary": self.primary_project,
                "goals": self.project_goals,
                "description": self.project_description,
            },
            "preferences": {
                "default_model": self.preferred_model,
                "budget_limit_usd": self.budget_limit_usd,
                "batch_enabled": self.batch_enabled,
                "learning_enabled": self.learning_enabled,
            },
            "detected": {
                "git_projects": self.git_projects,
                "python_version": self.python_version,
                "platform": self.platform,
            },
        }


# ── Subscription tier data ──

SUBSCRIPTION_TIERS = {
    "free": {
        "monthly_token_allowance": 500_000,
        "monthly_cost_usd": 0.0,
        "description": "Free tier — 500K tokens/month",
        "includes_batch": False,
        "rate_limit_rpm": 5,
    },
    "pro": {
        "monthly_token_allowance": 5_000_000,
        "monthly_cost_usd": 20.0,
        "description": "Pro — 5M tokens/month, batch API included",
        "includes_batch": True,
        "rate_limit_rpm": 50,
    },
    "team": {
        "monthly_token_allowance": 25_000_000,
        "monthly_cost_usd": 100.0,
        "description": "Team — 25M tokens/month, priority access",
        "includes_batch": True,
        "rate_limit_rpm": 200,
    },
    "enterprise": {
        "monthly_token_allowance": 100_000_000,
        "monthly_cost_usd": 500.0,
        "description": "Enterprise — 100M tokens/month, dedicated capacity",
        "includes_batch": True,
        "rate_limit_rpm": 1000,
    },
    "custom": {
        "monthly_token_allowance": 0,
        "monthly_cost_usd": 0.0,
        "description": "Custom — specify your own limits",
        "includes_batch": True,
        "rate_limit_rpm": 100,
    },
}


class CortexSetupWizard:
    """Interactive setup wizard for new Cortex users."""

    def __init__(self, non_interactive: bool = False):
        self.non_interactive = non_interactive
        self.config = SetupConfig()
        self.cortex_home = Path.home() / ".cortex"

    def run(self) -> SetupConfig:
        """Run the full setup wizard."""
        self._print_welcome()
        self._stage_autodetect()
        self._stage_essentials()
        self._stage_project()
        self._stage_preferences()
        self._stage_apply()
        self._stage_verify()
        self._stage_demonstrate()
        return self.config

    # ──────────────────────────────────────────────
    # Stage 0: Welcome
    # ──────────────────────────────────────────────

    def _print_welcome(self):
        print()
        print("=" * 60)
        print("  CORTEX SETUP WIZARD")
        print("  Persistent Intelligence for LLM Agents")
        print("=" * 60)
        print()
        print("  This wizard configures Cortex to work with your")
        print("  projects and subscription. It takes about 2 minutes.")
        print()
        print("  Cortex will:")
        print("  1. Auto-detect your projects and environment")
        print("  2. Configure your API subscription for optimal utilization")
        print("  3. Set up learning loops that compound over time")
        print("  4. Demonstrate intelligence with your real project data")
        print()

    # ──────────────────────────────────────────────
    # Stage 1: Auto-detect
    # ──────────────────────────────────────────────

    def _stage_autodetect(self):
        print("--- Stage 1/6: Auto-Detect ---")
        print()

        # Detect platform
        self.config.platform = sys.platform
        self.config.python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        print(f"  Platform:   {self.config.platform}")
        print(f"  Python:     {self.config.python_version}")

        # Detect Cortex directory
        cortex_dir = os.environ.get("CORTEX_ROOT_DIR", str(Path.cwd()))
        self.config.cortex_dir = cortex_dir
        print(f"  Working dir: {cortex_dir}")

        # Detect existing config
        config_path = self.cortex_home / "config.yaml"
        self.config.existing_config = config_path.exists()
        if self.config.existing_config:
            print(f"  Config:     Found existing config at {config_path}")
        else:
            print(f"  Config:     No existing config (will create)")

        # Detect git projects
        self.config.git_projects = self._detect_git_projects(cortex_dir)
        if self.config.git_projects:
            print(f"  Projects:   Found {len(self.config.git_projects)} git project(s):")
            for proj in self.config.git_projects[:5]:
                print(f"              - {proj['name']} ({proj['branch']})")
            if len(self.config.git_projects) > 5:
                print(f"              ... and {len(self.config.git_projects) - 5} more")
        else:
            print("  Projects:   No git projects detected in working directory")

        # Detect all API providers
        providers = {
            "ANTHROPIC_API_KEY": "Anthropic (Opus, Sonnet, Haiku)",
            "GROQ_API_KEY": "Groq (fast classification)",
            "OPENAI_API_KEY": "OpenAI (GPT models)",
            "XAI_API_KEY": "xAI (Grok, long context)",
            "DEEPSEEK_API_KEY": "DeepSeek (research, docs)",
        }
        detected_providers = []
        for env_var, label in providers.items():
            key = os.environ.get(env_var, "")
            if key:
                detected_providers.append(label)
                if env_var == "ANTHROPIC_API_KEY":
                    self.config.anthropic_api_key = key

        if detected_providers:
            print(f"  Providers:  {len(detected_providers)} configured:")
            for p in detected_providers:
                print(f"              + {p}")
        else:
            print("  Providers:  None detected (set ANTHROPIC_API_KEY to enable intelligence)")

        # Detect Claude Code / MCP
        claude_dir = Path.home() / ".claude"
        if claude_dir.exists():
            print("  Claude Code: Detected (~/.claude/ exists)")
        else:
            print("  Claude Code: Not detected")

        print()

    @staticmethod
    def _detect_git_projects(root_dir: str) -> List[Dict[str, str]]:
        """Find git repositories under the root directory."""
        projects = []
        root = Path(root_dir)

        # Check if current dir is a git repo
        if (root / ".git").exists():
            branch = ""
            try:
                result = subprocess.run(
                    ["git", "branch", "--show-current"],
                    capture_output=True, text=True, cwd=root, timeout=5,
                )
                branch = result.stdout.strip()
            except (subprocess.SubprocessError, FileNotFoundError):
                branch = "unknown"
            projects.append({"name": root.name, "path": str(root), "branch": branch})
            return projects

        # Scan one level deep for git repos
        try:
            for child in sorted(root.iterdir()):
                if child.is_dir() and (child / ".git").exists():
                    branch = ""
                    try:
                        result = subprocess.run(
                            ["git", "branch", "--show-current"],
                            capture_output=True, text=True, cwd=child, timeout=5,
                        )
                        branch = result.stdout.strip()
                    except (subprocess.SubprocessError, FileNotFoundError):
                        branch = "unknown"
                    projects.append({"name": child.name, "path": str(child), "branch": branch})
                    if len(projects) >= 20:
                        break
        except PermissionError:
            pass

        return projects

    # ──────────────────────────────────────────────
    # Stage 2: Essentials
    # ──────────────────────────────────────────────

    def _stage_essentials(self):
        print("--- Stage 2/6: Essentials ---")
        print()

        # API Key
        if not self.config.anthropic_api_key:
            if self.non_interactive:
                print("  WARNING: No ANTHROPIC_API_KEY found.")
                print("  Set it with: export ANTHROPIC_API_KEY=sk-...")
                print("  Cortex core features work without it,")
                print("  but intelligence queries require an API key.")
            else:
                print("  Cortex needs an Anthropic API key for intelligence features.")
                print("  (Core features like memory and routing work without one.)")
                print()
                key = input("  ANTHROPIC_API_KEY [skip]: ").strip()
                if key:
                    self.config.anthropic_api_key = key

        print()

        # Subscription tier
        print("  What Anthropic subscription tier are you on?")
        print()
        for key, tier in SUBSCRIPTION_TIERS.items():
            print(f"    {key:12} — {tier['description']}")
        print()

        if self.non_interactive:
            self.config.subscription_tier = "pro"
        else:
            tier_input = input("  Subscription tier [pro]: ").strip().lower() or "pro"
            if tier_input not in SUBSCRIPTION_TIERS:
                print(f"  Unknown tier '{tier_input}', defaulting to 'pro'")
                tier_input = "pro"
            self.config.subscription_tier = tier_input

        tier_data = SUBSCRIPTION_TIERS[self.config.subscription_tier]

        if self.config.subscription_tier == "custom":
            if not self.non_interactive:
                allowance = input("  Monthly token allowance: ").strip()
                cost = input("  Monthly cost (USD): ").strip()
                self.config.monthly_token_allowance = int(allowance) if allowance else 5_000_000
                self.config.monthly_cost_usd = float(cost) if cost else 20.0
            else:
                self.config.monthly_token_allowance = 5_000_000
                self.config.monthly_cost_usd = 20.0
        else:
            self.config.monthly_token_allowance = tier_data["monthly_token_allowance"]
            self.config.monthly_cost_usd = tier_data["monthly_cost_usd"]

        if not self.non_interactive:
            reset = input("  Billing reset day of month [1]: ").strip()
            self.config.billing_reset_day = int(reset) if reset else 1
        else:
            self.config.billing_reset_day = 1

        print()
        print(f"  Subscription: {self.config.subscription_tier}")
        print(f"  Allowance:    {self.config.monthly_token_allowance:,} tokens/month")
        print(f"  Cost:         ${self.config.monthly_cost_usd:.2f}/month")
        print()

    # ──────────────────────────────────────────────
    # Stage 3: Project
    # ──────────────────────────────────────────────

    def _stage_project(self):
        print("--- Stage 3/6: Project Setup ---")
        print()

        if self.config.git_projects:
            print("  Detected projects:")
            for i, proj in enumerate(self.config.git_projects[:10], 1):
                print(f"    {i}. {proj['name']}")

            if self.non_interactive:
                self.config.primary_project = self.config.git_projects[0]["name"]
            else:
                choice = input(f"  Primary project [1]: ").strip()
                idx = int(choice) - 1 if choice.isdigit() else 0
                idx = max(0, min(idx, len(self.config.git_projects) - 1))
                self.config.primary_project = self.config.git_projects[idx]["name"]
        else:
            if not self.non_interactive:
                name = input("  Project name: ").strip()
                self.config.primary_project = name or "my-project"
            else:
                self.config.primary_project = "my-project"

        print(f"  Primary project: {self.config.primary_project}")
        print()

        # Goals
        print("  Project goals help Cortex prioritize intelligence and suggestions.")
        print("  Enter up to 3 goals (press Enter to skip):")
        print()

        if not self.non_interactive:
            for i in range(1, 4):
                goal = input(f"  Goal {i}: ").strip()
                if goal:
                    self.config.project_goals.append(goal)
                else:
                    break

        if not self.config.project_goals:
            self.config.project_goals = ["Ship reliable code", "Reduce technical debt"]
            print("  Using defaults: Ship reliable code, Reduce technical debt")

        print()

    # ──────────────────────────────────────────────
    # Stage 4: Preferences
    # ──────────────────────────────────────────────

    def _stage_preferences(self):
        print("--- Stage 4/6: Preferences ---")
        print()

        print("  Default model for most tasks:")
        print("    haiku  — Fastest, cheapest, good for simple tasks")
        print("    sonnet — Balanced quality and speed (recommended)")
        print("    opus   — Best quality, highest cost, complex tasks")
        print()

        if not self.non_interactive:
            model = input("  Default model [sonnet]: ").strip().lower() or "sonnet"
            if model in ("haiku", "sonnet", "opus"):
                self.config.preferred_model = model
            else:
                print(f"  Unknown model '{model}', using sonnet")
        print(f"  Default model: {self.config.preferred_model}")
        print()

        if not self.non_interactive:
            budget = input("  Daily budget limit in USD (0 = no limit) [0]: ").strip()
            self.config.budget_limit_usd = float(budget) if budget else 0.0
        print(f"  Budget limit: {'No limit' if self.config.budget_limit_usd == 0 else f'${self.config.budget_limit_usd:.2f}/day'}")

        print()
        print("  Cortex learning features (recommended):")
        print("    - Track model performance to improve future recommendations")
        print("    - Learn routing preferences (batch vs interactive)")
        print("    - Build verifiable expertise credentials")
        print()

        if not self.non_interactive:
            learn = input("  Enable learning? [Y/n]: ").strip().lower()
            self.config.learning_enabled = learn != "n"
            batch = input("  Enable batch suggestions? [Y/n]: ").strip().lower()
            self.config.batch_enabled = batch != "n"

        print()

    # ──────────────────────────────────────────────
    # Stage 5: Apply Configuration
    # ──────────────────────────────────────────────

    def _stage_apply(self):
        print("--- Stage 5/6: Applying Configuration ---")
        print()

        # Create directories
        self.cortex_home.mkdir(parents=True, exist_ok=True)
        for subdir in ["memories", "anti_patterns", "metrics", "subscriptions",
                        "ensemble", "batches", "signals"]:
            (self.cortex_home / subdir).mkdir(exist_ok=True)
        print("  Created ~/.cortex/ directory structure")

        # Write config.yaml
        config_data = self.config.to_dict()
        config_path = self.cortex_home / "config.yaml"
        try:
            import yaml
            with open(config_path, "w") as f:
                yaml.dump(config_data, f, default_flow_style=False, sort_keys=False)
        except ImportError:
            # Fallback to JSON if PyYAML not available
            config_path = self.cortex_home / "config.json"
            with open(config_path, "w") as f:
                json.dump(config_data, f, indent=2)
        print(f"  Wrote configuration to {config_path}")

        # Configure subscription
        try:
            from batch.subscription_optimizer import SubscriptionOptimizer

            optimizer = SubscriptionOptimizer()
            tier_data = SUBSCRIPTION_TIERS.get(self.config.subscription_tier, {})
            optimizer.configure_subscription(
                provider="anthropic",
                tier=self.config.subscription_tier,
                monthly_token_allowance=self.config.monthly_token_allowance,
                monthly_cost_usd=self.config.monthly_cost_usd,
                billing_reset_day=self.config.billing_reset_day,
                includes_batch=tier_data.get("includes_batch", True),
                rate_limit_rpm=tier_data.get("rate_limit_rpm", 50),
            )
            print("  Configured subscription tracking")
        except Exception as e:
            print(f"  Note: Could not configure subscription tracking: {e}")

        # Write GOALS.md if it doesn't exist and we have goals
        if self.config.project_goals:
            goals_path = Path(self.config.cortex_dir) / "GOALS.md"
            if not goals_path.exists():
                goals_content = "# Project Goals\n\n"
                for goal in self.config.project_goals:
                    goals_content += f"- {goal}\n"
                goals_content += "\n_Generated by Cortex setup wizard._\n"
                try:
                    with open(goals_path, "w") as f:
                        f.write(goals_content)
                    print(f"  Created {goals_path}")
                except PermissionError:
                    print(f"  Note: Could not write GOALS.md (permission denied)")

        print()

    # ──────────────────────────────────────────────
    # Stage 6: Verify
    # ──────────────────────────────────────────────

    def _stage_verify(self):
        print("--- Stage 6/6: Verification ---")
        print()

        checks = []

        # Check 1: Config exists
        config_exists = (self.cortex_home / "config.yaml").exists() or (self.cortex_home / "config.json").exists()
        checks.append(("Configuration file", config_exists))

        # Check 2: Directory structure
        dirs_ok = all(
            (self.cortex_home / d).exists()
            for d in ["memories", "metrics", "subscriptions", "ensemble"]
        )
        checks.append(("Directory structure", dirs_ok))

        # Check 3: Subscription configured
        sub_ok = False
        try:
            from batch.subscription_optimizer import SubscriptionOptimizer
            optimizer = SubscriptionOptimizer()
            status = optimizer.get_utilization_status("anthropic")
            sub_ok = status is not None
        except Exception:
            pass
        checks.append(("Subscription tracking", sub_ok))

        # Check 4: Core imports
        imports_ok = True
        for mod in ["intelligence.ensemble_decider", "intelligence.temporal_router",
                     "intelligence.verifiable_expertise", "batch.utilization_learning"]:
            try:
                __import__(mod)
            except Exception:
                imports_ok = False
                break
        checks.append(("Core modules", imports_ok))

        # Check 5: API key
        api_ok = bool(self.config.anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY"))
        checks.append(("API key", api_ok))

        # Print results
        all_ok = True
        for name, passed in checks:
            icon = "OK" if passed else "MISSING"
            print(f"  [{icon:7}] {name}")
            if not passed:
                all_ok = False

        print()
        if all_ok:
            print("  All checks passed. Cortex is ready.")
        else:
            print("  Some checks failed. Cortex will work with reduced functionality.")
            print("  Run 'cortex setup' again to fix missing items.")
        print()

    # ──────────────────────────────────────────────
    # Demonstrate value immediately
    # ──────────────────────────────────────────────

    def _stage_demonstrate(self):
        print("=" * 60)
        print("  CORTEX IS READY")
        print("=" * 60)
        print()

        # Show utilization dashboard
        try:
            from batch.subscription_optimizer import SubscriptionOptimizer
            optimizer = SubscriptionOptimizer()
            dashboard = optimizer.format_utilization_dashboard()
            print(dashboard)
        except Exception:
            pass

        print()
        # Show MCP config if Claude Code detected
        claude_dir = Path.home() / ".claude"
        if claude_dir.exists():
            cortex_path = Path(__file__).parent / "mcp_server.py"
            print("  MCP Integration (for Claude Code / Claude Desktop):")
            print("  Add this to your MCP config:")
            print()
            print('  {')
            print('    "mcpServers": {')
            print('      "cortex": {')
            print(f'        "command": "python",')
            print(f'        "args": ["{cortex_path}"]')
            print('      }')
            print('    }')
            print('  }')
            print()

        print("  Next steps:")
        print()
        print("  1. Run 'cortex status' to see your session context")
        print("  2. Run 'cortex intelligence \"what should I work on?\"' to")
        print("     query the intelligence system")
        print("  3. Run 'cortex briefing' for your daily intelligence briefing")
        print()
        print("  As you work, Cortex will:")
        print("  - Learn which models work best for your tasks")
        print("  - Track your subscription utilization")
        print("  - Build verifiable expertise credentials")
        print("  - Surface anti-patterns before you repeat mistakes")
        print()
        print("  The more you use it, the smarter it gets.")
        print()


def main():
    """Entry point for setup wizard."""
    non_interactive = "--non-interactive" in sys.argv
    wizard = CortexSetupWizard(non_interactive=non_interactive)
    config = wizard.run()
    return config


if __name__ == "__main__":
    main()
