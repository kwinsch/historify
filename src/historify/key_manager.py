# src/historify/key_manager.py
"""
Key management module for historify that handles key backup and retrieval.
"""
import os
import logging
import shutil
from pathlib import Path
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)

class KeyError(Exception):
    """Exception raised for key-related errors."""
    pass

def backup_public_key(repo_path: str, public_key_path: str) -> Optional[str]:
    """
    Backup a public key to the repository's keys directory.
    
    Args:
        repo_path: Path to the repository.
        public_key_path: Path to the public key to backup.
        
    Returns:
        The key ID if the key was backed up successfully, None otherwise.
        
    Raises:
        KeyError: If the backup fails.
    """
    try:
        repo_path = Path(repo_path).resolve()
        public_key_path = Path(public_key_path).resolve()
        
        # Ensure the key exists
        if not public_key_path.exists():
            raise KeyError(f"Public key does not exist: {public_key_path}")
        
        # Create the keys directory if it doesn't exist
        keys_dir = repo_path / "db" / "keys"
        keys_dir.mkdir(parents=True, exist_ok=True)
        
        # Extract the key ID from the first line
        key_id = None
        with open(public_key_path, "r") as f:
            first_line = f.readline().strip()
            # Extract the key ID from the comment line
            # Format is usually: "untrusted comment: minisign public key KEYID"
            if "public key" in first_line:
                parts = first_line.split()
                if len(parts) > 0:
                    key_id = parts[-1]
            
            # If key ID couldn't be extracted, use the filename
            if not key_id:
                key_id = public_key_path.stem
        
        # Create the target file path
        target_path = keys_dir / f"{key_id}.pub"
        
        # If the key already exists with the same content, no need to copy
        if target_path.exists():
            with open(public_key_path, "rb") as src_file, open(target_path, "rb") as target_file:
                if src_file.read() == target_file.read():
                    logger.debug(f"Key {key_id} already backed up")
                    return key_id
        
        # Copy the key file
        shutil.copy2(public_key_path, target_path)
        logger.info(f"Backed up public key {key_id} to {target_path}")
        
        return key_id
        
    except Exception as e:
        logger.error(f"Failed to backup public key: {e}")
        raise KeyError(f"Failed to backup public key: {e}")

def find_public_key_by_id(repo_path: str, key_id: str) -> Optional[Path]:
    """
    Find a public key by its ID in the repository's keys directory.
    
    Args:
        repo_path: Path to the repository.
        key_id: ID of the key to find.
        
    Returns:
        Path to the public key file if found, None otherwise.
    """
    try:
        repo_path = Path(repo_path).resolve()
        keys_dir = repo_path / "db" / "keys"
        
        if not keys_dir.exists():
            return None
        
        # Look for exact match first
        key_file = keys_dir / f"{key_id}.pub"
        if key_file.exists():
            return key_file
        
        # If not found, try to find a key that contains the ID in its name
        for key_file in keys_dir.glob("*.pub"):
            if key_id in key_file.stem:
                return key_file
        
        return None
        
    except Exception as e:
        logger.error(f"Error finding public key: {e}")
        return None

def list_backed_up_keys(repo_path: str) -> List[Dict[str, str]]:
    """
    List all backed up public keys in the repository.
    
    Args:
        repo_path: Path to the repository.
        
    Returns:
        List of dictionaries with key info (id, path).
    """
    try:
        repo_path = Path(repo_path).resolve()
        keys_dir = repo_path / "db" / "keys"
        
        if not keys_dir.exists():
            return []
        
        keys = []
        for key_file in keys_dir.glob("*.pub"):
            keys.append({
                "id": key_file.stem,
                "path": str(key_file)
            })
        
        return keys
        
    except Exception as e:
        logger.error(f"Error listing backed up keys: {e}")
        return []