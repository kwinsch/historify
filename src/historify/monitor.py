import os
import logging
from pathlib import Path
from typing import List, Dict, Set
from historify.tools import get_blake3_hash
from historify.config import ConfigError
from historify.db import DatabaseManager

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

class FileMonitor:
    """Monitor file system changes in historify data directories."""
    
    def __init__(self, repo_path: str, db_manager: DatabaseManager):
        self.repo_path = Path(repo_path)
        self.db_manager = db_manager
        self.known_files: Dict[str, str] = {}  # hash -> path mapping

    def load_known_files(self):
        """Load existing files from the database."""
        self.known_files = {}
        try:
            self.db_manager._connect()
            self.db_manager.cursor.execute("SELECT hash, path FROM files")
            self.known_files = {file_hash: path for file_hash, path in self.db_manager.cursor.fetchall()}
            logging.debug(f"Loaded known files: {self.known_files}")
        except sqlite3.Error as e:
            raise ConfigError(f"Failed to load known files: {e}")
        finally:
            self.db_manager._close()

    def scan(self, data_dirs: List[str]) -> List[Dict[str, str]]:
        """
        Scan data directories for changes.

        Args:
            data_dirs: List of relative or absolute paths to data directories.

        Returns:
            List of transactions (type, path, hash, metadata).
        """
        # Load current known files from database
        self.load_known_files()
        
        transactions = []
        current_files: Set[str] = set()
        
        # Scan data directories
        for data_dir in data_dirs:
            # Handle relative or absolute paths
            if Path(data_dir).is_absolute():
                dir_path = Path(data_dir)
            else:
                dir_path = self.repo_path / data_dir
            
            if not dir_path.is_dir():
                logging.debug(f"Skipping non-existent directory: {dir_path}")
                continue
            
            logging.debug(f"Scanning directory: {dir_path}")
            
            for root, _, files in os.walk(dir_path):
                for file_name in files:
                    file_path = Path(root) / file_name
                    # Store paths relative to repo_path for consistency
                    try:
                        rel_path = str(file_path.relative_to(self.repo_path))
                    except ValueError:
                        # If file_path is outside repo_path, use absolute path
                        rel_path = str(file_path)
                    file_hash = get_blake3_hash(str(file_path))
                    current_files.add(rel_path)
                    logging.debug(f"Scanning file: {rel_path}, hash: {file_hash}")
                    
                    # Check for new or moved files
                    if file_hash not in self.known_files:
                        # New file
                        logging.debug(f"New file detected: {rel_path}")
                        transactions.append({
                            "type": "new",
                            "path": rel_path,
                            "hash": file_hash,
                            "metadata": {}
                        })
                        self.db_manager.add_file(str(file_path))
                    elif self.known_files[file_hash] != rel_path:
                        # Moved file
                        logging.debug(f"Move detected: {rel_path}, old path: {self.known_files[file_hash]}")
                        transactions.append({
                            "type": "move",
                            "path": rel_path,
                            "hash": file_hash,
                            "metadata": {"old_path": self.known_files[file_hash]}
                        })
                        self.db_manager.add_file(str(file_path))
        
        # Check for deleted files
        for file_hash, rel_path in self.known_files.items():
            if rel_path not in current_files:
                logging.debug(f"Deleted file detected: {rel_path}")
                transactions.append({
                    "type": "deleted",
                    "path": rel_path,
                    "hash": file_hash,
                    "metadata": {}
                })
                # Optionally remove from database (not implemented here)
        
        logging.debug(f"Generated transactions: {transactions}")
        return transactions