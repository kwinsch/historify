import pytest
from historify.log import LogManager
from historify.config import ConfigError
import tempfile
import csv
from pathlib import Path
from datetime import datetime, UTC

def test_log_write_read(tmp_path):
    """Test writing and reading transactions."""
    log_manager = LogManager(str(tmp_path))
    
    # Write config transaction
    log_manager.write_transaction(
        transaction_type="config",
        metadata={"hash_algorithm": "blake3"}
    )
    
    # Write comment transaction
    log_manager.write_transaction(
        transaction_type="comment",
        metadata={"message": "Test comment"}
    )
    
    # Write file transaction
    file_path = tmp_path / "test.txt"
    file_path.write_text("test data")
    log_manager.write_transaction(
        transaction_type="new",
        file_path="test.txt"
    )
    
    # Read transactions
    transactions = log_manager.read_log()
    assert len(transactions) == 3
    
    # Verify config transaction
    assert transactions[0]["transaction_type"] == "config"
    assert "hash_algorithm=blake3" in transactions[0]["metadata"]
    
    # Verify comment transaction
    assert transactions[1]["transaction_type"] == "comment"
    assert "message=Test comment" in transactions[1]["metadata"]
    
    # Verify file transaction
    assert transactions[2]["transaction_type"] == "new"
    assert transactions[2]["path"] == "test.txt"
    assert len(transactions[2]["hash"]) == 64  # Blake3 hash length
    assert "size=9" in transactions[2]["metadata"]  # "test data" is 9 bytes

def test_log_invalid_type(tmp_path):
    """Test writing an invalid transaction type."""
    log_manager = LogManager(str(tmp_path))
    with pytest.raises(ConfigError, match="Invalid transaction type: invalid"):
        log_manager.write_transaction(transaction_type="invalid")

def test_log_missing_file(tmp_path):
    """Test reading a non-existent log file."""
    log_manager = LogManager(str(tmp_path))
    with pytest.raises(ConfigError, match="Log file does not exist"):
        log_manager.read_log(str(tmp_path / "nonexistent.csv"))

def test_log_unsupported_fields(tmp_path, capsys):
    """Test warning for unsupported fields."""
    log_file = tmp_path / f"translog-{datetime.now(UTC).strftime('%Y-%m')}.csv"
    with log_file.open("w", newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "transaction_type", "hash", "path", "metadata", "unknown"])
        writer.writerow(["2025-04-01 12:00:00 UTC", "comment", "", "", "message=test", "value"])
    
    log_manager = LogManager(str(tmp_path))
    log_manager.read_log(str(log_file))
    captured = capsys.readouterr()
    assert "Warning: Unsupported fields in" in captured.out
    assert "unknown" in captured.out