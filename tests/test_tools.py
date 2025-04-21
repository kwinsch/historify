import pytest
from historify.tools import get_blake3_hash, minisign_verify
import tempfile
import os
from pathlib import Path
import subprocess

def test_blake3_hash():
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(b"test data")
        tmp.flush()
        hash_value = get_blake3_hash(tmp.name)
        assert len(hash_value) == 64  # Blake3 produces 32-byte (64-char) hex
        assert hash_value.islower()  # Ensure lowercase
    os.unlink(tmp.name)

def test_minisign_verify():
    """Test minisign verification with test key pair."""
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(b"test data")
        tmp.flush()
        key_path = "tests/fixtures/historify.key"
        pubkey_path = "tests/fixtures/historify.pub"
        sig_path = f"{tmp.name}.minisig"
        
        # Manually sign the file with the test key
        try:
            subprocess.run(
                ["minisign", "-Sm", str(tmp.name), "-s", key_path],
                capture_output=True,
                text=True,
                check=True
            )
        except subprocess.CalledProcessError as e:
            pytest.fail(f"Failed to sign file: {e.stderr}")
        
        # Verify the signature
        assert Path(sig_path).exists()
        assert minisign_verify(tmp.name, pubkey_path)
        
        # Clean up
        os.unlink(tmp.name)
        os.unlink(sig_path)