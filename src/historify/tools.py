import subprocess
import os
from pathlib import Path
from typing import Optional

class ToolError(Exception):
    """Custom exception for tool-related errors."""
    pass

def get_blake3_hash(file_path: str, tool_path: str = "b3sum") -> str:
    """
    Compute the Blake3 hash of a file.

    Args:
        file_path: Path to the file.
        tool_path: Path to the b3sum binary (default: "b3sum").

    Returns:
        The Blake3 hash as a lowercase hexadecimal string.

    Raises:
        ToolError: If the tool fails, file doesn't exist, or command errors.
    """
    file_path = Path(file_path)
    if not file_path.is_file():
        raise ToolError(f"File does not exist: {file_path}")

    try:
        result = subprocess.run(
            [tool_path, "--no-names", str(file_path)],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except FileNotFoundError:
        raise ToolError(f"Blake3 tool not found: {tool_path}")
    except subprocess.CalledProcessError as e:
        raise ToolError(f"Failed to compute Blake3 hash: {e.stderr}")

def minisign_verify(file_path: str, pubkey_path: str, tool_path: str = "minisign") -> bool:
    """
    Verify a minisign signature.

    Args:
        file_path: Path to the signed file.
        pubkey_path: Path to the minisign public key.
        tool_path: Path to the minisign binary (default: "minisign").

    Returns:
        True if verification succeeds, False otherwise.

    Raises:
        ToolError: If the tool fails, file/key doesn't exist, or command errors.
    """
    file_path = Path(file_path)
    pubkey_path = Path(pubkey_path)
    sig_path = f"{file_path}.minisig"
    if not file_path.is_file():
        raise ToolError(f"File does not exist: {file_path}")
    if not pubkey_path.is_file():
        raise ToolError(f"Public key file does not exist: {pubkey_path}")
    if not Path(sig_path).is_file():
        raise ToolError(f"Signature file does not exist: {sig_path}")

    try:
        subprocess.run(
            [tool_path, "-V", "-p", str(pubkey_path), "-m", str(file_path)],
            capture_output=True,
            text=True,
            check=True
        )
        return True
    except FileNotFoundError:
        raise ToolError(f"Minisign tool not found: {tool_path}")
    except subprocess.CalledProcessError as e:
        raise ToolError(f"Verification failed: {e.stderr}")
    return False