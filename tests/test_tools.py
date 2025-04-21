import pytest
from historify.tools import get_blake3_hash, minisign_sign, minisign_verify
import tempfile
import os
from pathlib import Path


def test_blake3_hash():
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(b"test data")
        tmp.flush()
        hash_value = get_blake3_hash(tmp.name)
        assert len(hash_value) == 64  # Blake3 produces 32-byte (64-char) hex
        assert hash_value.islower()  # Ensure lowercase
    os.unlink(tmp.name)


@pytest.mark.skip(reason="Minisign key pair not yet configured")
def test_minisign_sign_verify():
    with tempfile.NamedTemporaryFile(delete=False) as tmp, tempfile.NamedTemporaryFile(
        delete=False, suffix=".key"
    ) as key, tempfile.NamedTemporaryFile(delete=False, suffix=".pub") as pubkey:
        tmp.write(b"test data")
        tmp.flush()
        try:
            sig_path = minisign_sign(tmp.name, key.name)
            assert Path(sig_path).exists()
            verified = minisign_verify(tmp.name, pubkey.name)
            assert verified
        finally:
            os.unlink(tmp.name)
            os.unlink(key.name)
            os.unlink(pubkey.name)
            if Path(sig_path).exists():
                os.unlink(sig_path)
