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

from historify.key_manager import (
    backup_public_key, 
    find_public_key_by_id, 
    list_backed_up_keys, 
    extract_key_id_from_data,
    extract_key_id_from_comment,
    KeyError
)
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
        
        # Copy fixture files
        fixture_dir = Path("tests/fixtures")
        if fixture_dir.exists():
            # Copy the unencrypted minisign key files
            for key_file in ["unencrypted_minisign.pub", "encrypted_minisign.pub"]:
                src_file = fixture_dir / key_file
                if src_file.exists():
                    shutil.copy(src_file, self.keys_dir / key_file)
        
        # Create test key with ID in comment
        self.key1_path = self.keys_dir / "key1.pub"
        with open(self.key1_path, "w") as f:
            f.write("untrusted comment: minisign public key ABC123DEF456ABCD\n")
            f.write("RWQDJTPAA/YOmvb04sV60T1mIznpvhqIX6XBIEyee5XAr/ZDzkpg7KAS\n")
    
    def teardown_method(self):
        """Clean up test environment."""
        if self.test_repo_path.exists():
            shutil.rmtree(self.test_repo_path)
        if self.keys_dir.exists():
            shutil.rmtree(self.keys_dir)
    
    def test_extract_key_id_from_comment(self):
        """Test extracting key ID from comment line."""
        # Test with valid comment line
        comment = "untrusted comment: minisign public key 47405AF9970D8B71"
        key_id = extract_key_id_from_comment(comment)
        assert key_id == "47405AF9970D8B71"
        
        # Test with comment missing key ID
        comment = "untrusted comment: minisign public key"
        key_id = extract_key_id_from_comment(comment)
        assert key_id is None
        
        # Test with arbitrary comment
        comment = "just some random comment"
        key_id = extract_key_id_from_comment(comment)
        assert key_id is None
    
    def test_extract_key_id_from_data(self):
        """Test extracting key ID from base64 data."""
        # This is a complex test since we need valid base64 data
        # We'll use a known fixture file
        fixture_pub = Path("tests/fixtures/unencrypted_minisign.pub")
        if not fixture_pub.exists():
            pytest.skip("Fixture file not available")
        
        with open(fixture_pub, "r") as f:
            lines = f.readlines()
            if len(lines) >= 2:
                base64_data = lines[1].strip()
                key_id = extract_key_id_from_data(base64_data)
                assert key_id is not None
                assert len(key_id) == 16  # Key IDs are 16 hex characters
    
    def test_backup_public_key(self):
        """Test backing up a public key."""
        # Get the path to the fixture file
        fixture_pub = Path("tests/fixtures/unencrypted_minisign.pub")
        if not fixture_pub.exists():
            pytest.skip("Fixture file not available")
            
        # Backup the key
        key_id = backup_public_key(str(self.test_repo_path), str(fixture_pub))
        
        # Verify the key was backed up
        assert key_id == "47405AF9970D8B71"  # From the comment in the fixture
        backup_path = self.test_repo_path / "db" / "keys" / f"{key_id}.pub"
        assert backup_path.exists()
        
        # Verify key content
        with open(fixture_pub, "r") as src, open(backup_path, "r") as dest:
            assert src.read() == dest.read()
    
    def test_backup_public_key_with_id_in_comment(self):
        """Test backing up a public key with ID in comment."""
        # Backup key with ID in comment
        key_id = backup_public_key(str(self.test_repo_path), str(self.key1_path))
        
        # Verify the key was backed up
        assert key_id == "ABC123DEF456ABCD"  # From the comment
        backup_path = self.test_repo_path / "db" / "keys" / f"{key_id}.pub"
        assert backup_path.exists()
        
        # Verify key content
        with open(self.key1_path, "r") as src, open(backup_path, "r") as dest:
            assert src.read() == dest.read()
    
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
        # Backup a key first
        fixture_pub = Path("tests/fixtures/unencrypted_minisign.pub")
        if not fixture_pub.exists():
            pytest.skip("Fixture file not available")
            
        key_id = backup_public_key(str(self.test_repo_path), str(fixture_pub))
        
        # Find key by exact ID
        key_path = find_public_key_by_id(str(self.test_repo_path), key_id)
        assert key_path is not None
        assert key_path.name == f"{key_id}.pub"
        
        # Find key by partial ID
        key_path = find_public_key_by_id(str(self.test_repo_path), key_id[:8])
        assert key_path is not None
        assert key_path.name == f"{key_id}.pub"
        
        # Try to find non-existent key
        key_path = find_public_key_by_id(str(self.test_repo_path), "nonexistent")
        assert key_path is None
    
    def test_list_backed_up_keys(self):
        """Test listing backed up keys."""
        # Initially no keys
        keys = list_backed_up_keys(str(self.test_repo_path))
        assert len(keys) == 0
        
        # Backup a key
        fixture_pub = Path("tests/fixtures/unencrypted_minisign.pub")
        if not fixture_pub.exists():
            pytest.skip("Fixture file not available")
            
        key_id = backup_public_key(str(self.test_repo_path), str(fixture_pub))
        
        # List keys
        keys = list_backed_up_keys(str(self.test_repo_path))
        assert len(keys) == 1
        assert keys[0]["id"] == key_id