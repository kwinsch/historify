"""
Tests for the CSV Manager implementation.
"""
import pytest
import os
import csv
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open

from historify.csv_manager import CSVManager, CSVError

class TestCSVManager:
    """Test the CSV Manager implementation."""
    
    def setup_method(self):
        """Set up test environment."""
        self.test_dir = Path(tempfile.mkdtemp())
        self.csv_manager = CSVManager(str(self.test_dir))
        
        # Use custom field names for test CSV
        self.test_fields = ["key", "value"]
        
        # Create a test CSV file
        self.test_csv = self.test_dir / "test.csv"
        with open(self.test_csv, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=self.test_fields)
            writer.writeheader()
            writer.writerow({"key": "test1", "value": "value1"})
            writer.writerow({"key": "test2", "value": "value2"})
    
    def teardown_method(self):
        """Clean up test environment."""
        shutil.rmtree(self.test_dir)
    
    def test_init(self):
        """Test initialization of CSV Manager."""
        assert self.csv_manager.repo_path == self.test_dir
        assert len(self.csv_manager.required_fields) > 0
    
    def test_read_entries(self):
        """Test reading entries from a CSV file."""
        # Patch the lock and unlock methods to avoid fcntl issues in tests
        with patch('historify.csv_manager.CSVManager._lock_file'), \
             patch('historify.csv_manager.CSVManager._unlock_file'):
            entries = self.csv_manager.read_entries(self.test_csv)
            assert len(entries) == 2
            assert entries[0]["key"] == "test1"
            assert entries[0]["value"] == "value1"
            assert entries[1]["key"] == "test2"
            assert entries[1]["value"] == "value2"
    
    def test_read_entries_nonexistent_file(self):
        """Test reading entries from a non-existent file."""
        with pytest.raises(CSVError, match="CSV file does not exist"):
            self.csv_manager.read_entries(self.test_dir / "nonexistent.csv")
    
    def test_append_entry(self):
        """Test appending an entry to a CSV file."""
        # Patch the lock and unlock methods to avoid fcntl issues in tests
        with patch('historify.csv_manager.CSVManager._lock_file'), \
             patch('historify.csv_manager.CSVManager._unlock_file'):
            entry = {"key": "test3", "value": "value3"}
            result = self.csv_manager.append_entry(self.test_csv, entry)
            
            assert result is True
            
            # Verify the entry was added
            entries = []
            with open(self.test_csv, "r", newline="") as f:
                reader = csv.DictReader(f)
                entries = list(reader)
            
            assert len(entries) == 3
            assert entries[2]["key"] == "test3"
            assert entries[2]["value"] == "value3"
    
    def test_append_entry_nonexistent_file(self):
        """Test appending an entry to a non-existent file."""
        with pytest.raises(CSVError, match="CSV file does not exist"):
            self.csv_manager.append_entry(
                self.test_dir / "nonexistent.csv", 
                {"key": "test", "value": "value"}
            )
    
    def test_create_csv_file(self):
        """Test creating a new CSV file."""
        # Patch the lock and unlock methods to avoid fcntl issues in tests
        with patch('historify.csv_manager.CSVManager._lock_file'), \
             patch('historify.csv_manager.CSVManager._unlock_file'):
            new_csv = self.test_dir / "new.csv"
            result = self.csv_manager.create_csv_file(new_csv)
            assert result is True
            assert new_csv.exists()
            
            # Verify header was written
            with open(new_csv, "r", newline="") as f:
                reader = csv.reader(f)
                header = next(reader)
                assert len(header) == len(self.csv_manager.required_fields)
    
    def test_create_csv_file_exists(self):
        """Test creating a CSV file that already exists."""
        with pytest.raises(CSVError, match="CSV file already exists"):
            self.csv_manager.create_csv_file(self.test_csv)
    
    def test_find_entries(self):
        """Test finding entries matching filters."""
        # Create a test file with multiple entries
        test_file = self.test_dir / "find_test.csv"
        with open(test_file, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=self.test_fields)
            writer.writeheader()
            writer.writerow({"key": "test1", "value": "value1"})
            writer.writerow({"key": "test2", "value": "value2"})
            writer.writerow({"key": "test3", "value": "value1"})
        
        # Patch the lock and unlock methods
        with patch('historify.csv_manager.CSVManager._lock_file'), \
             patch('historify.csv_manager.CSVManager._unlock_file'):
            # Test basic filtering
            result = self.csv_manager.find_entries(test_file, key="test1")
            assert len(result) == 1
            assert result[0]["key"] == "test1"
            assert result[0]["value"] == "value1"
            
            # Test with multiple entries matching
            result = self.csv_manager.find_entries(test_file, value="value1")
            assert len(result) == 2
            assert result[0]["key"] == "test1"
            assert result[1]["key"] == "test3"
    
    def test_update_entry(self):
        """Test updating an entry in a CSV file."""
        # Create a test file for updating
        update_file = self.test_dir / "update_test.csv"
        with open(update_file, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=self.test_fields)
            writer.writeheader()
            writer.writerow({"key": "test1", "value": "value1"})
            writer.writerow({"key": "test2", "value": "value2"})
        
        # Mock get_fieldnames to return known field names
        with patch('historify.csv_manager.CSVManager._get_fieldnames', return_value=self.test_fields), \
             patch('historify.csv_manager.CSVManager._lock_file'), \
             patch('historify.csv_manager.CSVManager._unlock_file'), \
             patch('historify.csv_manager.Path.unlink'):  # Mock the temp file deletion
            # Create a new entry for updating
            new_entry = {"key": "test1-updated", "value": "value1-updated"}
            
            # Update the first entry
            result = self.csv_manager.update_entry(update_file, 0, new_entry)
            
            assert result is True
    
    def test_update_entry_invalid_index(self):
        """Test updating an entry with an invalid index."""
        # Create a test file for updating
        update_file = self.test_dir / "invalid_update.csv"
        with open(update_file, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=self.test_fields)
            writer.writeheader()
            writer.writerow({"key": "test1", "value": "value1"})
        
        # Mock the required methods
        with patch('historify.csv_manager.CSVManager._lock_file'), \
             patch('historify.csv_manager.CSVManager._unlock_file'):
            # Try to update with an invalid index
            with pytest.raises(CSVError, match="Invalid entry index"):
                self.csv_manager.update_entry(
                    update_file, 
                    10,  # Invalid index 
                    {"key": "invalid", "value": "value"}
                )
    
    def test_update_integrity_info(self):
        """Test updating integrity information."""
        # Create the db directory
        db_dir = self.test_dir / "db"
        db_dir.mkdir(exist_ok=True)
        
        # Mock the file operations
        with patch('historify.csv_manager.CSVManager._lock_file'), \
             patch('historify.csv_manager.CSVManager._unlock_file'), \
             patch('builtins.open', mock_open()):
            
            result = self.csv_manager.update_integrity_info(
                "test-changelog.csv",
                "blake3-hash-value",
                "test-changelog.csv.minisig",
                True,
                "2025-04-22 12:00:00 UTC"
            )
            
            assert result is True
    
    def test_get_integrity_info(self):
        """Test getting integrity information."""
        # Create the db directory
        db_dir = self.test_dir / "db"
        db_dir.mkdir(exist_ok=True)
        
        # Create a test integrity file
        integrity_file = db_dir / "integrity.csv"
        with open(integrity_file, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "changelog_file", "blake3", "signature_file", "verified", "verified_timestamp"
            ])
            writer.writeheader()
            writer.writerow({
                "changelog_file": "test-changelog.csv",
                "blake3": "blake3-hash-value",
                "signature_file": "test-changelog.csv.minisig",
                "verified": "1",
                "verified_timestamp": "2025-04-22 12:00:00 UTC"
            })
        
        # Mock file locking
        with patch('historify.csv_manager.CSVManager._lock_file'), \
             patch('historify.csv_manager.CSVManager._unlock_file'):
            
            # Get integrity info
            info = self.csv_manager.get_integrity_info("test-changelog.csv")
            
            assert info is not None
            assert info["changelog_file"] == "test-changelog.csv"
            assert info["blake3"] == "blake3-hash-value"
            assert info["signature_file"] == "test-changelog.csv.minisig"
            assert info["verified"] == "1"
            assert info["verified_timestamp"] == "2025-04-22 12:00:00 UTC"
