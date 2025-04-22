import pytest
import os
import shutil
import tempfile
from pathlib import Path
import subprocess
from historify.minisign import (
    minisign_sign,
    minisign_verify,
    MinisignError
)

# Skip tests if minisign is not installed
minisign_missing = shutil.which("minisign") is None
pytestmark = pytest.mark.skipif(
    minisign_missing, 
    reason="minisign executable not found in PATH"
)

class TestMinisign:
    
    def setup_method(self):
        """Create temporary test files and directories."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = Path(self.temp_dir) / "test.txt"
        with open(self.test_file, "w") as f:
            f.write("This is test data for minisign")
            
        # Paths to fixture keys
        self.fixture_dir = Path("tests/fixtures")
        self.encrypted_key = self.fixture_dir / "encrypted_minisign.key"
        self.encrypted_pub = self.fixture_dir / "encrypted_minisign.pub"
        self.unencrypted_key = self.fixture_dir / "unencrypted_minisign.key"
        self.unencrypted_pub = self.fixture_dir / "unencrypted_minisign.pub"
    
    def teardown_method(self):
        """Clean up temporary files."""
        shutil.rmtree(self.temp_dir)
    
    def test_sign_unencrypted(self):
        """Test signing with unencrypted key."""
        # Skip if fixtures don't exist
        if not self.unencrypted_key.exists():
            pytest.skip("Unencrypted key fixture not found")
            
        # Sign with unencrypted key
        result = minisign_sign(
            self.test_file,
            self.unencrypted_key,
            unencrypted=True
        )
        
        assert result, "Signing with unencrypted key failed"
        
        # Verify the signature exists
        sig_file = Path(f"{self.test_file}.minisig")
        assert sig_file.exists(), "Signature file was not created"
    
    def test_sign_encrypted(self):
        """Test signing with encrypted key."""
        # Skip if fixtures don't exist
        if not self.encrypted_key.exists():
            pytest.skip("Encrypted key fixture not found")
            
        # Sign with encrypted key
        result = minisign_sign(
            self.test_file,
            self.encrypted_key,
            password="123"  # Known test password
        )
        
        assert result, "Signing with encrypted key failed"
        
        # Verify the signature exists
        sig_file = Path(f"{self.test_file}.minisig")
        assert sig_file.exists(), "Signature file was not created"
    
    def test_sign_wrong_password(self):
        """Test signing with incorrect password."""
        # Skip if fixtures don't exist
        if not self.encrypted_key.exists():
            pytest.skip("Encrypted key fixture not found")
            
        # Sign with encrypted key but wrong password
        result = minisign_sign(
            self.test_file,
            self.encrypted_key,
            password="wrong_password"
        )
        
        assert not result, "Signing should fail with wrong password"
    
    def test_verify_signed_file(self):
        """Test verifying a signed file."""
        # Skip if fixtures don't exist
        if not self.unencrypted_key.exists() or not self.unencrypted_pub.exists():
            pytest.skip("Unencrypted key fixtures not found")
            
        # Sign the file first
        result = minisign_sign(
            self.test_file,
            self.unencrypted_key,
            unencrypted=True
        )
        assert result, "Signing failed"
        
        # Verify the signature
        success, message = minisign_verify(
            self.test_file,
            self.unencrypted_pub
        )
        
        assert success, f"Verification failed: {message}"
        assert "Signature and comment signature verified" in message
    
    def test_verify_tampered_file(self):
        """Test verifying a tampered file."""
        # Skip if fixtures don't exist
        if not self.unencrypted_key.exists() or not self.unencrypted_pub.exists():
            pytest.skip("Unencrypted key fixtures not found")
            
        # Sign the file
        result = minisign_sign(
            self.test_file,
            self.unencrypted_key,
            unencrypted=True
        )
        assert result, "Initial signing failed"
        
        # Tamper with the file
        with open(self.test_file, "a") as f:
            f.write("\nThis is tampering with the file")
        
        # Verify signature (should fail)
        success, message = minisign_verify(
            self.test_file,
            self.unencrypted_pub
        )
        
        assert not success, "Verification should fail for tampered file"
    
    def test_sign_nonexistent_file(self):
        """Test signing a non-existent file."""
        with pytest.raises(MinisignError, match="File does not exist"):
            minisign_sign(
                "nonexistent_file.txt",
                self.unencrypted_key,
                unencrypted=True
            )
    
    def test_sign_nonexistent_key(self):
        """Test signing with a non-existent key."""
        with pytest.raises(MinisignError, match="Private key file does not exist"):
            minisign_sign(
                self.test_file,
                "nonexistent_key.txt",
                unencrypted=True
            )
    
    def test_verify_nonexistent_file(self):
        """Test verifying a non-existent file."""
        with pytest.raises(MinisignError, match="File does not exist"):
            minisign_verify(
                "nonexistent_file.txt",
                self.unencrypted_pub
            )
    
    def test_verify_nonexistent_pubkey(self):
        """Test verifying with a non-existent public key."""
        with pytest.raises(MinisignError, match="Public key file does not exist"):
            minisign_verify(
                self.test_file,
                "nonexistent_pubkey.txt"
            )
    
    def test_verify_nonexistent_signature(self):
        """Test verifying a file with no signature."""
        with pytest.raises(MinisignError, match="Signature file does not exist"):
            # No signature has been created for this file yet
            minisign_verify(
                self.test_file,
                self.unencrypted_pub
            )
