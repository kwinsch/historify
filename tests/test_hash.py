import pytest
import os
import tempfile
from pathlib import Path
from historify.hash import (
    get_blake3_hash,
    get_sha256_hash,
    hash_file,
    HashError
)

class TestHash:
    
    def test_get_blake3_hash(self):
        """Test Blake3 hash computation."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(b"test data")
            tmp.flush()
            tmp_path = tmp.name
            
            # Test with default parameters
            hash_value = get_blake3_hash(tmp_path)
            assert hash_value is not None
            assert len(hash_value) == 64  # Blake3 produces 32-byte (64-char) hex
            assert hash_value.islower()  # Ensure lowercase
            
            # Test with explicit tool path
            hash_value2 = get_blake3_hash(tmp_path, tool_path="b3sum", use_native=False)
            assert hash_value2 == hash_value
            
        os.unlink(tmp_path)
    
    def test_get_blake3_hash_file_not_found(self):
        """Test Blake3 hash with non-existent file."""
        with pytest.raises(HashError, match="File does not exist"):
            get_blake3_hash("nonexistent_file.txt")
    
    def test_get_sha256_hash(self):
        """Test SHA256 hash computation."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(b"test data")
            tmp.flush()
            tmp_path = tmp.name
            
            # Test with default parameters
            hash_value = get_sha256_hash(tmp_path)
            assert hash_value is not None
            assert len(hash_value) == 64  # SHA256 produces 32-byte (64-char) hex
            assert hash_value.islower()  # Ensure lowercase
            
            # Test with explicit tool path
            hash_value2 = get_sha256_hash(tmp_path, tool_path="sha256sum")
            assert hash_value2 == hash_value
            
        os.unlink(tmp_path)
    
    def test_get_sha256_hash_file_not_found(self):
        """Test SHA256 hash with non-existent file."""
        with pytest.raises(HashError, match="File does not exist"):
            get_sha256_hash("nonexistent_file.txt")
    
    def test_hash_file(self):
        """Test computing multiple hashes for a file."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(b"test data")
            tmp.flush()
            tmp_path = tmp.name
            
            # Test with default algorithms
            hashes = hash_file(tmp_path)
            assert "blake3" in hashes
            assert "sha256" in hashes
            assert len(hashes["blake3"]) == 64
            assert len(hashes["sha256"]) == 64
            
            # Test with specific algorithms
            hashes_blake = hash_file(tmp_path, algorithms=["blake3"])
            assert "blake3" in hashes_blake
            assert "sha256" not in hashes_blake
            
            hashes_sha = hash_file(tmp_path, algorithms=["sha256"])
            assert "blake3" not in hashes_sha
            assert "sha256" in hashes_sha
            
            # Test with multiple algorithms
            hashes_both = hash_file(tmp_path, algorithms=["blake3", "sha256"])
            assert hashes_both == hashes
            
        os.unlink(tmp_path)
    
    def test_hash_file_not_found(self):
        """Test multiple hashes with non-existent file."""
        with pytest.raises(HashError, match="File does not exist"):
            hash_file("nonexistent_file.txt")
    
    def test_fixture_hash_verification(self):
        """Test hash verification against known fixture files."""
        fixture_dir = Path("tests/fixtures")
        
        # Verify Blake3 hashes from b3sum.txt
        with open(fixture_dir / "b3sum.txt", "r") as f:
            expected_b3_hashes = {}
            for line in f:
                parts = line.strip().split("  ")
                if len(parts) == 2:
                    expected_b3_hashes[parts[1]] = parts[0]
        
        # Verify SHA256 hashes from sha256sum.txt
        with open(fixture_dir / "sha256sum.txt", "r") as f:
            expected_sha256_hashes = {}
            for line in f:
                parts = line.strip().split("  ")
                if len(parts) == 2:
                    expected_sha256_hashes[parts[1]] = parts[0]
        
        # Check files that should exist in both hash files
        for filename in ["encrypted_minisign.key", "encrypted_minisign.pub", 
                         "unencrypted_minisign.key", "unencrypted_minisign.pub"]:
            file_path = fixture_dir / filename
            
            # Check if file exists
            assert file_path.exists(), f"Fixture file {filename} does not exist"
            
            # Verify Blake3 hash
            if filename in expected_b3_hashes:
                computed_b3 = get_blake3_hash(file_path)
                assert computed_b3 == expected_b3_hashes[filename], \
                    f"Blake3 hash mismatch for {filename}"
            
            # Verify SHA256 hash
            if filename in expected_sha256_hashes:
                computed_sha256 = get_sha256_hash(file_path)
                assert computed_sha256 == expected_sha256_hashes[filename], \
                    f"SHA256 hash mismatch for {filename}"
