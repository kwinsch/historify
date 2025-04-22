"""
Tests for the comment command implementation.
"""
import pytest
import os
import csv
import shutil
from pathlib import Path
from click.testing import CliRunner
from unittest.mock import patch, MagicMock

from historify.cli import comment
from historify.changelog import Changelog, ChangelogError
from historify.config import RepositoryConfig
from historify.cli_init import init_repository
from historify.cli_comment import handle_comment_command
from historify.csv_manager import CSVManager, CSVError

class TestCommentImplementation:
    """Test the comment command implementation."""
    
    def setup_method(self):
        """Set up test environment."""
        self.runner = CliRunner()
        self.test_repo_path = Path("test_repo_comment").absolute()
        
        # Initialize a test repository
        if not self.test_repo_path.exists():
            init_repository(str(self.test_repo_path), "test-repo")
        
        # Create a dummy changelog file
        self.changes_dir = self.test_repo_path / "changes"
        self.changes_dir.mkdir(exist_ok=True)
        self.test_changelog = self.changes_dir / "changelog-2025-04-22.csv"
        
        # Create a header row for the CSV
        with open(self.test_changelog, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "timestamp", "transaction_type", "path", "category", 
                "size", "ctime", "mtime", "sha256", "blake3"
            ])
    
    def teardown_method(self):
        """Clean up test environment."""
        if self.test_repo_path.exists():
            shutil.rmtree(self.test_repo_path)
    
    def test_write_comment(self):
        """Test writing a comment to the changelog."""
        # Initialize changelog
        changelog = Changelog(str(self.test_repo_path))
        
        # Write a comment
        success = changelog.write_comment("Test comment message")
        assert success is True
        
        # Verify the comment was written
        with open(self.test_changelog, "r", newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert len(rows) == 1
            assert rows[0]["transaction_type"] == "comment"
            assert rows[0]["blake3"] == "Test comment message"
    
    def test_write_comment_no_changelog(self):
        """Test writing a comment with no open changelog."""
        # Remove the changelog file
        self.test_changelog.unlink()
        
        # Initialize changelog
        changelog = Changelog(str(self.test_repo_path))
        
        # Try to write a comment (should fail)
        with pytest.raises(ChangelogError, match="No open changelog file"):
            changelog.write_comment("Test comment message")
    
    @patch('historify.changelog.Changelog.write_comment')
    def test_handle_comment_command(self, mock_write_comment):
        """Test handle_comment_command function."""
        # Set up mock
        mock_write_comment.return_value = True
        
        # Run the command
        handle_comment_command(str(self.test_repo_path), "Test message")
        
        # Verify the comment was added
        mock_write_comment.assert_called_once_with("Test message")
    
    @patch('historify.cli_comment.Changelog')
    def test_cli_comment_command(self, mock_changelog_class):
        """Test CLI comment command."""
        # Set up mock
        mock_changelog = MagicMock()
        mock_changelog.get_current_changelog.return_value = self.test_changelog
        mock_changelog.write_comment.return_value = True
        mock_changelog_class.return_value = mock_changelog
        
        # Run the command
        with self.runner.isolated_filesystem():
            # Create a simple repository structure
            os.makedirs("repo_dir/db")
            os.makedirs("repo_dir/changes")
            with open("repo_dir/db/config", "w") as f:
                f.write("[repository]\nname = test-repo\n")
                
            result = self.runner.invoke(comment, ["Test comment", "repo_dir"])
            
            assert result.exit_code == 0
            assert "Comment added to changelog" in result.output
            
            # Verify the comment method was called
            mock_changelog_class.assert_called_once()
            mock_changelog.write_comment.assert_called_once_with("Test comment")
    
    @patch('historify.cli_comment.Changelog')
    def test_cli_comment_no_changelog(self, mock_changelog_class):
        """Test CLI comment command with no open changelog."""
        # Set up mock
        mock_changelog = MagicMock()
        mock_changelog.get_current_changelog.return_value = None
        mock_changelog_class.return_value = mock_changelog
        
        # Run the command
        with self.runner.isolated_filesystem():
            # Create a simple repository structure
            os.makedirs("repo_dir/db")
            os.makedirs("repo_dir/changes")
            with open("repo_dir/db/config", "w") as f:
                f.write("[repository]\nname = test-repo\n")
                
            result = self.runner.invoke(comment, ["Test comment", "repo_dir"])
            
            assert result.exit_code != 0
            assert "No open changelog file" in result.output
