import pytest
from historify.config import HistorifyConfig, ConfigError
import tempfile
import os
from pathlib import Path

def test_config_set_get(tmp_path):
    """Test setting and getting configuration values."""
    config = HistorifyConfig(repo_path=str(tmp_path))
    
    # Set and get in local scope
    config.set("hash_algorithm", "blake3", scope="local")
    assert config.get("hash_algorithm") == "blake3"
    
    # Verify local config file exists
    assert (tmp_path / ".historify/config").exists()
    
    # Set in user scope (using temporary file)
    user_config = tmp_path / "user.conf"
    with pytest.MonkeyPatch.context() as m:
        m.setattr(config, "user_config", user_config)
        config.set("organization", "TestOrg", scope="user")
        assert config.get("organization") == "TestOrg"
        assert user_config.exists()

def test_config_invalid_scope(tmp_path):
    """Test setting with an invalid scope."""
    config = HistorifyConfig(repo_path=str(tmp_path))
    with pytest.raises(ConfigError, match="Invalid scope: invalid"):
        config.set("key", "value", scope="invalid")

def test_config_no_local_repo():
    """Test setting local config without a repository."""
    config = HistorifyConfig(repo_path=None)
    with pytest.raises(ConfigError, match="Local configuration requires a repository path"):
        config.set("key", "value", scope="local")

