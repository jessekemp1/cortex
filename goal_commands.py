"""
Cortex Goal/Task/Blocker CLI Commands
"""
import sys
import importlib.util
from pathlib import Path

# Force load storage from cortex directory (not from local-orchestrator/storage)
_cortex_dir = Path(__file__).parent.resolve()
_storage_init = _cortex_dir / "storage" / "__init__.py"
_database_file = _cortex_dir / "storage" / "database.py"
_models_file = _cortex_dir / "storage" / "models.py"

# Load storage package
spec = importlib.util.spec_from_file_location("cortex_storage", str(_storage_init), submodule_search_locations=[str(_cortex_dir / "storage")])
storage = importlib.util.module_from_spec(spec)
sys.modules["cortex_storage"] = storage
spec.loader.exec_module(storage)

# Load models
spec_models = importlib.util.spec_from_file_location("cortex_storage.models", str(_models_file))
models = importlib.util.module_from_spec(spec_models)
sys.modules["cortex_storage.models"] = models
spec_models.loader.exec_module(models)

# Load database
spec_db = importlib.util.spec_from_file_location("cortex_storage.database", str(_database_file))
database = importlib.util.module_from_spec(spec_db)
sys.modules["cortex_storage.database"] = database
# We need to patch the module to find models
database.__dict__["sys"] = sys
database.__dict__["Path"] = Path
spec_db.loader.exec_module(database)

# Now get what we need
CortexDB = database.CortexDB
Goal = models.Goal
Task = models.Task
Blocker = models.Blocker
Progress = models.Progress
Priority = models.Priority
Status = models.Status
TaskStatus = models.TaskStatus


def cmd_goal(args):
    """Manage goals."""
    db = CortexDB()

    if args.goal_command == "add":
        goal_id = args.title.lower().replace(" ", "-")[:30]
        goal = Goal(
            id=goal_id,
            title=args.title,
            priority=Priority(args.priority) if args.priority else Priority.B,
            status=Status.PENDING,
            project=getattr(args, 'project', None),
            success_criteria=getattr(args, 'criteria', None),
            deadline=getattr(args, 'deadline', None),
        )
        db.add_goal(goal)
        print(f"Goal added: {goal.id}")
        print(f"  Title: {goal.title}")
        print(f"  Priority: {goal.priority.value}")
        if goal.project:
            print(f"  Project: {goal.project}")
        if goal.deadline:
            print(f"  Deadline: {goal.deadline}")

    elif args.goal_command == "list":
        goals = db.list_goals(
            priority=getattr(args, 'priority', None),
            status=getattr(args, 'status', None),
            project=getattr(args, 'project', None),
        )
        if not goals:
            print("No goals found.")
            return

        print(f"\n{'ID':<25} {'Pri':<4} {'Status':<12} {'Project':<15} Title")
        print("-" * 80)
        for g in goals:
            pri = g.priority.value if isinstance(g.priority, Priority) else g.priority
            status = g.status.value if isinstance(g.status, Status) else g.status
            proj = (g.project or "")[:15]
            print(f"{g.id:<25} {pri:<4} {status:<12} {proj:<15} {g.title[:30]}")

    elif args.goal_command == "update":
        updates = {}
        if getattr(args, 'status', None):
            updates["status"] = args.status
        if getattr(args, 'priority', None):
            updates["priority"] = args.priority
        if getattr(args, 'title', None):
            updates["title"] = args.title

        goal = db.update_goal(args.id, **updates)
        if goal:
            print(f"Goal updated: {goal.id}")
        else:
            print(f"Goal not found: {args.id}")

    elif args.goal_command == "delete":
        if db.delete_goal(args.id):
            print(f"Goal deleted: {args.id}")
        else:
            print(f"Goal not found: {args.id}")

    elif args.goal_command == "show":
        result = db.get_goal_with_tasks(args.id)
        if not result:
            print(f"Goal not found: {args.id}")
            return

        goal = result["goal"]
        print(f"\nGoal: {goal['title']}")
        print(f"  ID: {goal['id']}")
        print(f"  Priority: {goal['priority']}")
        print(f"  Status: {goal['status']}")
        if goal.get("project"):
            print(f"  Project: {goal['project']}")
        if goal.get("deadline"):
            print(f"  Deadline: {goal['deadline']}")
        if goal.get("success_criteria"):
            print(f"  Success Criteria: {goal['success_criteria']}")

        print(f"\n  Tasks: {result['task_completion']}")
        for t in result["tasks"]:
            icon = "x" if t["status"] == "completed" else "o"
            print(f"    [{icon}] {t['title']}")

        if result["blockers"]:
            print(f"\n  Blockers:")
            for b in result["blockers"]:
                print(f"    ! {b['description']}")


def cmd_task(args):
    """Manage tasks."""
    db = CortexDB()

    if args.task_command == "add":
        task_id = args.title.lower().replace(" ", "-")[:30]
        task = Task(
            id=task_id,
            title=args.title,
            goal_id=getattr(args, 'goal', None),
            status=TaskStatus.PENDING,
            source="manual",
        )
        db.add_task(task)
        print(f"Task added: {task.id}")
        if task.goal_id:
            print(f"  Goal: {task.goal_id}")

    elif args.task_command == "list":
        tasks = db.list_tasks(
            goal_id=getattr(args, 'goal', None),
            status=getattr(args, 'status', None)
        )
        if not tasks:
            print("No tasks found.")
            return

        print(f"\n{'ID':<30} {'Status':<12} {'Goal':<20} Title")
        print("-" * 90)
        for t in tasks:
            status = t.status.value if isinstance(t.status, TaskStatus) else t.status
            goal = (t.goal_id or "")[:20]
            print(f"{t.id:<30} {status:<12} {goal:<20} {t.title[:30]}")

    elif args.task_command == "done":
        task = db.complete_task(args.id)
        if task:
            print(f"Task completed: {task.id}")
            if task.goal_id:
                db.add_progress(Progress(
                    goal_id=task.goal_id,
                    task_id=task.id,
                    action="completed",
                    notes=f"Completed task: {task.title}",
                ))
        else:
            print(f"Task not found: {args.id}")

    elif args.task_command == "update":
        updates = {}
        if getattr(args, 'status', None):
            updates["status"] = args.status
        if getattr(args, 'title', None):
            updates["title"] = args.title

        task = db.update_task(args.id, **updates)
        if task:
            print(f"Task updated: {task.id}")
        else:
            print(f"Task not found: {args.id}")


def cmd_blocker(args):
    """Manage blockers."""
    db = CortexDB()

    if args.blocker_command == "add":
        blocker = Blocker(
            description=args.description,
            project=getattr(args, 'project', None),
            goal_id=getattr(args, 'goal', None),
        )
        blocker = db.add_blocker(blocker)
        print(f"Blocker added: #{blocker.id}")
        print(f"  {blocker.description}")
        if blocker.project:
            print(f"  Project: {blocker.project}")

    elif args.blocker_command == "list":
        blockers = db.list_blockers(
            project=getattr(args, 'project', None),
            goal_id=getattr(args, 'goal', None),
            include_resolved=getattr(args, 'resolved', False),
        )
        if not blockers:
            print("No blockers found.")
            return

        print(f"\n{'#':<5} {'Project':<15} {'Goal':<15} Description")
        print("-" * 70)
        for b in blockers:
            icon = "[x]" if b.resolved else "[ ]"
            proj = (b.project or "")[:15]
            goal = (b.goal_id or "")[:15]
            print(f"{icon} {b.id:<3} {proj:<15} {goal:<15} {b.description[:40]}")

    elif args.blocker_command == "resolve":
        blocker = db.resolve_blocker(int(args.id))
        if blocker:
            print(f"Blocker resolved: #{blocker.id}")
        else:
            print(f"Blocker not found: #{args.id}")


def cmd_progress(args):
    """Log or view progress."""
    db = CortexDB()

    if args.progress_command == "add":
        progress = Progress(
            goal_id=args.goal,
            task_id=getattr(args, 'task', None),
            action="progressed",
            notes=args.notes,
        )
        db.add_progress(progress)
        print(f"Progress logged for goal: {args.goal}")

    elif args.progress_command == "list":
        entries = db.list_progress(goal_id=args.goal, limit=getattr(args, 'limit', 20))
        if not entries:
            print("No progress entries found.")
            return

        print(f"\nProgress for goal: {args.goal}")
        print("-" * 60)
        for p in entries:
            ts = p.timestamp[:16] if p.timestamp else "?"
            print(f"  [{ts}] {p.notes}")


def register_goal_commands(subparsers):
    """Register goal, task, blocker, and progress subparsers."""
    
    goal_parser = subparsers.add_parser("goal", help="Manage strategic goals")
    goal_subparsers = goal_parser.add_subparsers(dest="goal_command", help="Goal commands")

    goal_add = goal_subparsers.add_parser("add", help="Add a new goal")
    goal_add.add_argument("title", help="Goal title")
    goal_add.add_argument("--priority", "-p", choices=["A", "B", "C"], default="B")
    goal_add.add_argument("--project", help="Associated project")
    goal_add.add_argument("--deadline", help="Deadline (YYYY-MM-DD)")
    goal_add.add_argument("--criteria", help="Success criteria")
    goal_add.set_defaults(func=cmd_goal)

    goal_list = goal_subparsers.add_parser("list", help="List goals")
    goal_list.add_argument("--priority", "-p", choices=["A", "B", "C"])
    goal_list.add_argument("--status", "-s", choices=["pending", "in_progress", "completed", "blocked"])
    goal_list.add_argument("--project", help="Filter by project")
    goal_list.set_defaults(func=cmd_goal)

    goal_update = goal_subparsers.add_parser("update", help="Update a goal")
    goal_update.add_argument("id", help="Goal ID")
    goal_update.add_argument("--status", "-s", choices=["pending", "in_progress", "completed", "blocked"])
    goal_update.add_argument("--priority", "-p", choices=["A", "B", "C"])
    goal_update.add_argument("--title", help="New title")
    goal_update.set_defaults(func=cmd_goal)

    goal_delete = goal_subparsers.add_parser("delete", help="Delete a goal")
    goal_delete.add_argument("id", help="Goal ID")
    goal_delete.set_defaults(func=cmd_goal)

    goal_show = goal_subparsers.add_parser("show", help="Show goal details")
    goal_show.add_argument("id", help="Goal ID")
    goal_show.set_defaults(func=cmd_goal)

    task_parser = subparsers.add_parser("task", help="Manage tasks")
    task_subparsers = task_parser.add_subparsers(dest="task_command", help="Task commands")

    task_add = task_subparsers.add_parser("add", help="Add a new task")
    task_add.add_argument("title", help="Task title")
    task_add.add_argument("--goal", "-g", help="Associated goal ID")
    task_add.set_defaults(func=cmd_task)

    task_list = task_subparsers.add_parser("list", help="List tasks")
    task_list.add_argument("--goal", "-g", help="Filter by goal")
    task_list.add_argument("--status", "-s", choices=["pending", "in_progress", "completed"])
    task_list.set_defaults(func=cmd_task)

    task_done = task_subparsers.add_parser("done", help="Mark task as done")
    task_done.add_argument("id", help="Task ID")
    task_done.set_defaults(func=cmd_task)

    task_update = task_subparsers.add_parser("update", help="Update a task")
    task_update.add_argument("id", help="Task ID")
    task_update.add_argument("--status", "-s", choices=["pending", "in_progress", "completed"])
    task_update.add_argument("--title", help="New title")
    task_update.set_defaults(func=cmd_task)

    blocker_parser = subparsers.add_parser("blocker", help="Manage blockers")
    blocker_subparsers = blocker_parser.add_subparsers(dest="blocker_command", help="Blocker commands")

    blocker_add = blocker_subparsers.add_parser("add", help="Add a blocker")
    blocker_add.add_argument("description", help="Blocker description")
    blocker_add.add_argument("--project", "-p", help="Project name")
    blocker_add.add_argument("--goal", "-g", help="Goal ID")
    blocker_add.set_defaults(func=cmd_blocker)

    blocker_list = blocker_subparsers.add_parser("list", help="List blockers")
    blocker_list.add_argument("--project", "-p", help="Filter by project")
    blocker_list.add_argument("--goal", "-g", help="Filter by goal")
    blocker_list.add_argument("--resolved", "-r", action="store_true", help="Include resolved")
    blocker_list.set_defaults(func=cmd_blocker)

    blocker_resolve = blocker_subparsers.add_parser("resolve", help="Resolve a blocker")
    blocker_resolve.add_argument("id", help="Blocker ID")
    blocker_resolve.set_defaults(func=cmd_blocker)

    progress_parser = subparsers.add_parser("progress", help="Log progress updates")
    progress_subparsers = progress_parser.add_subparsers(dest="progress_command", help="Progress commands")

    progress_add = progress_subparsers.add_parser("add", help="Add progress note")
    progress_add.add_argument("notes", help="Progress notes")
    progress_add.add_argument("--goal", "-g", required=True, help="Goal ID")
    progress_add.add_argument("--task", "-t", help="Task ID")
    progress_add.set_defaults(func=cmd_progress)

    progress_list = progress_subparsers.add_parser("list", help="List progress")
    progress_list.add_argument("--goal", "-g", required=True, help="Goal ID")
    progress_list.add_argument("--limit", "-l", type=int, default=20)
    progress_list.set_defaults(func=cmd_progress)
