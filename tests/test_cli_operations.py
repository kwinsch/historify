import pytest
from click.testing import CliRunner
from historify.cli import scan, verify, status

def test_scan_command():
    """Test the scan command."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(scan, ["."])
        assert result.exit_code == 0
        assert "Scanning for changes in" in result.output

def test_scan_with_category():
    """Test scan with category filter."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(scan, [".", "--category", "documents"])
        assert result.exit_code == 0
        assert "Scanning for changes in" in result.output
        assert "category: documents" in result.output

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
