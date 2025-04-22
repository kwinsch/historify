"""
Tests for the log command implementation.
"""
import pytest
import os
import csv
import shutil
from pathlib import Path
from click.testing import CliRunner
from unittest.mock import patch, MagicMock

from historify.cli import log, comment
from historify.cli_log import handle_log_command, read_log_entries, display_log_entry
from historify.changelog import Changelog, ChangelogError
from historify.csv_manager import CSVManager

class TestLogImplementation:
    """Test the log command implementation."""
    
    def setup_method(self):
        """Set up test environment."""
        self.runner = CliRunner()
        self.test_repo_path = Path("test_repo_log").absolute()
        
        # Create directory structure
        self.test_repo_path.mkdir(exist_ok=True, parents=True)
        self.db_dir = self.test_repo_path / "db"
        self.db_dir.mkdir(exist_ok=True)
        
        # Create a minimal config file
        with open(self.db_dir / "config", "w") as f:
            f.write("[repository]\nname = test-repo\n")
            
        # Create changes directory
        self.changes_dir = self.test_repo_path / "changes"
        self.changes_dir.mkdir(exist_ok=True)
        
        # Create test changelog files
        self.create_test_changelog("changelog-2025-04-01.csv", [
            {"timestamp": "2025-04-01 10:00:00 UTC", "transaction_type": "closing", "path": "db/seed.bin", 
             "category": "", "size": "", "ctime": "", "mtime": "", "sha256": "", "blake3": "seed_hash_value"},
            {"timestamp": "2025-04-01 10:05:00 UTC", "transaction_type": "new", "path": "docs/readme.md", 
             "category": "docs", "size": "1024", "ctime": "2025-04-01", "mtime": "2025-04-01", 
             "sha256": "sha256_hash_value", "blake3": "blake3_hash_value"}
        ])
        
        self.create_test_changelog("changelog-2025-04-15.csv", [
            {"timestamp": "2025-04-15 09:00:00 UTC", "transaction_type": "closing", "path": "changes/changelog-2025-04-01.csv", 
             "category": "", "size": "", "ctime": "", "mtime": "", "sha256": "", "blake3": "previous_log_hash"},
            {"timestamp": "2025-04-15 09:15:00 UTC", "transaction_type": "new", "path": "src/main.py", 
             "category": "source", "size": "2048", "ctime": "2025-04-15", "mtime": "2025-04-15", 
             "sha256": "sha256_hash_value2", "blake3": "blake3_hash_value2"},
            {"timestamp": "2025-04-15 10:30:00 UTC", "transaction_type": "comment", "path": "", 
             "category": "", "size": "", "ctime": "", "mtime": "", "sha256": "", "blake3": "Added main implementation"}
        ])
        
        self.create_test_changelog("changelog-2025-04-22.csv", [
            {"timestamp": "2025-04-22 08:00:00 UTC", "transaction_type": "closing", "path": "changes/changelog-2025-04-15.csv", 
             "category": "", "size": "", "ctime": "", "mtime": "", "sha256": "", "blake3": "previous_log_hash2"},
            {"timestamp": "2025-04-22 08:30:00 UTC", "transaction_type": "config", "path": "minisign.key", 
             "category": "", "size": "", "ctime": "", "mtime": "", "sha256": "", "blake3": "/home/user/.minisign/key"},
            {"timestamp": "2025-04-22 09:45:00 UTC", "transaction_type": "move", "path": "src/app.py", 
             "category": "source", "size": "2048", "ctime": "2025-04-22", "mtime": "2025-04-22", 
             "sha256": "sha256_hash_value2", "blake3": "src/main.py"}
        ])
    
    def teardown_method(self):
        """Clean up test environment."""
        if self.test_repo_path.exists():
            shutil.rmtree(self.test_repo_path)
    
    def create_test_changelog(self, filename, entries):
        """Create a test changelog file with given entries."""
        filepath = self.changes_dir / filename
        with open(filepath, "w", newline="") as f:
            fieldnames = ["timestamp", "transaction_type", "path", "category", 
                         "size", "ctime", "mtime", "sha256", "blake3"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for entry in entries:
                writer.writerow(entry)
    
    def test_read_log_entries(self):
        """Test reading log entries from a file."""
        log_file = self.changes_dir / "changelog-2025-04-15.csv"
        
        # Initialize CSV manager
        csv_manager = CSVManager(str(self.test_repo_path))
        
        # Test reading all entries
        entries = csv_manager.read_entries(log_file)
        assert len(entries) == 3
        assert entries[0]["transaction_type"] == "closing"
        assert entries[1]["transaction_type"] == "new"
        assert entries[2]["transaction_type"] == "comment"
        
        # Test with category filter
        entries = csv_manager.read_entries(log_file)
        filtered_entries = [entry for entry in entries if entry["category"] == "source"]
        assert len(filtered_entries) == 1
        assert filtered_entries[0]["path"] == "src/main.py"
    
    @patch('historify.cli_log.click.echo')
    def test_display_log_entry(self, mock_echo):
        """Test displaying different types of log entries."""
        # Test display of closing entry
        closing_entry = {
            "timestamp": "2025-04-01 10:00:00 UTC", 
            "transaction_type": "closing", 
            "path": "db/seed.bin",
            "blake3": "seed_hash_value"
        }
        display_log_entry(1, closing_entry)
        # Assert echo was called with expected strings
        assert any("Entry #1" in args[0] for args, _ in mock_echo.call_args_list)
        assert any("Type: closing" in args[0] for args, _ in mock_echo.call_args_list)
        assert any("Previous file: db/seed.bin" in args[0] for args, _ in mock_echo.call_args_list)
        
        # Reset mock
        mock_echo.reset_mock()
        
        # Test display of comment entry
        comment_entry = {
            "timestamp": "2025-04-15 10:30:00 UTC", 
            "transaction_type": "comment", 
            "blake3": "Test comment"
        }
        display_log_entry(2, comment_entry)
        # Assert echo was called with expected strings
        assert any("Entry #2" in args[0] for args, _ in mock_echo.call_args_list)
        assert any("Type: comment" in args[0] for args, _ in mock_echo.call_args_list)
        assert any("Comment: Test comment" in args[0] for args, _ in mock_echo.call_args_list)
    
    @patch('historify.cli_log.Changelog')
    def test_handle_log_command_default(self, mock_changelog_class):
        """Test handling log command with default parameters."""
        # Set up mock
        mock_changelog = MagicMock()
        mock_changelog.changes_dir = self.changes_dir
        mock_changelog.get_current_changelog.return_value = self.changes_dir / "changelog-2025-04-22.csv"
        # Set up CSV manager mock
        mock_csv_manager = MagicMock()
        mock_changelog.csv_manager = mock_csv_manager
        mock_csv_manager.read_entries.return_value = [
            {"timestamp": "2025-04-22", "transaction_type": "closing"}
        ]
        mock_changelog_class.return_value = mock_changelog
        
        # Call the handler directly
        handle_log_command(str(self.test_repo_path))
        
        # Verify the correct changelog was used
        mock_changelog_class.assert_called_once()
        mock_changelog.get_current_changelog.assert_called_once()
    
    @patch('historify.cli_log.Changelog')
    def test_handle_log_command_with_file(self, mock_changelog_class):
        """Test handling log command with specific file parameter."""
        # Set up mock
        mock_changelog = MagicMock()
        mock_changelog.changes_dir = self.changes_dir
        # Set up CSV manager mock
        mock_csv_manager = MagicMock()
        mock_changelog.csv_manager = mock_csv_manager
        mock_csv_manager.read_entries.return_value = [
            {"timestamp": "2025-04-15", "transaction_type": "closing"}
        ]
        mock_changelog_class.return_value = mock_changelog
        
        # Call the handler directly with file parameter
        handle_log_command(str(self.test_repo_path), "2025-04-15")
        
        # Verify the correct changelog was used
        mock_changelog_class.assert_called_once()
        # get_current_changelog should not be called when file is specified
        mock_changelog.get_current_changelog.assert_not_called()
    
    @patch('historify.cli_log.Changelog')
    def test_handle_log_command_with_category(self, mock_changelog_class):
        """Test handling log command with category filter."""
        # Set up mock
        mock_changelog = MagicMock()
        mock_changelog.changes_dir = self.changes_dir
        mock_changelog.get_current_changelog.return_value = self.changes_dir / "changelog-2025-04-15.csv"
        # Set up CSV manager mock
        mock_csv_manager = MagicMock()
        mock_changelog.csv_manager = mock_csv_manager
        entries = [
            {"timestamp": "2025-04-15", "transaction_type": "closing", "category": ""},
            {"timestamp": "2025-04-15", "transaction_type": "new", "category": "source"}
        ]
        mock_csv_manager.read_entries.return_value = entries
        mock_changelog_class.return_value = mock_changelog
        
        # Call the handler directly with category parameter
        handle_log_command(str(self.test_repo_path), None, "source")
        
        # Verify the correct changelog was used
        mock_changelog_class.assert_called_once()
        mock_changelog.get_current_changelog.assert_called_once()
    
    def test_cli_log_command(self):
        """Test CLI log command."""
        with patch('historify.cli_log.handle_log_command') as mock_handler:
            result = self.runner.invoke(log, [str(self.test_repo_path)])
            
            assert result.exit_code == 0
            mock_handler.assert_called_once_with(str(self.test_repo_path), None, None)
    
    def test_cli_log_command_with_file(self):
        """Test CLI log command with file parameter."""
        with patch('historify.cli_log.handle_log_command') as mock_handler:
            result = self.runner.invoke(log, [str(self.test_repo_path), "--file", "2025-04-15"])
            
            assert result.exit_code == 0
            mock_handler.assert_called_once_with(str(self.test_repo_path), "2025-04-15", None)
    
    def test_cli_log_command_with_category(self):
        """Test CLI log command with category parameter."""
        with patch('historify.cli_log.handle_log_command') as mock_handler:
            result = self.runner.invoke(log, [str(self.test_repo_path), "--category", "source"])
            
            assert result.exit_code == 0
            mock_handler.assert_called_once_with(str(self.test_repo_path), None, "source")

@patch('historify.cli_comment.Changelog')
def test_comment_command(mock_changelog_class):
    """Test the comment command."""
    # Set up mock
    mock_changelog = MagicMock()
    mock_changelog.get_current_changelog.return_value = Path("changelog-2025-04-22.csv")
    mock_changelog.write_comment.return_value = True
    mock_changelog_class.return_value = mock_changelog
    
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(comment, ["Test comment message", "."])
        
        assert result.exit_code == 0
        assert "Comment added to changelog" in result.output or "Adding comment to" in result.output
        
        # Verify the comment method was called
        mock_changelog_class.assert_called_once()
        mock_changelog.write_comment.assert_called_once_with("Test comment message")
