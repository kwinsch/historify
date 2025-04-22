import pytest
from click.testing import CliRunner
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

def test_comment_command():
    """Test the comment command."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(comment, ["Test comment message", "."])
        assert result.exit_code == 0
        assert "Adding comment to" in result.output
        assert "Test comment message" in result.output
