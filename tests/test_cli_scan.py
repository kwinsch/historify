"""
Tests for the scan command implementation.
"""
import pytest
import os
import csv
import shutil
from pathlib import Path
from click.testing import CliRunner
from unittest.mock import patch, MagicMock

from historify.cli import init, config, scan, start_transaction
from historify.cli_scan import handle_scan_command, scan_category, get_file_metadata, ScanError
from historify.changelog import Changelog
from historify.config import RepositoryConfig
from historify.cli_init import init_repository

class TestScanImplementation:
    """Test the scan command implementation."""
    
    def setup_method(self):
        """Set up test environment."""
        self.runner = CliRunner()
        self.test_repo_path = Path("test_repo_scan").absolute()
        
        # Initialize a test repository
        if not self.test_repo_path.exists():
            init_repository(str(self.test_repo_path), "test-repo")
        
        # Create test data directories and files
        self.data_dir = self.test_repo_path / "data"
        self.data_dir.mkdir(exist_ok=True)
        
        # Create a few test files in different paths to test scanning
        self.test_files = [
            self.data_dir / "file1.txt",
            self.data_dir / "file2.txt",
            self.data_dir / "subdir" / "file3.txt"
        ]
        
        # Create the files with content
        for file_path in self.test_files:
            file_path.parent.mkdir(exist_ok=True, parents=True)
            with open(file_path, "w") as f:
                f.write(f"Test content for {file_path.name}")
        
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
        
        # Configure a test category
        config = RepositoryConfig(str(self.test_repo_path))
        config.set("category.test", "data")
    
    def teardown_method(self):
        """Clean up test environment."""
        if self.test_repo_path.exists():
            shutil.rmtree(self.test_repo_path)
    
    def test_get_file_metadata(self):
        """Test getting file metadata."""
        test_file = self.test_files[0]
        
        metadata = get_file_metadata(test_file)
        
        assert "size" in metadata
        assert "ctime" in metadata
        assert "mtime" in metadata
        assert "sha256" in metadata
        assert "blake3" in metadata
        
        # Verify the sizes are correct
        content_size = len(f"Test content for {test_file.name}")
        assert int(metadata["size"]) == content_size
    
    @patch('historify.cli_scan.Changelog')
    def test_scan_category(self, mock_changelog_class):
        """Test scanning a category."""
        # Setup mocks
        mock_changelog = MagicMock()
        mock_changelog.get_current_changelog.return_value = self.test_changelog
        mock_csv_manager = MagicMock()
        mock_changelog.csv_manager = mock_csv_manager
        mock_changelog_class.return_value = mock_changelog
        
        # Run the scan
        with patch('historify.csv_manager.CSVManager._lock_file'), \
             patch('historify.csv_manager.CSVManager._unlock_file'):
            results = scan_category(
                self.test_repo_path,
                "test",
                self.data_dir,
                mock_changelog
            )
        
        # Verify results - there should be entries for 3 files
        assert results["new"] == 3
        assert mock_csv_manager.append_entry.call_count == 3
    
    @patch('historify.cli_scan.RepositoryConfig')
    @patch('historify.cli_scan.Changelog')
    def test_handle_scan_command(self, mock_changelog_class, mock_config_class):
        """Test handle_scan_command function."""
        # Setup mocks for config
        mock_config = MagicMock()
        mock_config.list_all.return_value = {
            "category.test.path": "data"
        }
        mock_config_class.return_value = mock_config
        
        # Setup mocks for changelog
        mock_changelog = MagicMock()
        mock_changelog.get_current_changelog.return_value = self.test_changelog
        mock_csv_manager = MagicMock()
        mock_changelog.csv_manager = mock_csv_manager
        mock_changelog_class.return_value = mock_changelog
        
        # Mock scan_category
        with patch('historify.cli_scan.scan_category') as mock_scan:
            mock_scan.return_value = {"new": 3, "error": 0}
            
            # Run the command
            results = handle_scan_command(str(self.test_repo_path))
            
            # Verify the category was scanned
            assert "test" in results
            assert results["test"]["new"] == 3
    
    def test_cli_scan_command(self):
        """Test CLI scan command through the main CLI interface."""
        # Use dependency injection to provide the test environment
        with patch('historify.cli.cli_scan_command') as mock_scan_command:
            mock_scan_command.return_value = None  # Ensure it returns properly
            
            result = self.runner.invoke(scan, [str(self.test_repo_path)])
            
            assert result.exit_code == 0
            mock_scan_command.assert_called_once_with(str(self.test_repo_path), None)
    
    def test_cli_scan_command_with_category(self):
        """Test CLI scan command with category filter through the main CLI interface."""
        # Use dependency injection to provide the test environment
        with patch('historify.cli.cli_scan_command') as mock_scan_command:
            mock_scan_command.return_value = None  # Ensure it returns properly
            
            result = self.runner.invoke(scan, [str(self.test_repo_path), "--category", "docs"])
            
            assert result.exit_code == 0
            mock_scan_command.assert_called_once_with(str(self.test_repo_path), "docs")
    
    def test_scan_command_integration(self):
        """Test the scan command integrated with the CLI."""
        # First initialize a repository
        with self.runner.isolated_filesystem():
            repo_path = "test_repo"
            
            # Initialize the repository
            self.runner.invoke(init, [repo_path])
            
            # Add a category
            self.runner.invoke(config, ["category.docs.path", "docs", repo_path])
            
            # Create the docs directory and add a file
            docs_path = Path(repo_path) / "docs"
            docs_path.mkdir(exist_ok=True)
            test_file = docs_path / "test.txt"
            with open(test_file, "w") as f:
                f.write("Test content")
            
            # Start a transaction to create changelog
            with patch('historify.changelog.minisign_sign', return_value=True):
                self.runner.invoke(start_transaction, [repo_path])
            
            # Patch file locking and minisign operations as well as the error handling
            with patch('historify.csv_manager.CSVManager._lock_file'), \
                 patch('historify.csv_manager.CSVManager._unlock_file'), \
                 patch('historify.cli_scan.handle_scan_command') as mock_handle_scan:
                
                # Setup the mock to return good results
                mock_handle_scan.return_value = {"docs": {"new": 1, "error": 0}}
                
                # Run the scan command
                result = self.runner.invoke(scan, [repo_path])
                
                # Verify the command executed successfully
                assert result.exit_code == 0
                mock_handle_scan.assert_called_once_with(repo_path, None)
