import pytest
import logging
from click.testing import CliRunner
from historify.cli import cli, main, init

def test_cli_help():
    """Test the CLI shows help information."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Historify: track file history with cryptographic integrity verification" in result.output
    assert "Commands:" in result.output

def test_cli_verbose():
    """Test the CLI verbose mode."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        # First initialize a repo
        runner.invoke(init, ["./test_repo", "--name", "test-repo"])
        
        # Then use it with verbose mode
        result = runner.invoke(cli, ["--verbose", "check-config", "./test_repo"])
        assert result.exit_code == 0
        assert "Verbose mode enabled" in result.output

def test_main_function():
    """Test the main function doesn't crash."""
    # This is a very minimal test just to check that the function exists
    assert callable(main)
