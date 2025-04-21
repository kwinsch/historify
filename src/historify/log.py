import csv
import os
from pathlib import Path
from datetime import datetime, UTC
from typing import Optional, Dict, List
from historify.tools import get_blake3_hash
from historify.config import ConfigError

class LogManager:
    """Manage historify transaction logs."""
    
    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path)
        self.log_dir = self.repo_path
        self.required_fields = [
            "timestamp",
            "transaction_type",
            "hash",
            "path",
            "metadata"
        ]
        self.optional_fields = [
            "size",
            "ctime",
            "mtime",
            "sha256",
            "blake3"
        ]
        self.all_fields = self.required_fields + self.optional_fields

    def get_current_log_file(self) -> Path:
        """Return the path to the current month's log file."""
        return self.log_dir / f"translog-{datetime.now(UTC).strftime('%Y-%m')}.csv"

    def write_transaction(
        self,
        transaction_type: str,
        file_path: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None
    ) -> None:
        """
        Write a transaction to the current log file.

        Args:
            transaction_type: Type of transaction (e.g., 'new', 'move').
            file_path: Path to the file (relative to repo).
            metadata: Dictionary of metadata (e.g., {'size': '12345'}).

        Raises:
            ConfigError: If the transaction type or fields are invalid.
        """
        if transaction_type not in [
            "closing_db", "closing_log", "new", "move", "duplicate", "deleted",
            "config", "comment", "seed", "verify"
        ]:
            raise ConfigError(f"Invalid transaction type: {transaction_type}")

        log_file = self.get_current_log_file()
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Prepare transaction data
        timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
        file_hash = ""
        rel_path = ""
        metadata_str = ""
        
        metadata = metadata or {}
        if file_path:
            abs_path = self.repo_path / file_path
            if abs_path.is_file():
                file_hash = get_blake3_hash(str(abs_path))
                rel_path = str(abs_path.relative_to(self.repo_path))
                stat = abs_path.stat()
                metadata.update({
                    "size": str(stat.st_size),
                    "ctime": datetime.fromtimestamp(stat.st_ctime).strftime("%Y-%m-%dT%H:%M:%S"),
                    "mtime": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%dT%H:%M:%S"),
                    "blake3": file_hash
                })
        
        # Format metadata as string
        metadata_str = ",".join(f"{k}={v}" for k, v in metadata.items()) if metadata else ""
        
        row = {
            "timestamp": timestamp,
            "transaction_type": transaction_type,
            "hash": file_hash,
            "path": rel_path,
            "metadata": metadata_str,
            "size": metadata.get("size", ""),
            "ctime": metadata.get("ctime", ""),
            "mtime": metadata.get("mtime", ""),
            "sha256": "",
            "blake3": metadata.get("blake3", "")
        }
        
        # Check for existing log file and validate fields
        file_exists = log_file.exists()
        with log_file.open("a", newline='') as f:
            writer = csv.DictWriter(f, fieldnames=self.all_fields, restval="")
            if not file_exists:
                writer.writeheader()
            writer.writerow(row)
        
        # Provide signing instructions (except for closing_db)
        if transaction_type != "closing_db":
            print(f"Transaction logged to {log_file}. Sign manually with:")
            print(f"  minisign -Sm {log_file} -s <private_key>")

    def read_log(self, log_file: Optional[str] = None) -> List[Dict[str, str]]:
        """
        Read transactions from a log file.

        Args:
            log_file: Path to the log file (defaults to current month).

        Returns:
            List of transaction dictionaries.

        Raises:
            ConfigError: If the log file is invalid or fields are incorrect.
        """
        log_path = Path(log_file) if log_file else self.get_current_log_file()
        if not log_path.is_file():
            raise ConfigError(f"Log file does not exist: {log_path}")
        
        transactions = []
        with log_path.open("r", newline='') as f:
            reader = csv.DictReader(f)
            if not all(field in reader.fieldnames for field in self.required_fields):
                raise ConfigError(f"Invalid log file format: {log_path}")
            
            unsupported = [f for f in reader.fieldnames if f not in self.all_fields]
            if unsupported:
                print(f"Warning: Unsupported fields in {log_path}: {unsupported}")
            
            for row in reader:
                transactions.append(row)
        
        return transactions