"""
Tests for the status command implementation.
"""
import pytest
import os
import csv
import shutil
from pathlib import Path
from click.testing import CliRunner
from unittest.mock import patch, MagicMock

from historify.cli import status
from historify.cli_status import (
    handle_status_command, 
    get_category_status,
    get_changelog_status,
    cli_status_command,
    StatusError
)
from historify.config import RepositoryConfig
from historify.cli_init import init_repository

class TestStatusImplementation:
    """Test the status command implementation."""
    
    def setup_method(self):
        """Set up test environment."""
        self.runner = CliRunner()
        self.test_repo_path = Path("test_repo_status").absolute()
        
        # Initialize a test repository
        if not self.test_repo_path.exists():
            init_repository(str(self.test_repo_path), "test-repo")
        
        # Create some sample data directories and files
        self.docs_dir = self.test_repo_path / "docs"
        self.docs_dir.mkdir(exist_ok=True)
        
        # Create some sample files
        (self.docs_dir / "README.md").write_text("# Test Repository")
        (self.docs_dir / "guide.txt").write_text("This is a test guide")
        
        # Create a changes directory with changelogs
        self.changes_dir = self.test_repo_path / "changes"
        self.changes_dir.mkdir(exist_ok=True)
        
        # Create a test changelog
        self.test_changelog = self.changes_dir / "changelog-2025-04-22.csv"
        with open(self.test_changelog, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "timestamp", "transaction_type", "path", "category", 
                "size", "ctime", "mtime", "sha256", "blake3"
            ])
            writer.writerow([
                "2025-04-22 10:00:00 UTC", "closing", "db/seed.bin", "", 
                "", "", "", "", "test_hash_value"
            ])
            writer.writerow([
                "2025-04-22 10:05:00 UTC", "new", "docs/README.md", "docs", 
                "16", "2025-04-22", "2025-04-22", "sha256_value", "blake3_value"
            ])
        
        # Configure the repository
        config = RepositoryConfig(str(self.test_repo_path))
        config.set("category.docs.path", "docs")
        config.set("repository.created", "2025-04-22T10:00:00")
    
    def teardown_method(self):
        """Clean up test environment."""
        if self.test_repo_path.exists():
            shutil.rmtree(self.test_repo_path)
    
    def test_get_category_status(self):
        """Test getting status for a category."""
        # Test with existing category
        result = get_category_status(
            str(self.test_repo_path),
            "docs",
            self.docs_dir
        )
        
        assert result["name"] == "docs"
        assert result["exists"] is True
        assert result["is_external"] is False
        assert result["file_count"] == 2
        assert result["total_size"] > 0
        
        # Test with non-existent category
        nonexistent_dir = self.test_repo_path / "nonexistent"
        result = get_category_status(
            str(self.test_repo_path),
            "nonexistent",
            nonexistent_dir
        )
        
        assert result["name"] == "nonexistent"
        assert result["exists"] is False
        assert result["file_count"] == 0
        assert result["total_size"] == 0
    
    def test_get_changelog_status(self):
        """Test getting changelog status."""
        result = get_changelog_status(str(self.test_repo_path))
        
        assert result["changelog_count"] == 1
        assert result["current_changelog"] == "changelog-2025-04-22.csv"
        assert result["signed_count"] == 0  # No signatures yet
        assert result["recent_changes"] > 0  # Should have recent changes
        
        # Create a signed changelog
        signed_changelog = self.changes_dir / "changelog-2025-04-01.csv"
        signed_changelog.touch()
        sig_file = signed_changelog.with_suffix(".csv.minisig")
        sig_file.touch()
        
        # Check status again
        result = get_changelog_status(str(self.test_repo_path))
        assert result["changelog_count"] == 2
        assert result["signed_count"] == 1
    
    def test_handle_status_command(self):
        """Test handling the status command."""
        # Test with all categories
        result = handle_status_command(str(self.test_repo_path))
        
        assert "repository" in result
        assert result["repository"]["name"] == "test-repo"
        assert "categories" in result
        assert "docs" in result["categories"]
        assert "changelog" in result
        assert result["changelog"]["changelog_count"] == 1
        
        # Test with specific category
        result = handle_status_command(str(self.test_repo_path), "docs")
        
        assert "categories" in result
        assert "docs" in result["categories"]
        assert len(result["categories"]) == 1  # Only the docs category
    
    def test_cli_status_command(self):
        """Test the CLI status command handler."""
        # Mock the required functions to prevent errors in the test
        with patch('historify.cli_status.handle_status_command') as mock_handle:
            # Setup mock to return a valid status dictionary
            mock_handle.return_value = {
                "repository": {
                    "name": "test-repo",
                    "created": "2025-04-22",
                    "path": str(self.test_repo_path)
                },
                "changelog": {
                    "current_changelog": "changelog-2025-04-22.csv",
                    "changelog_count": 1,
                    "signed_count": 0,
                    "recent_changes": 2,
                    "last_activity": "2025-04-22 10:05:00 UTC"
                },
                "categories": {
                    "docs": {
                        "name": "docs",
                        "path": str(self.docs_dir),
                        "is_external": False,
                        "exists": True,
                        "file_count": 2,
                        "total_size": 100
                    }
                }
            }
            
            # Call the function
            result = cli_status_command(str(self.test_repo_path))
            
            assert result == 0  # Success
            mock_handle.assert_called_once_with(str(self.test_repo_path), None)
    
    def test_cli_status_command_with_category(self):
        """Test CLI status command with a specific category."""
        # Mock the required functions to prevent errors in the test
        with patch('historify.cli_status.handle_status_command') as mock_handle:
            # Setup mock to return a valid status dictionary
            mock_handle.return_value = {
                "repository": {
                    "name": "test-repo",
                    "created": "2025-04-22",
                    "path": str(self.test_repo_path)
                },
                "changelog": {
                    "current_changelog": "changelog-2025-04-22.csv",
                    "changelog_count": 1,
                    "signed_count": 0,
                    "recent_changes": 2,
                    "last_activity": "2025-04-22 10:05:00 UTC"
                },
                "categories": {
                    "docs": {
                        "name": "docs",
                        "path": str(self.docs_dir),
                        "is_external": False,
                        "exists": True,
                        "file_count": 2,
                        "total_size": 100
                    }
                }
            }
            
            # Call the function
            result = cli_status_command(str(self.test_repo_path), "docs")
            
            assert result == 0  # Success
            mock_handle.assert_called_once_with(str(self.test_repo_path), "docs")
    
    def test_cli_command(self):
        """Test the status command through the main CLI."""
        # Patch the CLI function directly from cli_status instead of cli
        with patch('historify.cli_status.cli_status_command') as mock_status:
            mock_status.return_value = 0
            
            # Mock the status function import in cli.py
            with patch('historify.cli.cli_status_command', mock_status):
                result = self.runner.invoke(status, [str(self.test_repo_path)])
                
                assert result.exit_code == 0
                mock_status.assert_called_once_with(str(self.test_repo_path), None)
                
                # Test with category filter
                result = self.runner.invoke(status, [str(self.test_repo_path), "--category", "docs"])
                
                assert result.exit_code == 0
                mock_status.assert_called_with(str(self.test_repo_path), "docs")
