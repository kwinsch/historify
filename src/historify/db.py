import sqlite3
import os
from pathlib import Path
from typing import List, Tuple, Optional
from historify.tools import get_blake3_hash
from historify.config import ConfigError
from datetime import datetime, UTC

class DatabaseManager:
    """Manage SQLite database for historify hash-to-path mappings."""
    
    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path)
        self.db_path = self.repo_path / ".historify/historify.db"
        self.conn = None
        self.cursor = None

    def initialize(self):
        """Initialize the SQLite database with required tables."""
        self._connect()
        try:
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS files (
                    hash TEXT PRIMARY KEY,
                    path TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                )
            """)
            self.conn.commit()
        except sqlite3.Error as e:
            raise ConfigError(f"Failed to initialize database: {e}")
        finally:
            self._close()

    def _connect(self):
        """Connect to the SQLite database."""
        # Ensure .historify directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.cursor = self.conn.cursor()
        except sqlite3.Error as e:
            raise ConfigError(f"Failed to connect to database: {e}")

    def _close(self):
        """Close the database connection."""
        if self.cursor:
            self.cursor.close()
            self.cursor = None
        if self.conn:
            self.conn.close()
            self.conn = None

    def add_file(self, file_path: str):
        """Add a file's hash and path to the database."""
        file_path = Path(file_path)
        if not file_path.is_file():
            raise ConfigError(f"File does not exist: {file_path}")
        
        file_hash = get_blake3_hash(str(file_path))
        rel_path = str(file_path.relative_to(self.repo_path))
        timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
        
        self._connect()
        try:
            self.cursor.execute(
                "INSERT OR REPLACE INTO files (hash, path, timestamp) VALUES (?, ?, ?)",
                (file_hash, rel_path, timestamp)
            )
            self.conn.commit()
        except sqlite3.Error as e:
            raise ConfigError(f"Failed to add file to database: {e}")
        finally:
            self._close()

    def get_file(self, file_hash: str) -> Optional[Tuple[str, str]]:
        """Retrieve the path and timestamp for a given hash."""
        self._connect()
        try:
            self.cursor.execute("SELECT path, timestamp FROM files WHERE hash = ?", (file_hash,))
            result = self.cursor.fetchone()
            return result if result else None
        except sqlite3.Error as e:
            raise ConfigError(f"Failed to retrieve file from database: {e}")
        finally:
            self._close()

    def verify_integrity(self) -> List[Tuple[str, str]]:
        """
        Verify database integrity against the file system.

        Returns:
            List of (hash, path) tuples for missing or mismatched files.
        """
        self._connect()
        try:
            self.cursor.execute("SELECT hash, path FROM files")
            issues = []
            for file_hash, rel_path in self.cursor.fetchall():
                abs_path = self.repo_path / rel_path
                if not abs_path.is_file():
                    issues.append((file_hash, rel_path))
                else:
                    current_hash = get_blake3_hash(str(abs_path))
                    if current_hash != file_hash:
                        issues.append((file_hash, rel_path))
            return issues
        except sqlite3.Error as e:
            raise ConfigError(f"Failed to verify database integrity: {e}")
        finally:
            self._close()

    def close(self):
        """Close the database, logging a closing_db transaction."""
        self._connect()
        try:
            self.conn.commit()
        except sqlite3.Error as e:
            raise ConfigError(f"Failed to close database: {e}")
        finally:
            self._close()