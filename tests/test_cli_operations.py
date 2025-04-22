"""
Tests for operations-related commands (scan, verify, status, etc.).
"""
import pytest
import os
import csv
import shutil
from pathlib import Path
from click.testing import CliRunner
from unittest.mock import patch, MagicMock

from historify.cli import scan, verify, status
from historify.cli_scan import cli_scan_command, handle_scan_command

class TestOperationsImplementation:
    """Test operations-related command implementations."""
    
    def setup_method(self):
        """Set up test environment."""
        self.runner = CliRunner()
        self.test_repo_path = Path("test_repo_ops").absolute()
        
        # Create directory structure
        self.test_repo_path.mkdir(exist_ok=True, parents=True)
        self.db_dir = self.test_repo_path / "db"
        self.db_dir.mkdir(exist_ok=True)
        
        # Create a minimal config file with proper hash algorithms
        with open(self.db_dir / "config", "w") as f:
            f.write("[repository]\nname = test-repo\n")
            f.write("[hash]\nalgorithms = blake3,sha256\n")
            
        # Create changes directory
        self.changes_dir = self.test_repo_path / "changes"
        self.changes_dir.mkdir(exist_ok=True)
        
        # Create a dummy data directory with some files to scan
        self.data_dir = self.test_repo_path / "data"
        self.data_dir.mkdir(exist_ok=True)
        
        with open(self.data_dir / "test_file1.txt", "w") as f:
            f.write("Test content 1")
        
        with open(self.data_dir / "test_file2.txt", "w") as f:
            f.write("Test content 2")
            
        # Create test minisign key files for verify command
        self.key_dir = self.test_repo_path / "keys"
        self.key_dir.mkdir(exist_ok=True)
        
        self.minisign_key = self.key_dir / "historify.key"
        self.minisign_pub = self.key_dir / "historify.pub"
        
        # Create mock minisign key files
        with open(self.minisign_key, "w") as f:
            f.write("untrusted comment: minisign unencrypted secret key\n")
            f.write("TESTKEY123456789\n")
        
        with open(self.minisign_pub, "w") as f:
            f.write("untrusted comment: minisign public key\n")
            f.write("TESTPUB987654321\n")
            
        # Add minisign keys to config
        with open(self.db_dir / "config", "a") as f:
            f.write("[minisign]\n")
            f.write(f"key = {self.minisign_key}\n")
            f.write(f"pub = {self.minisign_pub}\n")
    
    def teardown_method(self):
        """Clean up test environment."""
        if self.test_repo_path.exists():
            shutil.rmtree(self.test_repo_path)
    
    def test_scan_command(self):
        """Test the scan command."""
        # Patch cli_scan_command to avoid actual execution
        with patch('historify.cli.cli_scan_command') as mock_scan:
            mock_scan.return_value = None
            
            result = self.runner.invoke(scan, [str(self.test_repo_path)])
            
            assert result.exit_code == 0
            mock_scan.assert_called_once_with(str(self.test_repo_path), None)
    
    def test_scan_command_with_category(self):
        """Test scan command with category."""
        # Patch cli_scan_command to avoid actual execution
        with patch('historify.cli.cli_scan_command') as mock_scan:
            mock_scan.return_value = None
            
            result = self.runner.invoke(scan, [str(self.test_repo_path), "--category", "data"])
            
            assert result.exit_code == 0
            mock_scan.assert_called_once_with(str(self.test_repo_path), "data")
    
    @patch('historify.cli_scan.RepositoryConfig')
    @patch('historify.cli_scan.Changelog')
    def test_handle_scan_command(self, mock_changelog, mock_config):
        """Test the handle_scan_command function."""
        # Setup mock config
        mock_config_instance = MagicMock()
        mock_config_instance.list_all.return_value = {
            "category.data.path": "data"
        }
        mock_config.return_value = mock_config_instance
        
        # Setup mock changelog
        mock_changelog_instance = MagicMock()
        mock_changelog_instance.get_current_changelog.return_value = Path("some_changelog.csv")
        mock_changelog_instance.csv_manager = MagicMock()
        mock_changelog.return_value = mock_changelog_instance
        
        # Mock scan_category function
        with patch('historify.cli_scan.scan_category') as mock_scan_category:
            mock_scan_category.return_value = {"new": 2, "modified": 0, "error": 0}
            
            # Run the function
            result = handle_scan_command(str(self.test_repo_path))
            
            # Check results
            assert isinstance(result, dict)
            assert "data" in result
            mock_scan_category.assert_called_once()
    
    @patch('historify.cli.cli_verify_command')
    def test_verify_command(self, mock_verify):
        """Test the verify command."""
        # Setup mock to return success
        mock_verify.return_value = 0
        
        result = self.runner.invoke(verify, [str(self.test_repo_path)])
        
        assert result.exit_code == 0
        mock_verify.assert_called_once_with(str(self.test_repo_path), False)
    
    @patch('historify.cli.cli_verify_command')
    def test_verify_full_chain(self, mock_verify):
        """Test verify with full-chain option."""
        # Setup mock to return success
        mock_verify.return_value = 0
        
        result = self.runner.invoke(verify, [str(self.test_repo_path), "--full-chain"])
        
        assert result.exit_code == 0
        mock_verify.assert_called_once_with(str(self.test_repo_path), True)
    
    def test_status_command(self):
        """Test the status command."""
        result = self.runner.invoke(status, [str(self.test_repo_path)])
        
        assert result.exit_code == 0
        assert "Status of" in result.output
    
    def test_status_with_category(self):
        """Test status with category."""
        result = self.runner.invoke(status, [str(self.test_repo_path), "--category", "data"])
        
        assert result.exit_code == 0
        assert "Status of" in result.output
        assert "for category 'data'" in result.output
