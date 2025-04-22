"""
Tests for the enhanced scan command implementation.
"""
import pytest
import os
import csv
import shutil
from pathlib import Path
from click.testing import CliRunner
from unittest.mock import patch, MagicMock

from historify.cli import scan
from historify.cli_scan import (
    scan_category,
    handle_scan_command,
    cli_scan_command,
    get_file_metadata,
    log_change,
    log_deletion
)
from historify.changelog import Changelog
from historify.csv_manager import CSVManager
from historify.cli_init import init_repository
from historify.config import RepositoryConfig

class TestEnhancedScan:
    """Test the enhanced scan command with change detection."""
    
    def setup_method(self):
        """Set up test environment."""
        self.runner = CliRunner()
        self.test_repo_path = Path("test_repo_enhanced_scan").absolute()
        
        # Initialize a test repository
        if not self.test_repo_path.exists():
            init_repository(str(self.test_repo_path), "test-repo")
        
        # Create a test data directory
        self.data_dir = self.test_repo_path / "data"
        self.data_dir.mkdir(exist_ok=True)
        
        # Add a test category
        config = RepositoryConfig(str(self.test_repo_path))
        config.set("category.test.path", "data")
        
        # Create a changes directory
        self.changes_dir = self.test_repo_path / "changes"
        self.changes_dir.mkdir(exist_ok=True)
        
        # Create initial changelog file
        self.changelog = self.changes_dir / "changelog-2025-04-22.csv"
        with open(self.changelog, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "timestamp", "transaction_type", "path", "category", 
                "size", "ctime", "mtime", "sha256", "blake3"
            ])
    
    def teardown_method(self):
        """Clean up test environment."""
        if self.test_repo_path.exists():
            shutil.rmtree(self.test_repo_path)
    
    def test_get_file_metadata(self):
        """Test getting file metadata."""
        # Create a test file
        test_file = self.data_dir / "test.txt"
        with open(test_file, "w") as f:
            f.write("Test content")
        
        metadata = get_file_metadata(test_file)
        
        assert metadata["size"] == str(test_file.stat().st_size)
        assert "ctime" in metadata
        assert "mtime" in metadata
        assert "blake3" in metadata
        assert "sha256" in metadata
    
    def test_log_change(self):
        """Test logging a file change."""
        # Create a test changelog
        changelog = Changelog(str(self.test_repo_path))
        
        # Create a test file
        test_file = self.data_dir / "log_test.txt"
        with open(test_file, "w") as f:
            f.write("Test content")
        
        # Get metadata
        metadata = get_file_metadata(test_file)
        
        # Log a new file
        log_change(changelog, "new", "log_test.txt", "test", metadata)
        
        # Verify the entry was added
        with open(self.changelog, "r", newline="") as f:
            reader = csv.DictReader(f)
            entries = list(reader)
            
            assert len(entries) >= 1
            assert entries[-1]["transaction_type"] == "new"
            assert entries[-1]["path"] == "log_test.txt"
            assert entries[-1]["category"] == "test"
    
    def test_scan_new_file(self):
        """Test scanning a new file."""
        # Create a test file
        test_file = self.data_dir / "new_file.txt"
        with open(test_file, "w") as f:
            f.write("New file content")
        
        # Get a changelog object
        changelog = Changelog(str(self.test_repo_path))
        
        # Scan the category
        results = scan_category(self.test_repo_path, "test", self.data_dir, changelog)
        
        # Verify results
        assert results["new"] >= 1
        
        # Verify the changelog entry
        with open(self.changelog, "r", newline="") as f:
            reader = csv.DictReader(f)
            entries = list(reader)
            
            # Find entries for our test file
            new_entries = [e for e in entries if e["path"] == "new_file.txt"]
            assert len(new_entries) == 1
            assert new_entries[0]["transaction_type"] == "new"
    
    def test_scan_changed_file(self):
        """Test scanning a changed file."""
        # Create a test file and log it
        test_file = self.data_dir / "changed_file.txt"
        with open(test_file, "w") as f:
            f.write("Original content")
        
        # Get a changelog object
        changelog = Changelog(str(self.test_repo_path))
        
        # First scan to record the file
        scan_category(self.test_repo_path, "test", self.data_dir, changelog)
        
        # Modify the file
        with open(test_file, "w") as f:
            f.write("Modified content")
        
        # Scan again
        results = scan_category(self.test_repo_path, "test", self.data_dir, changelog)
        
        # Verify results
        assert results["changed"] >= 1
        
        # Verify the changelog entries
        with open(self.changelog, "r", newline="") as f:
            reader = csv.DictReader(f)
            entries = list(reader)
            
            # Find entries for our test file
            file_entries = [e for e in entries if e["path"] == "changed_file.txt"]
            assert len(file_entries) == 2
            assert file_entries[0]["transaction_type"] == "new"
            assert file_entries[1]["transaction_type"] == "changed"
    
    def test_scan_moved_file(self):
        """Test scanning a moved file."""
        # Create a test file and log it
        original_file = self.data_dir / "original_location.txt"
        with open(original_file, "w") as f:
            f.write("File to be moved")
        
        # Get a changelog object
        changelog = Changelog(str(self.test_repo_path))
        
        # First scan to record the file
        scan_category(self.test_repo_path, "test", self.data_dir, changelog)
        
        # Move the file
        new_file = self.data_dir / "new_location.txt"
        shutil.move(original_file, new_file)
        
        # Scan again
        results = scan_category(self.test_repo_path, "test", self.data_dir, changelog)
        
        # Verify results
        assert results["moved"] >= 1
        assert results["deleted"] >= 0  # May be 0 if move was detected properly
        
        # Verify the changelog entries
        with open(self.changelog, "r", newline="") as f:
            reader = csv.DictReader(f)
            entries = list(reader)
            
            # Find entries for our test files
            new_entries = [e for e in entries if e["path"] == "new_location.txt"]
            assert len(new_entries) > 0
            # Last entry should be a move
            assert new_entries[-1]["transaction_type"] == "move"
            # The blake3 field should contain the old path
            assert new_entries[-1]["blake3"] == "original_location.txt"
    
    def test_scan_deleted_file(self):
        """Test scanning a deleted file."""
        # Create a test file and log it
        test_file = self.data_dir / "deleted_file.txt"
        with open(test_file, "w") as f:
            f.write("File to be deleted")
        
        # Get a changelog object
        changelog = Changelog(str(self.test_repo_path))
        
        # First scan to record the file
        scan_category(self.test_repo_path, "test", self.data_dir, changelog)
        
        # Delete the file
        test_file.unlink()
        
        # Scan again
        results = scan_category(self.test_repo_path, "test", self.data_dir, changelog)
        
        # Verify results
        assert results["deleted"] >= 1
        
        # Verify the changelog entries
        with open(self.changelog, "r", newline="") as f:
            reader = csv.DictReader(f)
            entries = list(reader)
            
            # Find entries for our test file
            file_entries = [e for e in entries if e["path"] == "deleted_file.txt"]
            assert len(file_entries) == 2
            assert file_entries[0]["transaction_type"] == "new"
            assert file_entries[1]["transaction_type"] == "deleted"
    
    def test_handle_scan_command(self):
        """Test the handle_scan_command function."""
        # Create test files
        test_file1 = self.data_dir / "test1.txt"
        test_file2 = self.data_dir / "test2.txt"
        
        with open(test_file1, "w") as f:
            f.write("Test content 1")
        with open(test_file2, "w") as f:
            f.write("Test content 2")
        
        # Run the scan command
        results = handle_scan_command(str(self.test_repo_path))
        
        # Verify results
        assert "test" in results
        assert results["test"]["new"] >= 2
    
    def test_cli_scan_command(self):
        """Test the CLI scan command."""
        # Create test files
        test_file = self.data_dir / "cli_test.txt"
        with open(test_file, "w") as f:
            f.write("CLI test content")
        
        # Mock the handle_scan_command function to return known results
        with patch('historify.cli_scan.handle_scan_command') as mock_handle:
            mock_handle.return_value = {
                "test": {
                    "new": 1, 
                    "changed": 0, 
                    "unchanged": 0, 
                    "deleted": 0, 
                    "moved": 0,
                    "error": 0
                }
            }
            
            # Run the CLI command
            result = self.runner.invoke(scan, [str(self.test_repo_path)])
            
            # Verify the output
            assert result.exit_code == 0
            assert "Scanning repository" in result.output
            assert "New: 1" in result.output
            
            # Test with category filter
            result = self.runner.invoke(scan, [str(self.test_repo_path), "--category", "test"])
            
            assert result.exit_code == 0
            assert "category: test" in result.output

    def test_full_workflow(self):
        """Test a complete workflow with multiple changes."""
        # Get a changelog object
        changelog = Changelog(str(self.test_repo_path))
        
        # 1. Create new files
        file1 = self.data_dir / "workflow1.txt"
        file2 = self.data_dir / "workflow2.txt"
        
        with open(file1, "w") as f:
            f.write("Workflow file 1")
        with open(file2, "w") as f:
            f.write("Workflow file 2")
        
        # 2. First scan - should detect new files
        results1 = scan_category(self.test_repo_path, "test", self.data_dir, changelog)
        assert results1["new"] >= 2
        
        # 3. Modify file1
        with open(file1, "w") as f:
            f.write("Modified workflow file 1")
        
        # 4. Move file2
        file2_new = self.data_dir / "workflow2_moved.txt"
        shutil.move(file2, file2_new)
        
        # 5. Create file3
        file3 = self.data_dir / "workflow3.txt"
        with open(file3, "w") as f:
            f.write("Workflow file 3")
        
        # 6. Second scan - should detect changed, moved, and new files
        results2 = scan_category(self.test_repo_path, "test", self.data_dir, changelog)
        assert results2["changed"] >= 1
        assert results2["moved"] >= 1
        assert results2["new"] >= 1
        
        # 7. Delete file1
        file1.unlink()
        
        # 8. Third scan - should detect deletion
        results3 = scan_category(self.test_repo_path, "test", self.data_dir, changelog)
        assert results3["deleted"] >= 1
        
        # Verify the complete changelog
        with open(self.changelog, "r", newline="") as f:
            reader = csv.DictReader(f)
            entries = list(reader)
            
            # We should have entries for all the operations
            workflows = [e for e in entries if "workflow" in e["path"]]
            
            # Count each transaction type
            transaction_counts = {}
            for entry in workflows:
                t_type = entry["transaction_type"]
                transaction_counts[t_type] = transaction_counts.get(t_type, 0) + 1
            
            # Verify we have the expected operations
            assert transaction_counts.get("new", 0) >= 3
            assert transaction_counts.get("changed", 0) >= 1
            assert transaction_counts.get("move", 0) >= 1
            assert transaction_counts.get("deleted", 0) >= 1
