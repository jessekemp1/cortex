"""CLI command modules."""

from cli.commands.core import cmd_next, cmd_init, cmd_status, cmd_health
from cli.commands.briefing import cmd_briefing, cmd_briefing_style, cmd_statusline, cmd_reflect
from cli.commands.intelligence import (
    cmd_deep,
    cmd_quick,
    cmd_auto,
    cmd_config,
    cmd_intelligence,
    cmd_portfolio,
    cmd_deps,
    cmd_tooling,
)
from cli.commands.learning import cmd_feedback, cmd_learn, cmd_interactions
from cli.commands.batch import (
    cmd_batch_status,
    cmd_v2a_batch,
    cmd_schedule,
    cmd_execute,
    cmd_orchestrate,
    cmd_notify,
)
from cli.commands.system import (
    cmd_git,
    cmd_sync,
    cmd_docs,
    cmd_dashboard,
    cmd_bandwidth,
    cmd_watch,
    cmd_batch_fill,
)

__all__ = [
    "cmd_next",
    "cmd_init",
    "cmd_status",
    "cmd_health",
    "cmd_briefing",
    "cmd_briefing_style",
    "cmd_statusline",
    "cmd_reflect",
    "cmd_deep",
    "cmd_quick",
    "cmd_auto",
    "cmd_config",
    "cmd_intelligence",
    "cmd_portfolio",
    "cmd_deps",
    "cmd_tooling",
    "cmd_feedback",
    "cmd_learn",
    "cmd_interactions",
    "cmd_batch_status",
    "cmd_v2a_batch",
    "cmd_schedule",
    "cmd_execute",
    "cmd_orchestrate",
    "cmd_notify",
    "cmd_git",
    "cmd_sync",
    "cmd_docs",
    "cmd_dashboard",
    "cmd_bandwidth",
    "cmd_watch",
    "cmd_batch_fill",
]
