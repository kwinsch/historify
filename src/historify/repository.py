"""
Repository module for historify that handles repository initialization and structure.
"""
import os
import logging
import sqlite3
import secrets
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
        self.db_file = self.db_dir / "cache.db"
        self.seed_file = self.db_dir / "seed.bin"
        self.seed_sig_file = self.seed_file.with_suffix(".bin.minisig")
        self.changes_dir = self.path / "changes"
    
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
            self._initialize_database()
            self._create_seed()
            self._create_config()
            
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
    
    def _initialize_database(self) -> None:
        """Initialize SQLite database with schema."""
        logger.debug(f"Initializing database at {self.db_file}")
        
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        # Files table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS files (
            path TEXT NOT NULL,
            category TEXT NOT NULL,
            size INTEGER,
            ctime TEXT,
            mtime TEXT,
            sha256 TEXT,
            blake3 TEXT NOT NULL PRIMARY KEY,
            timestamp TEXT NOT NULL,
            status TEXT NOT NULL
        )
        """)
        
        # Categories table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            name TEXT PRIMARY KEY,
            path TEXT NOT NULL,
            description TEXT,
            is_external BOOLEAN NOT NULL DEFAULT 0
        )
        """)
        
        # Changelog table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS changelog (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            transaction_type TEXT NOT NULL,
            path TEXT,
            category TEXT,
            metadata TEXT,
            file TEXT
        )
        """)
        
        # Configuration table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            description TEXT
        )
        """)
        
        # Integrity table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS integrity (
            changelog_file TEXT PRIMARY KEY,
            blake3 TEXT NOT NULL,
            signature_file TEXT,
            verified BOOLEAN NOT NULL DEFAULT 0,
            verified_timestamp TEXT
        )
        """)
        
        # Add repository name to config
        cursor.execute(
            "INSERT INTO config (key, value, description) VALUES (?, ?, ?)",
            ("repository.name", self.name, "Repository name")
        )
        
        # Add default configuration
        cursor.execute(
            "INSERT INTO config (key, value, description) VALUES (?, ?, ?)",
            ("hash.algorithms", "blake3,sha256", "Hash algorithms used for file integrity")
        )
        
        conn.commit()
        conn.close()
    
    def _create_seed(self) -> None:
        """Create random seed file."""
        logger.debug(f"Creating seed file at {self.seed_file}")
        
        with open(self.seed_file, "wb") as f:
            f.write(secrets.token_bytes(1024 * 1024))  # 1MB of random data
    
    def _create_config(self) -> None:
        """Create configuration file."""
        logger.debug(f"Creating config file at {self.config_file}")
        
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
