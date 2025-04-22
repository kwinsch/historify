"""
Tests for the scan command functionality.
"""
import pytest
import os
from pathlib import Path
from click.testing import CliRunner
from unittest.mock import patch

from historify.cli import scan

def test_cli_scan_command():
    """Test CLI scan command through the main CLI interface."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        # Create a minimal test environment
        os.makedirs("test_repo/db")
        with open("test_repo/db/config", "w") as f:
            f.write("[repository]\nname = test-repo\n")
            
        # Use the correct patching target
        with patch('historify.cli.cli_scan_command') as mock_scan_command:
            mock_scan_command.return_value = None
            
            result = runner.invoke(scan, ["test_repo"])
            
            assert result.exit_code == 0
            mock_scan_command.assert_called_once_with("test_repo", None)

def test_cli_scan_command_with_category():
    """Test CLI scan command with category filter through the main CLI interface."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        # Create a minimal test environment
        os.makedirs("test_repo/db")
        with open("test_repo/db/config", "w") as f:
            f.write("[repository]\nname = test-repo\n")
            
        # Use the correct patching target
        with patch('historify.cli.cli_scan_command') as mock_scan_command:
            mock_scan_command.return_value = None
            
            result = runner.invoke(scan, ["test_repo", "--category", "docs"])
            
            assert result.exit_code == 0
            mock_scan_command.assert_called_once_with("test_repo", "docs")