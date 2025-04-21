import pytest
from historify.monitor import FileMonitor
from historify.db import DatabaseManager
from historify.log import LogManager
from historify.config import HistorifyConfig
import tempfile
from pathlib import Path

def test_monitor_scan(tmp_path):
    """Test scanning for file changes."""
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    data_dir = repo_path / "data"
    data_dir.mkdir()
    
    # Initialize configuration
    config = HistorifyConfig(repo_name="test", repo_path=str(repo_path))
    config.set("data_dir", "data", section="repo.test", scope="local")
    
    # Initialize database and log
    db_manager = DatabaseManager(str(repo_path))
    db_manager.initialize()
    log_manager = LogManager(str(repo_path))
    
    # Create a file
    file_path = data_dir / "test.txt"
    file_path.write_text("test data")
    
    # Scan for changes
    monitor = FileMonitor(str(repo_path), db_manager)
    transactions = monitor.scan(["data"])
    
    # Verify new file transaction
    assert len(transactions) == 1
    assert transactions[0]["type"] == "new"
    assert transactions[0]["path"] == "data/test.txt"
    assert len(transactions[0]["hash"]) == 64  # Blake3 hash
    
    # Log transaction
    log_manager.write_transaction(
        transaction_type=transactions[0]["type"],
        file_path=transactions[0]["path"],
        metadata=transactions[0]["metadata"]
    )
    
    # Verify database
    result = db_manager.get_file(transactions[0]["hash"])
    assert result[0] == "data/test.txt"
    
    # Simulate move
    new_path = data_dir / "moved.txt"
    file_path.rename(new_path)
    transactions = monitor.scan(["data"])
    
    # Verify move and deleted transactions
    assert len(transactions) == 2
    move_tx = next(t for t in transactions if t["type"] == "move")
    delete_tx = next(t for t in transactions if t["type"] == "deleted")
    assert move_tx["path"] == "data/moved.txt"
    assert move_tx["metadata"]["old_path"] == "data/test.txt"
    assert delete_tx["path"] == "data/test.txt"
    
    # Simulate delete
    new_path.unlink()
    transactions = monitor.scan(["data"])
    
    # Verify delete transaction
    assert len(transactions) == 1
    assert transactions[0]["type"] == "deleted"
    assert transactions[0]["path"] == "data/moved.txt"

def test_monitor_empty_dirs(tmp_path):
    """Test scanning with no data directories."""
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    
    db_manager = DatabaseManager(str(repo_path))
    db_manager.initialize()
    monitor = FileMonitor(str(repo_path), db_manager)
    
    transactions = monitor.scan([])
    assert len(transactions) == 0