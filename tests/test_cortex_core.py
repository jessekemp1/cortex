import pytest
import time
from datetime import datetime, timedelta
from freezegun import freeze_time
from unittest.mock import patch, MagicMock

from cortex.intelligence import (
    StrategicOptions, ContextBuilder, DecisionLogger, 
    OutcomeTracker, OptionValidator
)


class TestContextBuilder:
    """Test ContextBuilder functionality."""
    
    def test_initialization(self, mock_git_repo):
        """Test ContextBuilder initializes correctly."""
        builder = ContextBuilder(str(mock_git_repo))
        assert builder.repo_path == str(mock_git_repo)
    
    @patch('subprocess.run')
    def test_get_git_status(self, mock_run, context_builder):
        """Test git status extraction."""
        # Mock git commands
        mock_run.side_effect = [
            MagicMock(stdout="feature/test-branch\n", returncode=0),
            MagicMock(stdout=" M intelligence.py\n M cli.py\n", returncode=0),
            MagicMock(stdout="2\n", returncode=0)
        ]
        
        status = context_builder.get_git_status()
        
        assert status['branch'] == 'feature/test-branch'
        assert status['uncommitted_changes'] is True
        assert len(status['files_changed']) == 2
        assert 'intelligence.py' in status['files_changed']
    
    @patch('subprocess.run')
    def test_get_git_status_clean_repo(self, mock_run, context_builder):
        """Test git status with clean repository."""
        mock_run.side_effect = [
            MagicMock(stdout="main\n", returncode=0),
            MagicMock(stdout="", returncode=0),
            MagicMock(stdout="0\n", returncode=0)
        ]
        
        status = context_builder.get_git_status()
        
        assert status['branch'] == 'main'
        assert status['uncommitted_changes'] is False
        assert len(status['files_changed']) == 0
    
    def test_get_recent_errors(self, context_builder, mock_git_repo):
        """Test error detection from log files."""
        # Create error log
        error_log = mock_git_repo / "error.log"
        error_log.write_text("""
[ERROR] intelligence.py:42 - TypeError: expected str, got None
[ERROR] cli.py:100 - ValueError: invalid option index
        """)
        
        errors = context_builder.get_recent_errors(str(error_log))
        
        assert len(errors) >= 2
        assert any('TypeError' in e['error'] for e in errors)
        assert any('intelligence.py' in e['file'] for e in errors)
    
    @patch('subprocess.run')
    def test_get_test_results(self, mock_run, context_builder):
        """Test pytest results parsing."""
        mock_run.return_value = MagicMock(
            stdout="8 passed, 2 failed in 2.5s\nCoverage: 65.5%\n",
            returncode=0
        )
        
        results = context_builder.get_test_results()
        
        assert results['total'] == 10
        assert results['passed'] == 8
        assert results['failed'] == 2
    
    @freeze_time("2024-01-15 09:30:00")
    def test_get_time_context(self, context_builder):
        """Test time-of-day context detection."""
        context = context_builder.get_time_context()
        
        assert context['time_of_day'] == 'morning'
        assert context['hour'] == 9
    
    @freeze_time("2024-01-15 14:30:00")
    def test_get_time_context_afternoon(self, context_builder):
        """Test afternoon time context."""
        context = context_builder.get_time_context()
        
        assert context['time_of_day'] == 'afternoon'
    
    def test_build_context(self, context_builder):
        """Test full context building."""
        with patch.object(context_builder, 'get_git_status') as mock_git, \
             patch.object(context_builder, 'get_recent_errors') as mock_errors, \
             patch.object(context_builder, 'get_test_results') as mock_tests:
            
            mock_git.return_value = {'branch': 'main', 'uncommitted_changes': False}
            mock_errors.return_value = []
            mock_tests.return_value = {'total': 10, 'passed': 10, 'failed': 0}
            
            context = context_builder.build_context()
            
            assert 'git_status' in context
            assert 'recent_errors' in context
            assert 'test_results' in context
            assert 'time_of_day' in context


class TestDecisionLogger:
    """Test DecisionLogger functionality."""
    
    def test_log_decision(self, decision_logger, sample_context, sample_options):
        """Test logging a decision."""
        decision_id = decision_logger.log_decision(
            context=sample_context,
            options=sample_options,
            selected_option=0,
            reasoning="Critical bug needs immediate attention"
        )
        
        assert decision_id > 0
    
    def test_get_decision(self, decision_logger, sample_context, sample_options):
        """Test retrieving a logged decision."""
        decision_id = decision_logger.log_decision(
            context=sample_context,
            options=sample_options,
            selected_option=1
        )
        
        decision = decision_logger.get_decision(decision_id)
        
        assert decision is not None
        assert decision['id'] == decision_id
        assert decision['selected_option'] == 1
        assert 'context' in decision
        assert 'options' in decision
    
    def test_get_recent_decisions(self, decision_logger, sample_context, sample_options):
        """Test retrieving recent decisions."""
        # Log multiple decisions
        for i in range(5):
            decision_logger.log_decision(
                context=sample_context,
                options=sample_options,
                selected_option=i % 3
            )
        
        recent = decision_logger.get_recent_decisions(limit=3)
        
        assert len(recent) == 3
        assert recent[0]['id'] > recent[1]['id']  # Most recent first
    
    def test_get_decision_not_found(self, decision_logger):
        """Test retrieving non-existent decision."""
        decision = decision_logger.get_decision(99999)
        assert decision is None


class TestOutcomeTracker:
    """Test OutcomeTracker functionality."""
    
    def test_track_outcome_success(self, outcome_tracker, decision_logger, sample_context, sample_options):
        """Test tracking successful outcome."""
        decision_id = decision_logger.log_decision(
            context=sample_context,
            options=sample_options,
            selected_option=0
        )
        
        outcome_id = outcome_tracker.track_outcome(
            decision_id=decision_id,
            outcome='success',
            metrics={'time_taken': '25 minutes', 'tests_fixed': 2},
            lessons_learned='TypeError was due to missing null check'
        )
        
        assert outcome_id > 0
    
    def test_track_outcome_failure(self, outcome_tracker, decision_logger, sample_context, sample_options):
        """Test tracking failed outcome."""
        decision_id = decision_logger.log_decision(
            context=sample_context,
            options=sample_options,
            selected_option=1
        )
        
        outcome_id = outcome_tracker.track_outcome(
            decision_id=decision_id,
            outcome='failure',
            metrics={'time_taken': '2 hours'},
            lessons_learned='Underestimated complexity of test refactoring'
        )
        
        assert outcome_id > 0
    
    def test_get_outcome(self, outcome_tracker, decision_logger, sample_context, sample_options):
        """Test retrieving tracked outcome."""
        decision_id = decision_logger.log_decision(
            context=sample_context,
            options=sample_options,
            selected_option=0
        )
        
        outcome_id = outcome_tracker.track_outcome(
            decision_id=decision_id,
            outcome='success',
            metrics={'time_taken': '30 minutes'}
        )
        
        outcome = outcome_tracker.get_outcome(outcome_id)
        
        assert outcome is not None
        assert outcome['decision_id'] == decision_id
        assert outcome['outcome'] == 'success'
    
    def test_get_decision_outcomes(self, outcome_tracker, decision_logger, sample_context, sample_options):
        """Test retrieving all outcomes for a decision."""
        decision_id = decision_logger.log_decision(
            context=sample_context,
            options=sample_options,
            selected_option=0
        )
        
        # Track multiple outcomes (e.g., partial then full completion)
        outcome_tracker.track_outcome(decision_id, 'partial', {})
        outcome_tracker.track_outcome(decision_id, 'success', {})
        
        outcomes = outcome_tracker.get_decision_outcomes(decision_id)
        
        assert len(outcomes) == 2
    
    def test_analyze_patterns(self, outcome_tracker, decision_logger, sample_context, sample_options):
        """Test pattern analysis from outcomes."""
        # Create multiple decisions with outcomes
        for i in range(10):
            decision_id = decision_logger.log_decision(
                context=sample_context,
                options=sample_options,
                selected_option=i % 3
            )
            outcome = 'success' if i % 2 == 0 else 'failure'
            outcome_tracker.track_outcome(decision_id, outcome, {})
        
        patterns = outcome_tracker.analyze_patterns()
        
        assert 'success_rate' in patterns
        assert 'most_successful_options' in patterns
        assert 0 <= patterns['success_rate'] <= 1


class TestOptionValidator:
    """Test OptionValidator functionality."""
    
    def test_validate_option_structure(self, sample_options):
        """Test option structure validation."""
        validator = OptionValidator()
        
        for option in sample_options:
            is_valid, errors = validator.validate_option(option)
            assert is_valid
            assert len(errors) == 0
    
    def test_validate_missing_fields(self):
        """Test validation with missing required fields."""
        validator = OptionValidator()
        invalid_option = {
            'title': 'Test Option',
            # Missing description, priority, etc.
        }
        
        is_valid, errors = validator.validate_option(invalid_option)
        
        assert not is_valid
        assert len(errors) > 0
        assert any('description' in error for error in errors)
    
    def test_validate_options_distinct(self, sample_options):
        """Test that options are distinct from each other."""
        validator = OptionValidator()
        
        is_valid, errors = validator.validate_options_distinct(sample_options)
        
        assert is_valid
        assert len(errors) == 0
    
    def test_validate_duplicate_options(self):
        """Test detection of duplicate options."""
        validator = OptionValidator()
        duplicate_options = [
            {
                'title': 'Fix Bug',
                'description': 'Fix the bug in module X',
                'priority': 'high',
                'estimated_time': '1 hour',
                'dependencies': [],
                'reasoning': 'Critical issue'
            },
            {
                'title': 'Fix Bug',  # Duplicate
                'description': 'Fix the bug in module X',
                'priority': 'high',
                'estimated_time': '1 hour',
                'dependencies': [],
                'reasoning': 'Critical issue'
            }
        ]
        
        is_valid, errors = validator.validate_options_distinct(duplicate_options)
        
        assert not is_valid
        assert len(errors) > 0


class TestStrategicOptions:
    """Test StrategicOptions main class."""
    
    def test_initialization(self, strategic_options):
        """Test StrategicOptions initializes correctly."""
        assert strategic_options.context_builder is not None
        assert strategic_options.decision_logger is not None
        assert strategic_options.outcome_tracker is not None
    
    def test_generate_options(self, strategic_options, sample_context):
        """Test option generation."""
        start_time = time.time()
        options = strategic_options.generate_options(sample_context)
        duration = time.time() - start_time
        
        # Should generate 3-5 options
        assert 3 <= len(options) <= 5
        
        # Should complete in <500ms
        assert duration < 0.5
        
        # Each option should be valid
        for option in options:
            assert 'title' in option
            assert 'description' in option
            assert 'priority' in option
            assert 'estimated_time' in option
    
    def test_generate_options_with_errors(self, strategic_options):
        """Test option generation prioritizes errors."""
        context = {
            'git_status': {'branch': 'main', 'uncommitted_changes': False},
            'recent_errors': [
                {'file': 'main.py', 'line': 10, 'error': 'SyntaxError'}
            ],
            'test_results': {'total': 10, 'passed': 10, 'failed': 0},
            'time_of_day': 'morning',
            'recent_decisions': []
        }
        
        options = strategic_options.generate_options(context)
        
        # First option should address the error
        assert any('error' in opt['title'].lower() or 'error' in opt['description'].lower() 
                   for opt in options[:2])
    
    def test_generate_options_with_failing_tests(self, strategic_options):
        """Test option generation prioritizes failing tests."""
        context = {
            'git_status': {'branch': 'main', 'uncommitted_changes': False},
            'recent_errors': [],
            'test_results': {'total': 10, 'passed': 7, 'failed': 3},
            'time_of_day': 'afternoon',
            'recent_decisions': []
        }
        
        options = strategic_options.generate_options(context)
        
        # Should include option to fix failing tests
        assert any('test' in opt['title'].lower() or 'test' in opt['description'].lower() 
                   for opt in options)
    
    def test_generate_options_clean_state(self, strategic_options):
        """Test option generation with clean repository."""
        context = {
            'git_status': {'branch': 'main', 'uncommitted_changes': False},
            'recent_errors': [],
            'test_results': {'total': 10, 'passed': 10, 'failed': 0, 'coverage': 85.0},
            'time_of_day': 'morning',
            'recent_decisions': []
        }
        
        options = strategic_options.generate_options(context)
        
        # Should suggest proactive improvements
        assert len(options) >= 3
    
    def test_select_option(self, strategic_options, sample_context, sample_options):
        """Test option selection."""
        with patch.object(strategic_options, 'generate_options', return_value=sample_options):
            decision_id = strategic_options.select_option(
                context=sample_context,
                option_index=0,
                reasoning="Most critical issue"
            )
            
            assert decision_id > 0
    
    def test_select_invalid_option(self, strategic_options, sample_context, sample_options):
        """Test selecting invalid option index."""
        with patch.object(strategic_options, 'generate_options', return_value=sample_options):
            with pytest.raises(IndexError):
                strategic_options.select_option(
                    context=sample_context,
                    option_index=99
                )
    
    def test_learning_improves_recommendations(self, strategic_options, decision_logger, outcome_tracker):
        """Test that learning from outcomes improves future recommendations."""
        context = {
            'git_status': {'branch': 'main', 'uncommitted_changes': False},
            'recent_errors': [{'file': 'test.py', 'error': 'TypeError'}],
            'test_results': {'total': 10, 'passed': 10, 'failed': 0},
            'time_of_day': 'morning',
            'recent_decisions': []
        }
        
        # Generate initial options
        options1 = strategic_options.generate_options(context)
        
        # Log several successful decisions
        for _ in range(5):
            decision_id = decision_logger.log_decision(context, options1, 0)
            outcome_tracker.track_outcome(decision_id, 'success', {'time_taken': '20 min'})
        
        # Generate options again - should be influenced by learning
        options2 = strategic_options.generate_options(context)
        
        # Options should still be valid and potentially improved
        assert len(options2) >= 3
        assert all('title' in opt for opt in options2)