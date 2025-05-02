"""
Changelog module for historify that handles transaction logs and signatures.
"""
import os
import csv
import logging
import shutil
from pathlib import Path
from datetime import datetime, UTC
from typing import Optional, Dict, List, Tuple, Any

from historify.config import RepositoryConfig, ConfigError
from historify.hash import hash_file
from historify.minisign import minisign_sign, minisign_verify, MinisignError
from historify.csv_manager import CSVManager, CSVError

logger = logging.getLogger(__name__)

class ChangelogError(Exception):
    """Exception raised for changelog-related errors."""
    pass

class Changelog:
    """Manages historify changelog files and signatures."""
    
    def __init__(self, repo_path: str):
        """
        Initialize a Changelog object.
        
        Args:
            repo_path: Path to the repository.
            
        Raises:
            ChangelogError: If the repository is not properly initialized.
        """
        self.repo_path = Path(repo_path).resolve()
        
        try:
            self.config = RepositoryConfig(repo_path)
        except ConfigError as e:
            raise ChangelogError(f"Repository configuration error: {e}")
        
        self.db_dir = self.repo_path / "db"
        self.seed_file = self.db_dir / "seed.bin"
        self.seed_sig_file = self.seed_file.with_suffix(".bin.minisig")
        
        # Get changes directory from config or use default
        changes_dir = self.config.get("changes.directory", "changes")
        self.changes_dir = self.repo_path / changes_dir
        
        # Ensure changes directory exists
        self.changes_dir.mkdir(parents=True, exist_ok=True)
        
        # Required fields for changelog CSV
        self.required_fields = [
            "timestamp",
            "transaction_type", 
            "path",
            "category",
            "size",
            "ctime",
            "mtime",
            "sha256",
            "blake3"
        ]
        
        # Try to get minisign keys
        self.minisign_key = self.config.get("minisign.key")
        self.minisign_pub = self.config.get("minisign.pub")
        
        # Initialize CSV manager
        self.csv_manager = CSVManager(repo_path)
    
    def get_current_changelog(self) -> Optional[Path]:
        """
        Get the path to the current open changelog file.
        
        Returns:
            Path to the current changelog file, or None if no open changelog.
        """
        # List all changelog files
        changelog_files = sorted(self.changes_dir.glob("changelog-*.csv"))
        
        # Check each file to see if it's signed
        for changelog_file in reversed(changelog_files):  # Start with most recent
            sig_file = changelog_file.with_suffix(".csv.minisig")
            if not sig_file.exists():
                return changelog_file
        
        # No open changelog file found
        return None
    
    def get_latest_changelog(self) -> Optional[Path]:
        """
        Get the path to the latest changelog file (signed or not).
        
        Returns:
            Path to the latest changelog file, or None if no changelog.
        """
        changelog_files = sorted(self.changes_dir.glob("changelog-*.csv"))
        return changelog_files[-1] if changelog_files else None
    
    def create_new_changelog(self) -> Path:
        """
        Create a new changelog file with today's date.
        
        Returns:
            Path to the new changelog file.
            
        Raises:
            ChangelogError: If there is already an open changelog.
        """
        # Check if there is an open changelog
        current = self.get_current_changelog()
        if current:
            raise ChangelogError(f"There is already an open changelog: {current.name}")
        
        # Create a new changelog file
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        new_changelog = self.changes_dir / f"changelog-{today}.csv"
        
        # Check if this file already exists (unlikely but possible)
        counter = 1
        while new_changelog.exists():
            new_changelog = self.changes_dir / f"changelog-{today}-{counter}.csv"
            counter += 1
        
        # Create and initialize the new changelog file
        try:
            self.csv_manager.create_csv_file(new_changelog)
        except CSVError as e:
            raise ChangelogError(f"Failed to create new changelog: {e}")
        
        logger.info(f"Created new changelog file: {new_changelog}")
        return new_changelog
    
    def sign_file(self, file_path: Path, password: Optional[str] = None) -> bool:
        """
        Sign a file using minisign.
        
        Args:
            file_path: Path to the file to sign.
            password: Optional password for the minisign key.
            
        Returns:
            True if signing succeeded.
            
        Raises:
            ChangelogError: If signing fails or minisign keys are not configured.
        """
        if not self.minisign_key:
            raise ChangelogError("Minisign private key not configured")
        
        if not Path(self.minisign_key).exists():
            raise ChangelogError(f"Minisign private key not found: {self.minisign_key}")
        
        try:
            # Determine if the key is unencrypted
            with open(self.minisign_key, "r") as f:
                first_line = f.readline()
                # Keys with 'encrypted' in the comment are encrypted
                unencrypted = "encrypted" not in first_line.lower()
            
            # Log appropriate message about password usage
            if not unencrypted and password is None:
                logger.warning("Attempting to sign with encrypted key but no password provided")
                logger.info("Note: You can set HISTORIFY_PASSWORD environment variable")
                # Provide a clear indication that password is needed
                print("Enter password for encrypted minisign key (or set HISTORIFY_PASSWORD env variable):")
            elif not unencrypted and password is not None:
                logger.debug("Using provided password for encrypted key")
            elif unencrypted:
                logger.debug("Using unencrypted key - no password needed")
            
            result = minisign_sign(
                str(file_path),
                self.minisign_key,
                password=password,
                unencrypted=unencrypted
            )
            
            if not result:
                raise ChangelogError(f"Failed to sign file: {file_path}")
            
            logger.info(f"Successfully signed file: {file_path}")
            return True
            
        except MinisignError as e:
            raise ChangelogError(f"Minisign error: {e}")
    
    def sync_file(self, file_path: Path) -> None:
        """
        Sync a file to disk to ensure changes are written.
        
        Args:
            file_path: Path to the file to sync.
        """
        try:
            # Open the file in append mode (doesn't truncate the file)
            with open(file_path, "a") as f:
                # Force OS to sync file to disk
                os.fsync(f.fileno())
            logger.debug(f"File synced to disk: {file_path}")
        except Exception as e:
            logger.warning(f"Failed to sync file to disk (continuing anyway): {e}")
    
    def write_closing_transaction(self, prev_file: Optional[Path] = None) -> bool:
        """
        Write a closing transaction to the current changelog.
        
        Args:
            prev_file: Optional path to the previous file (changelog or seed).
            
        Returns:
            True if the transaction was written successfully.
            
        Raises:
            ChangelogError: If there is no open changelog or writing fails.
        """
        # Get the current changelog
        changelog_file = self.get_current_changelog()
        if not changelog_file:
            raise ChangelogError("No open changelog file. Run 'start' command first.")
        
        # Prepare the transaction
        timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
        transaction = {
            "timestamp": timestamp,
            "transaction_type": "closing",
            "path": "",
            "category": "",
            "size": "",
            "ctime": "",
            "mtime": "",
            "sha256": "",
            "blake3": ""
        }
        
        # If we have a previous file, add its hash to the blake3 field
        if prev_file and prev_file.exists():
            # Ensure the file is completely written to disk before hashing
            self.sync_file(prev_file)
            
            # Calculate hash after ensuring file is synced
            hash_result = hash_file(prev_file)
            transaction["blake3"] = hash_result["blake3"]
            logger.debug(f"Using hash for closing transaction: {transaction['blake3']}")
            
            if prev_file.name == "seed.bin":
                transaction["path"] = "db/seed.bin"
            else:
                transaction["path"] = f"changes/{prev_file.name}"
        
        # Write the transaction to the changelog
        try:
            self.csv_manager.append_entry(changelog_file, transaction)
            
            logger.info(f"Wrote closing transaction to {changelog_file}")
            
            # Update integrity info
            blake3_hash = hash_file(changelog_file)["blake3"]
            signature_file = f"{changelog_file.name}.minisig"
            verified_timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
            
            self.csv_manager.update_integrity_info(
                changelog_file.name,
                blake3_hash,
                signature_file,
                True,  # Considered verified when signed
                verified_timestamp
            )
            
            return True
            
        except CSVError as e:
            raise ChangelogError(f"Failed to write transaction: {e}")
    
    def write_comment(self, message: str) -> bool:
        """
        Write a comment transaction to the current changelog.
        
        Args:
            message: Comment text to add to the changelog.
            
        Returns:
            True if the comment was written successfully.
            
        Raises:
            ChangelogError: If there is no open changelog or writing fails.
        """
        # Get the current changelog
        changelog_file = self.get_current_changelog()
        if not changelog_file:
            raise ChangelogError("No open changelog file. Run 'start' command first.")
        
        # Prepare the transaction
        timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
        transaction = {
            "timestamp": timestamp,
            "transaction_type": "comment",
            "path": "",
            "category": "",
            "size": "",
            "ctime": "",
            "mtime": "",
            "sha256": "",
            "blake3": message  # Store the comment in the blake3 field
        }
        
        # Write the transaction to the changelog
        try:
            self.csv_manager.append_entry(changelog_file, transaction)
            
            logger.info(f"Wrote comment to {changelog_file}: {message}")
            return True
            
        except CSVError as e:
            raise ChangelogError(f"Failed to write comment: {e}")
            
    def log_action(self, action: str, details: str = None) -> bool:
        """
        Log an action as a comment in the changelog.
        This is a helper method for system actions that should be documented.
        
        Args:
            action: Short action description (e.g., "Verify", "Snapshot")
            details: Optional additional details about the action
            
        Returns:
            True if the comment was written successfully, False if it fails or
            if there's no open changelog (will not raise an exception).
        """
        try:
            message = f"System: {action}"
            if details:
                message += f" - {details}"
                
            return self.write_comment(message)
        except ChangelogError as e:
            # Just log the error but don't raise an exception
            # This ensures the main command can still complete even if logging fails
            logger.warning(f"Failed to log action '{action}': {e}")
            return False
    
    def start_closing(self, password: Optional[str] = None) -> Tuple[bool, str]:
        """
        Start a new transaction period or close the current one.
        
        This signs the current changelog or seed file and creates a new changelog.
        
        Args:
            password: Optional password for the minisign key.
            
        Returns:
            Tuple of (success, message).
            
        Raises:
            ChangelogError: If signing fails or there are other issues.
        """
        # Check minisign configuration
        if not self.minisign_key or not self.minisign_pub:
            raise ChangelogError("Minisign keys not configured. Use 'config minisign.key' and 'config minisign.pub'.")
        
        # Get the current open changelog
        current_changelog = self.get_current_changelog()
        
        # If no open changelog, check if we need to sign the seed
        if not current_changelog:
            if not self.seed_sig_file.exists():
                # Sign the seed file
                try:
                    logger.info("No open changelog. Signing the seed file.")
                    self.sign_file(self.seed_file, password)
                    
                    # Ensure the file is written to disk
                    self.sync_file(self.seed_file)
                    self.sync_file(self.seed_sig_file)
                    
                    # Create the first changelog and add a closing entry
                    new_changelog = self.create_new_changelog()
                    
                    # Write a closing transaction referencing the seed
                    self.write_closing_transaction(self.seed_file)
                    
                    return True, f"Signed seed file and created first changelog: {new_changelog.name}"
                    
                except (MinisignError, ChangelogError) as e:
                    return False, f"Failed to sign seed file: {e}"
            else:
                # Seed is already signed, create a new changelog
                try:
                    new_changelog = self.create_new_changelog()
                    
                    # Get the latest signed changelog
                    latest_signed = None
                    for changelog in sorted(self.changes_dir.glob("changelog-*.csv")):
                        sig_file = changelog.with_suffix(".csv.minisig")
                        if sig_file.exists():
                            latest_signed = changelog
                    
                    # Write a closing transaction referencing the previous changelog or seed
                    if latest_signed:
                        # Ensure the file is written to disk
                        self.sync_file(latest_signed)
                        self.sync_file(latest_signed.with_suffix(".csv.minisig"))
                        
                        self.write_closing_transaction(latest_signed)
                    else:
                        # If no previous changelog, reference the seed
                        self.sync_file(self.seed_file)
                        self.sync_file(self.seed_sig_file)
                        
                        self.write_closing_transaction(self.seed_file)
                    
                    return True, f"Created new changelog: {new_changelog.name}"
                    
                except ChangelogError as e:
                    return False, f"Failed to create new changelog: {e}"
        else:
            # We have an open changelog, close it by signing
            try:
                # Sign the current changelog
                logger.debug(f"Signing file: {current_changelog}")
                self.sign_file(current_changelog, password)
                
                # Ensure the file and signature are written to disk
                self.sync_file(current_changelog)
                sig_file = current_changelog.with_suffix(".csv.minisig")
                self.sync_file(sig_file)
                
                # Calculate hash after ensuring file is synced
                prev_hash = hash_file(current_changelog)["blake3"]
                logger.debug(f"Hash of signed file: {prev_hash}")
                
                # Create a new changelog
                new_changelog = self.create_new_changelog()
                
                # Write a closing transaction referencing the previous changelog
                self.write_closing_transaction(current_changelog)
                
                return True, f"Signed {current_changelog.name} and created new changelog: {new_changelog.name}"
                
            except (MinisignError, ChangelogError) as e:
                return False, f"Failed to close changelog: {e}"
