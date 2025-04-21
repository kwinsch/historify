"""
Tools module for historify with improved native BLAKE3 support.
"""
import subprocess
import os
import logging
from pathlib import Path
from typing import Optional, Union

# Configure logging
logger = logging.getLogger(__name__)

class ToolError(Exception):
    """Custom exception for tool-related errors."""
    pass

def get_blake3_hash_native(file_path: Union[str, Path]) -> str:
    """
    Compute the Blake3 hash of a file using the native Python implementation.
    
    Args:
        file_path: Path to the file.
        
    Returns:
        The Blake3 hash as a lowercase hexadecimal string.
        
    Raises:
        ToolError: If the file doesn't exist or can't be read.
        ImportError: If the blake3 module is not available.
    """
    try:
        import blake3
    except ImportError:
        raise ImportError("Native blake3 module not available. Install with 'pip install blake3'.")
    
    file_path = Path(file_path)
    if not file_path.is_file():
        raise ToolError(f"File does not exist: {file_path}")

    try:
        hasher = blake3.blake3()
        with open(file_path, "rb") as f:
            # Read in chunks to handle large files efficiently
            chunk = f.read(8192)
            while chunk:
                hasher.update(chunk)
                chunk = f.read(8192)
        
        return hasher.hexdigest()
    except (IOError, OSError) as e:
        raise ToolError(f"Failed to read file {file_path}: {e}")

def get_blake3_hash(file_path: Union[str, Path], tool_path: str = "b3sum", use_native: bool = True) -> str:
    """
    Compute the Blake3 hash of a file. Prefers native implementation if available.
    
    Args:
        file_path: Path to the file.
        tool_path: Path to the b3sum binary (default: "b3sum").
        use_native: Whether to prefer the native Python implementation.
        
    Returns:
        The Blake3 hash as a lowercase hexadecimal string.
        
    Raises:
        ToolError: If the tool fails, file doesn't exist, or command errors.
    """
    # Try native implementation first if requested
    if use_native:
        try:
            return get_blake3_hash_native(file_path)
        except ImportError:
            logger.warning("Native blake3 module not available, falling back to command-line tool.")
        except Exception as e:
            logger.warning(f"Native Blake3 implementation failed: {e}. Falling back to tool.")
    
    # Fall back to command-line tool
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

def minisign_sign(file_path: Union[str, Path], key_path: Union[str, Path], 
                 tool_path: str = "minisign", password: Optional[str] = None) -> bool:
    """
    Sign a file using minisign.
    
    Args:
        file_path: Path to the file to sign.
        key_path: Path to the minisign private key.
        tool_path: Path to the minisign binary (default: "minisign").
        password: Optional password for encrypted keys.
        
    Returns:
        True if signing succeeds.
        
    Raises:
        ToolError: If signing fails or files don't exist.
    """
    file_path = Path(file_path)
    key_path = Path(key_path)
    
    if not file_path.is_file():
        raise ToolError(f"File does not exist: {file_path}")
    if not key_path.is_file():
        raise ToolError(f"Private key file does not exist: {key_path}")
    
    cmd = [tool_path, "-Sm", str(file_path), "-s", str(key_path)]
    
    try:
        if password:
            # Use subprocess.Popen to pass the password to stdin
            process = subprocess.Popen(
                cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, text=True
            )
            stdout, stderr = process.communicate(input=password + '\n')
            
            if process.returncode != 0:
                raise ToolError(f"Signing failed: {stderr}")
        else:
            # If no password, just run the command
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            
        logger.info(f"Successfully signed {file_path}")
        return True
    except FileNotFoundError:
        raise ToolError(f"Minisign tool not found: {tool_path}")
    except subprocess.CalledProcessError as e:
        raise ToolError(f"Signing failed: {e.stderr}")

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
        logger.info(f"Successfully verified signature for {file_path}")
        return True
    except FileNotFoundError:
        raise ToolError(f"Minisign tool not found: {tool_path}")
    except subprocess.CalledProcessError as e:
        logger.error(f"Verification failed: {e.stderr}")
        return False
