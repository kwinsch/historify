import pytest
import os
from pathlib import Path
from click.testing import CliRunner
from unittest.mock import patch

from historify.cli import scan, verify, status

def test_scan_command():
    """Test the scan command."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        # Create a minimal repository structure for the test
        os.makedirs("repo_dir/db")
        os.makedirs("repo_dir/changes")
        
        # Mock the actual scan implementation to avoid errors
        with patch('historify.cli.cli_scan_command') as mock_scan_command:
            mock_scan_command.return_value = None  # Ensure it returns properly
            
            result = runner.invoke(scan, ["repo_dir"])
            
            assert result.exit_code == 0
            mock_scan_command.assert_called_once_with("repo_dir", None)

def test_scan_with_category():
    """Test scan with category filter."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        # Create a minimal repository structure for the test
        os.makedirs("repo_dir/db")
        os.makedirs("repo_dir/changes")
        
        # Mock the actual scan implementation to avoid errors
        with patch('historify.cli.cli_scan_command') as mock_scan_command:
            mock_scan_command.return_value = None  # Ensure it returns properly
            
            result = runner.invoke(scan, ["repo_dir", "--category", "documents"])
            
            assert result.exit_code == 0
            mock_scan_command.assert_called_once_with("repo_dir", "documents")

def test_verify_command():
    """Test the verify command."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(verify, ["."])
        assert result.exit_code == 0
        assert "Verifying recent logs in" in result.output

def test_verify_full_chain():
    """Test verify with full-chain option."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(verify, [".", "--full-chain"])
        assert result.exit_code == 0
        assert "Verifying full chain in" in result.output

def test_status_command():
    """Test the status command."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(status, ["."])
        assert result.exit_code == 0
        assert "Status of" in result.output

def test_status_with_category():
    """Test status with category filter."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(status, [".", "--category", "documents"])
        assert result.exit_code == 0
        assert "Status of" in result.output
        assert "for category 'documents'" in result.output
