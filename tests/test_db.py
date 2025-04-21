import pytest
import sqlite3
from historify.db import DatabaseManager
from historify.tools import get_blake3_hash
from historify.config import ConfigError
import tempfile
from pathlib import Path

def test_db_initialize(tmp_path):
    """Test initializing the database."""
    db_manager = DatabaseManager(str(tmp_path))
    db_manager.initialize()
    
    db_path = tmp_path / ".historify/historify.db"
    assert db_path.exists()
    
    # Verify schema
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='files'")
        assert cursor.fetchone() is not None

def test_db_add_get_file(tmp_path):
    """Test adding and retrieving a file."""
    db_manager = DatabaseManager(str(tmp_path))
    db_manager.initialize()
    
    file_path = tmp_path / "test.txt"
    file_path.write_text("test data")
    
    db_manager.add_file(str(file_path))
    file_hash = get_blake3_hash(str(file_path))
    result = db_manager.get_file(file_hash)
    
    assert result is not None
    assert result[0] == "test.txt"
    assert "UTC" in result[1]  # Timestamp includes UTC

def test_db_verify_integrity(tmp_path):
    """Test verifying database integrity."""
    db_manager = DatabaseManager(str(tmp_path))
    db_manager.initialize()
    
    file_path = tmp_path / "test.txt"
    file_path.write_text("test data")
    db_manager.add_file(str(file_path))
    
    # Verify no issues
    issues = db_manager.verify_integrity()
    assert len(issues) == 0
    
    # Simulate missing file
    file_path.unlink()
    issues = db_manager.verify_integrity()
    assert len(issues) == 1
    assert issues[0][1] == "test.txt"

def test_db_invalid_file(tmp_path):
    """Test adding a non-existent file."""
    db_manager = DatabaseManager(str(tmp_path))
    db_manager.initialize()
    
    with pytest.raises(ConfigError, match="File does not exist"):
        db_manager.add_file(str(tmp_path / "nonexistent.txt"))