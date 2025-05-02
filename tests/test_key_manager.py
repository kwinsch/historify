# tests/test_key_manager.py
"""
Tests for the key management module.
"""
import pytest
import os
import shutil
from pathlib import Path
from click.testing import CliRunner
from unittest.mock import patch, MagicMock

from historify.key_manager import backup_public_key, find_public_key_by_id, list_backed_up_keys, KeyError
from historify.cli_init import init_repository
from historify.cli import config

class TestKeyManager:
    """Test the key management functionality."""
    
    def setup_method(self):
        """Set up test environment."""
        self.runner = CliRunner()
        self.test_repo_path = Path("test_repo_keys").absolute()
        
        # Initialize a test repository
        if not self.test_repo_path.exists():
            init_repository(str(self.test_repo_path), "test-repo")
        
        # Create test keys directory
        self.keys_dir = Path("test_keys").absolute()
        self.keys_dir.mkdir(parents=True, exist_ok=True)
        
        # Create test key files
        self.key1_path = self.keys_dir / "key1.pub"
        self.key2_path = self.keys_dir / "key2.pub"
        
        # Create key with ID in comment
        with open(self.key1_path, "w") as f:
            f.write("untrusted comment: minisign public key ABC123\n")
            f.write("RWQDJTPAA/YOmvb04sV60T1mIznpvhqIX6XBIEyee5XAr/ZDzkpg7KAS\n")
        
        # Create key without ID in comment but with valid base64 data
        # Using sample data with known key ID
        with open(self.key2_path, "w") as f:
            f.write("untrusted comment: test key\n")
            f.write("RWSf/cF5Ae3QuQy89/xkXu4ipDDDvjRw63fsXjyLiPvKdGrC1Aujn93D\n")
        
        # Copy the fixture file for reference
        fixture_dir = Path("tests/fixtures")
        if fixture_dir.exists():
            unencrypted_pub = fixture_dir / "unencrypted_minisign.pub"
            if unencrypted_pub.exists():
                shutil.copy(unencrypted_pub, self.keys_dir / "unencrypted_minisign.pub")
    
    def teardown_method(self):
        """Clean up test environment."""
        if self.test_repo_path.exists():
            shutil.rmtree(self.test_repo_path)
        if self.keys_dir.exists():
            shutil.rmtree(self.keys_dir)
    
    def test_backup_public_key(self):
        """Test backing up a public key."""
        # Backup key with ID in comment
        key_id = backup_public_key(str(self.test_repo_path), str(self.key1_path))
        
        # Verify the key was backed up
        assert key_id == "ABC123"  # Still prioritize comment ID
        backup_path = self.test_repo_path / "db" / "keys" / f"{key_id}.pub"
        assert backup_path.exists()
        
        # Verify key content
        with open(self.key1_path, "r") as src, open(backup_path, "r") as dest:
            assert src.read() == dest.read()
    
    @patch('historify.key_manager.base64.b64decode')
    def test_backup_public_key_no_id(self, mock_b64decode):
        """Test backing up a public key without ID in comment."""
        # Mock the base64 decode to return a known key ID
        mock_b64decode.return_value = b'Ed' + b'933D407DF3BEB9E3'.decode('hex_codec').encode('utf-8') + b'rest_of_data'
        
        key_id = backup_public_key(str(self.test_repo_path), str(self.key2_path))
        
        # Verify the key was backed up with the extracted binary key ID
        assert key_id == "933D407DF3BEB9E3"
        backup_path = self.test_repo_path / "db" / "keys" / f"{key_id}.pub"
        assert backup_path.exists()
    
    def test_backup_nonexistent_key(self):
        """Test backing up a non-existent key."""
        with pytest.raises(KeyError, match="Public key does not exist"):
            backup_public_key(str(self.test_repo_path), "nonexistent.pub")
    
    def test_backup_duplicate_key(self):
        """Test backing up the same key twice."""
        # Backup key first time
        key_id1 = backup_public_key(str(self.test_repo_path), str(self.key1_path))
        
        # Backup same key again
        key_id2 = backup_public_key(str(self.test_repo_path), str(self.key1_path))
        
        # Should return the same key ID and not create a duplicate
        assert key_id1 == key_id2
        
        # Should have only one backup
        keys_dir = self.test_repo_path / "db" / "keys"
        key_files = list(keys_dir.glob("*.pub"))
        assert len(key_files) == 1
    
    def test_find_public_key_by_id(self):
        """Test finding a public key by ID."""
        # Backup keys first
        key_id1 = backup_public_key(str(self.test_repo_path), str(self.key1_path))
        key_id2 = backup_public_key(str(self.test_repo_path), str(self.key2_path))
        
        # Find key by exact ID
        key_path = find_public_key_by_id(str(self.test_repo_path), key_id1)
        assert key_path is not None
        assert key_path.name == f"{key_id1}.pub"
        
        # Find key by partial ID
        key_path = find_public_key_by_id(str(self.test_repo_path), "ABC")
        assert key_path is not None
        assert key_path.name == f"{key_id1}.pub"
        
        # Try to find non-existent key
        key_path = find_public_key_by_id(str(self.test_repo_path), "nonexistent")
        assert key_path is None
    
    @patch('historify.key_manager.base64.b64decode')
    def test_list_backed_up_keys(self, mock_b64decode):
        """Test listing backed up keys."""
        # Mock the base64 decode to return known key IDs
        def side_effect(arg):
            if "RWQDJTPAA" in arg:  # key1
                return b'Ed' + b'ABC123'.ljust(8, b'\x00') + b'rest_of_data'
            else:  # key2
                return b'Ed' + b'933D407DF3BEB9E3'.decode('hex_codec').encode('utf-8') + b'rest_of_data'
        
        mock_b64decode.side_effect = side_effect
        
        # Initially no keys
        keys = list_backed_up_keys(str(self.test_repo_path))
        assert len(keys) == 0
        
        # Backup keys
        backup_public_key(str(self.test_repo_path), str(self.key1_path))
        backup_public_key(str(self.test_repo_path), str(self.key2_path))
        
        # List keys
        keys = list_backed_up_keys(str(self.test_repo_path))
        assert len(keys) == 2
        
        # Verify key info
        key_ids = [key["id"] for key in keys]
        assert "ABC123" in key_ids
        assert "933D407DF3BEB9E3" in key_ids