import pytest
import os
from historify.config import HistorifyConfig, ConfigError
from pathlib import Path

def test_config_set_get(tmp_path):
    """Test setting and getting configuration values."""
    config = HistorifyConfig(repo_path=str(tmp_path))
    
    # Set and get in local scope
    config.set("hash_algorithm", "blake3", section="repo.test", scope="local")
    assert config.get("hash_algorithm", section="repo.test") == "blake3"
    
    # Set and get minisign keypair in local scope
    config.set("minisign_key", "/home/kab/.minisign/minisign.key", section="repo.test", scope="local")
    config.set("minisign_pub", "/home/kab/.minisign/minisign.pub", section="repo.test", scope="local")
    assert config.get("minisign_key", section="repo.test") == "/home/kab/.minisign/minisign.key"
    assert config.get("minisign_pub", section="repo.test") == "/home/kab/.minisign/minisign.pub"
    
    # Set and get in global scope
    config.set("random_source", "/dev/urandom", section="global", scope="global")
    assert config.get("random_source", section="global") == "/dev/urandom"
    
    # Verify local config file
    config_file = tmp_path / ".historify/config"
    assert config_file.exists()
    
    # Verify global config file
    global_config = os.path.expanduser("~/.historify/config")
    assert os.path.exists(global_config)
    
    # Test default value
    assert config.get("nonexistent", section="repo.test", default="default") == "default"

def test_config_invalid_scope(tmp_path):
    """Test setting with an invalid scope."""
    config = HistorifyConfig(repo_path=str(tmp_path))
    with pytest.raises(ConfigError, match="Invalid scope: invalid"):
        config.set("key", "value", section="repo.test", scope="invalid")

def test_config_no_local_repo():
    """Test setting local config without a repository."""
    config = HistorifyConfig(repo_path=None)
    with pytest.raises(ConfigError, match="Repository path required for local config"):
        config.set("key", "value", section="repo.test", scope="local")

def test_config_multi_repo_keypair(tmp_path):
    """Test using the same minisign keypair across multiple repositories."""
    repo1_path = tmp_path / "repo1"
    repo2_path = tmp_path / "repo2"
    repo1_path.mkdir()
    repo2_path.mkdir()
    
    # Configure repo1
    config1 = HistorifyConfig(repo_name="repo1", repo_path=str(repo1_path))
    config1.set("minisign_key", "/home/kab/.minisign/minisign.key", section="repo.repo1", scope="local")
    config1.set("minisign_pub", "/home/kab/.minisign/minisign.pub", section="repo.repo1", scope="local")
    
    # Configure repo2 with the same keypair
    config2 = HistorifyConfig(repo_name="repo2", repo_path=str(repo2_path))
    config2.set("minisign_key", "/home/kab/.minisign/minisign.key", section="repo.repo2", scope="local")
    config2.set("minisign_pub", "/home/kab/.minisign/minisign.pub", section="repo.repo2", scope="local")
    
    # Verify both repos use the same keypair
    assert config1.get("minisign_key", section="repo.repo1") == "/home/kab/.minisign/minisign.key"
    assert config1.get("minisign_pub", section="repo.repo1") == "/home/kab/.minisign/minisign.pub"
    assert config2.get("minisign_key", section="repo.repo2") == "/home/kab/.minisign/minisign.key"
    assert config2.get("minisign_pub", section="repo.repo2") == "/home/kab/.minisign/minisign.pub"
    
    # Verify config files
    assert (repo1_path / ".historify/config").exists()
    assert (repo2_path / ".historify/config").exists()