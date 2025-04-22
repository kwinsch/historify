"""
Repository module for historify that handles repository initialization and structure.
"""
import os
import logging
import secrets
import csv
import configparser
from datetime import datetime, UTC
from pathlib import Path
from typing import Optional, Dict

logger = logging.getLogger(__name__)

class RepositoryError(Exception):
    """Exception raised for repository-related errors."""
    pass

class Repository:
    """Manages a historify repository."""
    
    def __init__(self, repo_path: str, name: Optional[str] = None):
        """
        Initialize a Repository object.
        
        Args:
            repo_path: Path to the repository.
            name: Repository name (defaults to directory name).
        """
        self.path = Path(repo_path).resolve()
        self.name = name or self.path.name
        
        # Repository structure paths
        self.db_dir = self.path / "db"
        self.config_file = self.db_dir / "config"
        self.config_csv = self.db_dir / "config.csv"
        self.seed_file = self.db_dir / "seed.bin"
        self.seed_sig_file = self.seed_file.with_suffix(".bin.minisig")
        self.changes_dir = self.path / "changes"
        self.integrity_csv = self.db_dir / "integrity.csv"
    
    def initialize(self) -> bool:
        """
        Initialize a new repository.
        
        Returns:
            True if initialization succeeded.
            
        Raises:
            RepositoryError: If initialization fails.
        """
        logger.info(f"Initializing repository '{self.name}' at {self.path}")
        
        try:
            # Create repository structure
            self._create_dirs()
            self._create_config_files()
            self._create_seed()
            self._create_integrity_csv()
            
            logger.info(f"Repository initialization completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Repository initialization failed: {e}")
            raise RepositoryError(f"Failed to initialize repository: {e}")
    
    def _create_dirs(self) -> None:
        """Create repository directory structure."""
        logger.debug(f"Creating repository directories")
        
        self.db_dir.mkdir(parents=True, exist_ok=True)
        self.changes_dir.mkdir(parents=True, exist_ok=True)
    
    def _create_config_files(self) -> None:
        """Create configuration files."""
        logger.debug(f"Creating config files")
        
        # Create INI config file
        with open(self.config_file, "w") as f:
            f.write(f"[repository]\n")
            f.write(f"name = {self.name}\n")
            f.write(f"created = {datetime.now(UTC).isoformat()}\n")
            f.write(f"\n")
            f.write(f"[hash]\n")
            f.write(f"algorithms = blake3,sha256\n")
            f.write(f"\n")
            f.write(f"[changes]\n")
            f.write(f"directory = changes\n")
        
        # Create CSV config file
        with open(self.config_csv, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["key", "value"])
            writer.writeheader()
            writer.writerow({"key": "repository.name", "value": self.name})
            writer.writerow({"key": "repository.created", "value": datetime.now(UTC).isoformat()})
            writer.writerow({"key": "hash.algorithms", "value": "blake3,sha256"})
            writer.writerow({"key": "changes.directory", "value": "changes"})
    
    def _create_seed(self) -> None:
        """Create random seed file."""
        logger.debug(f"Creating seed file")
        
        with open(self.seed_file, "wb") as f:
            f.write(secrets.token_bytes(1024 * 1024))  # 1MB of random data
    
    def _create_integrity_csv(self) -> None:
        """Create integrity CSV file."""
        logger.debug(f"Creating integrity CSV file")
        
        with open(self.integrity_csv, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "changelog_file", "blake3", "signature_file", "verified", "verified_timestamp"
            ])
            writer.writeheader()
