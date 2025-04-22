"""
Implementation of the scan command for historify.
"""
import os
import logging
import click
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from datetime import datetime, UTC

from historify.changelog import Changelog, ChangelogError
from historify.config import RepositoryConfig, ConfigError
from historify.hash import hash_file, HashError

logger = logging.getLogger(__name__)

class ScanError(Exception):
    """Exception raised for scan-related errors."""
    pass

def get_file_metadata(file_path: Path) -> Dict[str, str]:
    """
    Get metadata for a file including size, timestamps, and hashes.
    
    Args:
        file_path: Path to the file.
        
    Returns:
        Dictionary of metadata.
        
    Raises:
        ScanError: If the file doesn't exist or metadata can't be gathered.
    """
    if not file_path.exists() or not file_path.is_file():
        raise ScanError(f"File does not exist or is not a regular file: {file_path}")
    
    try:
        # Get basic file stats
        stat = file_path.stat()
        
        # Get hashes
        hashes = hash_file(file_path)
        
        # Format timestamps
        ctime = datetime.fromtimestamp(stat.st_ctime, tz=UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
        mtime = datetime.fromtimestamp(stat.st_mtime, tz=UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
        
        return {
            "size": str(stat.st_size),
            "ctime": ctime,
            "mtime": mtime,
            "sha256": hashes.get("sha256", ""),
            "blake3": hashes.get("blake3", "")
        }
    except (OSError, HashError) as e:
        raise ScanError(f"Failed to gather metadata for {file_path}: {e}")

def scan_category(repo_path: Path, category: str, category_path: Path, changelog: Changelog) -> Dict[str, int]:
    """
    Scan a category for file changes and log them.
    
    Args:
        repo_path: Path to the repository.
        category: Category name.
        category_path: Path to the category directory.
        changelog: Changelog object for logging changes.
        
    Returns:
        Dictionary with counts of different types of changes.
        
    Raises:
        ScanError: If scanning fails.
        
    Note:
        Duplicates are not marked separately in the changelog but can be 
        identified using the 'duplicates' command which compares hash values.
    """
    if not category_path.exists():
        raise ScanError(f"Category path does not exist: {category_path}")
    
    # Get the current open changelog
    current_changelog = changelog.get_current_changelog()
    if not current_changelog:
        raise ScanError("No open changelog file. Run 'start' command first.")
    
    # Track counts for statistics
    counts = {
        "new": 0,
        "modified": 0,
        "unchanged": 0,
        "deleted": 0,
        "moved": 0,
        "error": 0
    }
    
    # Get list of files to scan
    files_to_scan = []
    try:
        for root, _, files in os.walk(category_path):
            root_path = Path(root)
            for file in files:
                # Skip dotfiles and special system files
                if file.startswith(".") or file == "Thumbs.db" or file == ".DS_Store":
                    continue
                
                file_path = root_path / file
                if file_path.is_file():
                    files_to_scan.append(file_path)
    except OSError as e:
        raise ScanError(f"Failed to walk directory {category_path}: {e}")
    
    # Process each file
    for file_path in files_to_scan:
        try:
            # Get relative path from category_path
            try:
                rel_path = file_path.relative_to(category_path)
            except ValueError:
                # If file is not relative to category_path (should not happen)
                logger.warning(f"File {file_path} is not relative to category path {category_path}")
                counts["error"] += 1
                continue
            
            # Get metadata
            metadata = get_file_metadata(file_path)
            
            # Create entry for changelog
            timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
            entry = {
                "timestamp": timestamp,
                "transaction_type": "new",  # Default, may change based on logic
                "path": str(rel_path),
                "category": category,
                "size": metadata["size"],
                "ctime": metadata["ctime"],
                "mtime": metadata["mtime"],
                "sha256": metadata["sha256"],
                "blake3": metadata["blake3"]
            }
            
            # TODO: Implement logic to detect file modifications, moves, etc.
            # For now, just log as new
            
            # Write entry to changelog
            changelog.csv_manager.append_entry(current_changelog, entry)
            counts["new"] += 1
            
        except Exception as e:
            logger.error(f"Error processing file {file_path}: {e}")
            counts["error"] += 1
    
    return counts

def handle_scan_command(repo_path: str, category: Optional[str] = None) -> Dict[str, Dict[str, int]]:
    """
    Handle the scan command from the CLI.
    
    Args:
        repo_path: Path to the repository.
        category: Optional category to scan.
        
    Returns:
        Dictionary with scan results by category.
        
    Raises:
        ScanError: If scanning fails.
    """
    repo_path = Path(repo_path).resolve()
    
    try:
        # Initialize config and changelog
        config = RepositoryConfig(str(repo_path))
        changelog = Changelog(str(repo_path))
    except (ConfigError, ChangelogError) as e:
        raise ScanError(f"Failed to initialize repository: {e}")
    
    # Get categories to scan
    categories = {}
    all_config = config.list_all()
    
    for key, value in all_config.items():
        if key.startswith("category.") and key.endswith(".path"):
            cat_name = key.split(".")[1]
            if category and cat_name != category:
                continue
                
            categories[cat_name] = value
    
    if not categories:
        if category:
            raise ScanError(f"Category '{category}' not found")
        else:
            raise ScanError("No categories configured. Use 'add-category' command first.")
    
    # Scan each category
    results = {}
    for cat_name, cat_path in categories.items():
        cat_path = Path(cat_path)
        if not cat_path.is_absolute():
            # Relative path to repository
            cat_path = repo_path / cat_path
            
        logger.info(f"Scanning category '{cat_name}' at {cat_path}")
        
        try:
            results[cat_name] = scan_category(repo_path, cat_name, cat_path, changelog)
        except ScanError as e:
            logger.error(f"Failed to scan category '{cat_name}': {e}")
            results[cat_name] = {"error": 1}
    
    return results

def cli_scan_command(repo_path: str, category: Optional[str] = None) -> None:
    """
    CLI handler for the scan command.
    
    Args:
        repo_path: Path to the repository.
        category: Optional category to scan.
    """
    try:
        if category:
            click.echo(f"Scanning repository at {repo_path} (category: {category})")
        else:
            click.echo(f"Scanning repository at {repo_path}")
        
        results = handle_scan_command(repo_path, category)
        
        # Display results
        for cat_name, counts in results.items():
            click.echo(f"\nCategory: {cat_name}")
            for action, count in counts.items():
                if count > 0:
                    click.echo(f"  {action.capitalize()}: {count}")
                    
        total_files = sum(sum(counts.values()) for counts in results.values())
        total_errors = sum(counts.get("error", 0) for counts in results.values())
        
        click.echo(f"\nTotal files processed: {total_files}")
        if total_errors > 0:
            click.echo(f"Errors: {total_errors}", err=True)
        click.echo("Scan completed successfully")
        
    except ScanError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()