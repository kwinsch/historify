"""
Hash module for historify providing hash functionality.
"""
import subprocess
import logging
from pathlib import Path
from typing import Union, Optional, List, Dict

# Configure logging
logger = logging.getLogger(__name__)

class HashError(Exception):
    """Custom exception for hash-related errors."""
    pass

def get_blake3_hash_native(file_path: Union[str, Path]) -> str:
    """
    Compute the Blake3 hash of a file using the native Python implementation.
    
    Args:
        file_path: Path to the file.
        
    Returns:
        The Blake3 hash as a lowercase hexadecimal string.
        
    Raises:
        HashError: If the file doesn't exist or can't be read.
        ImportError: If the blake3 module is not available.
    """
    try:
        import blake3
    except ImportError:
        raise ImportError("Native blake3 module not available. Install with 'pip install blake3'.")
    
    file_path = Path(file_path)
    if not file_path.is_file():
        raise HashError(f"File does not exist: {file_path}")

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
        raise HashError(f"Failed to read file {file_path}: {e}")

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
        HashError: If the tool fails, file doesn't exist, or command errors.
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
        raise HashError(f"File does not exist: {file_path}")

    try:
        result = subprocess.run(
            [tool_path, "--no-names", str(file_path)],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except FileNotFoundError:
        raise HashError(f"Blake3 tool not found: {tool_path}")
    except subprocess.CalledProcessError as e:
        raise HashError(f"Failed to compute Blake3 hash: {e.stderr}")

def get_sha256_hash(file_path: Union[str, Path], tool_path: str = "sha256sum") -> str:
    """
    Compute the SHA256 hash of a file.
    
    Args:
        file_path: Path to the file.
        tool_path: Path to the sha256sum binary (default: "sha256sum").
        
    Returns:
        The SHA256 hash as a lowercase hexadecimal string.
        
    Raises:
        HashError: If the tool fails, file doesn't exist, or command errors.
    """
    file_path = Path(file_path)
    if not file_path.is_file():
        raise HashError(f"File does not exist: {file_path}")

    try:
        result = subprocess.run(
            [tool_path, str(file_path)],
            capture_output=True,
            text=True,
            check=True
        )
        # Extract just the hash part (before the first space)
        return result.stdout.split()[0].strip()
    except FileNotFoundError:
        raise HashError(f"SHA256 tool not found: {tool_path}")
    except (subprocess.CalledProcessError, IndexError) as e:
        error_msg = getattr(e, 'stderr', str(e))
        raise HashError(f"Failed to compute SHA256 hash: {error_msg}")

def hash_file(file_path: Union[str, Path], algorithms: List[str] = None) -> Dict[str, str]:
    """
    Compute multiple hashes for a file based on specified algorithms.
    
    Args:
        file_path: Path to the file.
        algorithms: List of hash algorithms to use (default: ["blake3", "sha256"]).
        
    Returns:
        Dictionary of algorithm names to hash values.
        
    Raises:
        HashError: If any hash computation fails.
    """
    if algorithms is None:
        algorithms = ["blake3", "sha256"]
    
    file_path = Path(file_path)
    if not file_path.is_file():
        raise HashError(f"File does not exist: {file_path}")
    
    result = {}
    for algorithm in algorithms:
        if algorithm.lower() == "blake3":
            result["blake3"] = get_blake3_hash(file_path)
        elif algorithm.lower() == "sha256":
            result["sha256"] = get_sha256_hash(file_path)
        else:
            logger.warning(f"Unsupported hash algorithm: {algorithm}")
    
    return result
