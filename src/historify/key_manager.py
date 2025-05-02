"""
Key management module for historify that handles key backup and retrieval.
"""
import os
import sys
import logging
import shutil
import re
import base64
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
        
        # Read the public key file
        with open(public_key_path, "r") as f:
            lines = f.readlines()
            
        if len(lines) < 2:
            raise KeyError("Invalid public key format: file too short")
            
        # Extract the key ID from the base64 blob (primary method)
        # Format is base64(<signature_algorithm> || <key_id> || <public_key>)
        key_id = None
        try:
            # Get the second line (base64 data) and decode it
            b64_data = lines[1].strip()
            raw_data = base64.b64decode(b64_data)
            
            # The key ID is 8 bytes starting at index 2 (after 'Ed')
            if len(raw_data) >= 10:  # 2 bytes for 'Ed' + 8 bytes for key ID
                # Extract the key ID bytes and convert to hex
                key_id_bytes = raw_data[2:10]
                key_id = key_id_bytes.hex().upper()
                logger.debug(f"Extracted key ID from binary data: {key_id}")
        except Exception as e:
            logger.warning(f"Could not extract key ID from binary data: {e}")
            
        # If base64 extraction failed, try to extract from the comment line (fallback method)
        if not key_id:
            first_line = lines[0].strip()
            if "public key" in first_line:
                match = re.search(r"public key\s+(\w+)", first_line)
                if match:
                    key_id = match.group(1)
                    logger.debug(f"Extracted key ID from comment: {key_id}")
            
        # If we still don't have a key ID, use the filename (last resort fallback)
        if not key_id:
            key_id = public_key_path.stem
            logger.debug(f"Using filename as key ID: {key_id}")
        
        logger.debug(f"Final key ID: {key_id}")
        
        # Create the target file path
        target_path = keys_dir / f"{key_id}.pub"
        
        # If the key already exists with the same content, no need to copy
        if target_path.exists():
            with open(target_path, "r") as existing_file:
                existing_content = ''.join(existing_file.readlines())
                if ''.join(lines) == existing_content:
                    logger.debug(f"Key {key_id} already backed up with identical content")
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