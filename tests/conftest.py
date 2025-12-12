import shutil
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from cortex.email_delivery import EmailDelivery
from cortex.intelligence import (
    ContextBuilder,
    DecisionLogger,
    OutcomeTracker,
    StrategicOptions,
)


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    temp_path = tempfile.mkdtemp()
    yield Path(temp_path)
    shutil.rmtree(temp_path)


@pytest.fixture
def mock_git_repo(temp_dir):
    """Create a mock git repository structure."""
    repo_path = temp_dir / "test_repo"
    repo_path.mkdir()

    # Create git directory
    (repo_path / ".git").mkdir()

    # Create some test files
    (repo_path / "src").mkdir()
    (repo_path / "src" / "main.py").write_text("def main(): pass")
    (repo_path / "tests").mkdir()
    (repo_path / "tests" / "test_main.py").write_text("def test_main(): pass")
    (repo_path / "README.md").write_text("# Test Project")

    return repo_path


@pytest.fixture
def test_db(temp_dir):
    """Create a test database."""
    db_path = temp_dir / "cortex_test.db"
    conn = sqlite3.connect(str(db_path))

    # Create tables
    conn.execute(
        """
        CREATE TABLE decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            context TEXT NOT NULL,
            options TEXT NOT NULL,
            selected_option INTEGER,
            reasoning TEXT
        )
    """
    )

    conn.execute(
        """
        CREATE TABLE outcomes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            decision_id INTEGER NOT NULL,
            timestamp TEXT NOT NULL,
            outcome TEXT NOT NULL,
            metrics TEXT,
            lessons_learned TEXT,
            FOREIGN KEY (decision_id) REFERENCES decisions(id)
        )
    """
    )

    conn.commit()
    conn.close()

    return db_path


@pytest.fixture
def context_builder(mock_git_repo):
    """Create a ContextBuilder instance."""
    return ContextBuilder(str(mock_git_repo))


@pytest.fixture
def decision_logger(test_db):
    """Create a DecisionLogger instance."""
    return DecisionLogger(str(test_db))


@pytest.fixture
def outcome_tracker(test_db):
    """Create an OutcomeTracker instance."""
    return OutcomeTracker(str(test_db))


@pytest.fixture
def strategic_options(context_builder, decision_logger, outcome_tracker):
    """Create a StrategicOptions instance."""
    return StrategicOptions(context_builder, decision_logger, outcome_tracker)


@pytest.fixture
def mock_gmail_service():
    """Create a mock Gmail API service."""
    service = MagicMock()
    service.users().messages().send().execute.return_value = {
        "id": "test_message_id",
        "labelIds": ["SENT"],
    }
    return service


@pytest.fixture
def email_delivery(mock_gmail_service, temp_dir):
    """Create an EmailDelivery instance with mocked Gmail."""
    delivery = EmailDelivery(
        credentials_path=str(temp_dir / "credentials.json"),
        token_path=str(temp_dir / "token.pickle"),
    )
    delivery.service = mock_gmail_service
    return delivery


@pytest.fixture
def sample_context():
    """Sample context data for testing."""
    return {
        "git_status": {
            "branch": "feature/cortex-tests",
            "uncommitted_changes": True,
            "files_changed": ["intelligence.py", "cli.py"],
        },
        "recent_errors": [
            {
                "file": "intelligence.py",
                "line": 42,
                "error": "TypeError: expected str, got None",
            }
        ],
        "test_results": {"total": 10, "passed": 8, "failed": 2, "coverage": 65.5},
        "time_of_day": "morning",
        "recent_decisions": [],
    }


@pytest.fixture
def sample_options():
    """Sample strategic options for testing."""
    return [
        {
            "title": "Fix Critical Error in intelligence.py",
            "description": "Address TypeError in line 42 affecting core functionality",
            "priority": "high",
            "estimated_time": "30 minutes",
            "dependencies": [],
            "reasoning": "Blocking 2 failing tests",
        },
        {
            "title": "Increase Test Coverage",
            "description": "Add tests for uncovered code paths in cli.py",
            "priority": "medium",
            "estimated_time": "1 hour",
            "dependencies": [],
            "reasoning": "Coverage below target (65.5%)",
        },
        {
            "title": "Commit Current Progress",
            "description": "Commit working changes before proceeding",
            "priority": "medium",
            "estimated_time": "5 minutes",
            "dependencies": [],
            "reasoning": "Uncommitted changes on feature branch",
        },
    ]
