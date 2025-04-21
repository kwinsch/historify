import pytest
from historify.config import HistorifyConfig
from historify.tools import get_blake3_hash
import tempfile
import os
from pathlib import Path
import csv
from datetime import datetime
from click.testing import CliRunner

def test_init(tmp_path):
    """Test initializing a new repository."""
    repo_path = tmp_path / "test-repo"
    repo_name = "test-repo"
    
    # Run init command
    from historify.cli import main
    runner = CliRunner()
    result = runner.invoke(main, ["init", str(repo_path), "--name", repo_name])
    
    assert result.exit_code == 0
    assert f"Initialized repository '{repo_name}' in {repo_path}" in result.output
    
    # Verify .historify/config
    config = HistorifyConfig(repo_name=repo_name, repo_path=str(repo_path))
    assert config.get("hash_algorithm", section=f"repo.{repo_name}") == "blake3"
    assert config.get("random_source", section=f"repo.{repo_name}") == "/dev/urandom"
    assert config.get("tools.b3sum", section=f"repo.{repo_name}") == "/usr/bin/b3sum"
    
    # Verify seed.bin
    seed_file = repo_path / ".historify/seed.bin"
    assert seed_file.exists()
    assert seed_file.stat().st_size == 1024 * 1024  # 1MB
    
    # Skip signature checks until Step 7
    # assert (repo_path / ".historify/seed.bin.minisig").exists()
    
    # Verify transaction log
    log_file = repo_path / f"translog-{datetime.utcnow().strftime('%Y-%m')}.csv"
    assert log_file.exists()
    with log_file.open("r") as f:
        reader = csv.reader(f)
        rows = list(reader)
        assert len(rows) >= 3  # Header + config + seed
        assert rows[0] == ["timestamp", "transaction_type", "hash", "path", "metadata"]
        assert rows[1][1] == "config"
        assert rows[2][1] == "seed"
        assert rows[2][2] == get_blake3_hash(str(seed_file))
    
    # Skip log signature check
    # assert (log_file.with_suffix(".csv.minisig")).exists()