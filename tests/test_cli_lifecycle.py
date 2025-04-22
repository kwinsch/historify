import pytest
from click.testing import CliRunner
from historify.cli import start_transaction, closing

def test_start_command():
    """Test the start command."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(start_transaction, ["."])
        assert result.exit_code == 0
        assert "Starting new transaction period in" in result.output

def test_closing_command():
    """Test the closing command."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(closing, ["."])
        assert result.exit_code == 0
        assert "Closing current changelog in" in result.output
