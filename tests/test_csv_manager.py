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
    
    @patch('historify.csv_manager.csv.DictWriter')
    def test_append_entry(self, mock_dict_writer):
        """Test appending an entry to a CSV file."""
        # Setup mock
        mock_writer = MagicMock()
        mock_dict_writer.return_value = mock_writer
        
        # Test with dynamically determining field names
        with patch('historify.csv_manager.csv.DictReader') as mock_dict_reader:
            mock_reader = MagicMock()
            mock_reader.fieldnames = self.test_fields
            mock_dict_reader.return_value = mock_reader
            
            entry = {"key": "test3", "value": "value3"}
            result = self.csv_manager.append_entry(self.test_csv, entry)
            
            assert result is True
            mock_writer.writerow.assert_called_once_with(entry)
    
    def test_append_entry_nonexistent_file(self):
        """Test appending an entry to a non-existent file."""
        with pytest.raises(CSVError, match="CSV file does not exist"):
            self.csv_manager.append_entry(
                self.test_dir / "nonexistent.csv", 
                {"key": "test", "value": "value"}
            )
    
    def test_create_csv_file(self):
        """Test creating a new CSV file."""
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
    
    @patch('historify.csv_manager.csv.DictReader')
    def test_find_entries(self, mock_dict_reader):
        """Test finding entries matching filters."""
        # Setup mock
        entries = [
            {"key": "test1", "value": "value1"},
            {"key": "test2", "value": "value2"},
            {"key": "test3", "value": "value1"}
        ]
        mock_reader = MagicMock()
        mock_reader.__iter__.return_value = iter(entries)
        mock_dict_reader.return_value = mock_reader
        
        # Test basic filtering
        result = self.csv_manager.find_entries(self.test_csv, key="test1")
        assert len(result) == 1
        assert result[0]["key"] == "test1"
        assert result[0]["value"] == "value1"
        
        # Test with multiple entries matching
        result = self.csv_manager.find_entries(self.test_csv, value="value1")
        assert len(result) == 2
        assert result[0]["key"] == "test1"
        assert result[1]["key"] == "test3"
    
    @patch('historify.csv_manager.csv.DictReader')
    @patch('historify.csv_manager.csv.DictWriter')
    def test_update_entry(self, mock_dict_writer, mock_dict_reader):
        """Test updating an entry in a CSV file."""
        # Setup mocks
        entries = [
            {"key": "test1", "value": "value1"},
            {"key": "test2", "value": "value2"}
        ]
        mock_reader = MagicMock()
        mock_reader.__iter__.return_value = iter(entries)
        mock_reader.fieldnames = self.test_fields
        mock_dict_reader.return_value = mock_reader
        
        mock_writer = MagicMock()
        mock_dict_writer.return_value = mock_writer
        
        # Test updating
        new_entry = {"key": "test1-updated", "value": "value1-updated"}
        with patch('pathlib.Path.exists', return_value=True):
            with patch('tempfile.mktemp', return_value="/tmp/temp.csv"):
                with patch('builtins.open', mock_open()):
                    with patch('shutil.copyfileobj'):
                        result = self.csv_manager.update_entry(self.test_csv, 0, new_entry)
                        
                        assert result is True
                        mock_writer.writerow.assert_any_call(new_entry)
    
    def test_update_entry_invalid_index(self):
        """Test updating an entry with an invalid index."""
        with patch('historify.csv_manager.CSVManager.read_entries', return_value=[{"key": "test"}]):
            with pytest.raises(CSVError, match="Invalid entry index"):
                self.csv_manager.update_entry(
                    self.test_csv, 
                    10,  # Invalid index 
                    {"key": "invalid"}
                )
    
    def test_update_integrity_info(self):
        """Test updating integrity information."""
        # Create integrity file first
        integrity_file = self.test_dir / "db" / "integrity.csv"
        self.test_dir.joinpath("db").mkdir(exist_ok=True)
        
        # Update integrity info with appropriate mocking
        with patch('builtins.open', mock_open()):
            with patch('csv.DictWriter'):
                with patch('csv.DictReader', return_value=iter([])):
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
        # Create and populate integrity file
        integrity_file = self.test_dir / "db" / "integrity.csv"
        self.test_dir.joinpath("db").mkdir(exist_ok=True)
        
        # Mock reading entries
        test_entries = [
            {
                "changelog_file": "test-changelog.csv",
                "blake3": "blake3-hash-value",
                "signature_file": "test-changelog.csv.minisig",
                "verified": "1",
                "verified_timestamp": "2025-04-22 12:00:00 UTC"
            }
        ]
        
        with patch('historify.csv_manager.CSVManager.read_entries', return_value=test_entries):
            # Get integrity info
            info = self.csv_manager.get_integrity_info("test-changelog.csv")
            assert info is not None
            assert info["changelog_file"] == "test-changelog.csv"
            assert info["blake3"] == "blake3-hash-value"
            assert info["signature_file"] == "test-changelog.csv.minisig"
            assert info["verified"] == "1"
            assert info["verified_timestamp"] == "2025-04-22 12:00:00 UTC"
        
        # Test with non-existent entry
        with patch('historify.csv_manager.CSVManager.read_entries', return_value=test_entries):
            info = self.csv_manager.get_integrity_info("nonexistent.csv")
            assert info is None
