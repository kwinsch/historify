import pytest
from click.testing import CliRunner
from unittest.mock import patch, MagicMock
from pathlib import Path
from historify.cli import log, comment

def test_log_command():
    """Test the log command."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(log, ["."])
        assert result.exit_code == 0
        assert "Showing logs for" in result.output

def test_log_with_file():
    """Test log with file option."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(log, [".", "--file", "changelog-2025-04.csv"])
        assert result.exit_code == 0
        assert "Showing logs for" in result.output
        assert "file: changelog-2025-04.csv" in result.output

def test_log_with_category():
    """Test log with category filter."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(log, [".", "--category", "documents"])
        assert result.exit_code == 0
        assert "Showing logs for" in result.output
        assert "category: documents" in result.output

@patch('historify.cli_comment.Changelog')
def test_comment_command(mock_changelog_class):
    """Test the comment command."""
    # Set up mock
    mock_changelog = MagicMock()
    # Use a Path object instead of a string since the code accesses .name
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
