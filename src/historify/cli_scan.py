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

def walk_directory(directory: Path) -> List[Path]:
    """
    Get all files in a directory recursively, excluding special files.
    
    Args:
        directory: Path to the directory to walk.
        
    Returns:
        List of file paths.
        
    Raises:
        ScanError: If walking the directory fails.
    """
    files = []
    try:
        for root, _, filenames in os.walk(directory):
            root_path = Path(root)
            for filename in filenames:
                # Skip dotfiles and special system files
                if filename.startswith(".") or filename in ["Thumbs.db", ".DS_Store"]:
                    continue
                file_path = root_path / filename
                if file_path.is_file():
                    files.append(file_path)
    except OSError as e:
        raise ScanError(f"Failed to walk directory {directory}: {e}")
        
    return files

def log_change(changelog: Changelog, change_type: str, path: str, category: str, 
              metadata: Dict[str, str], old_path: str = None) -> None:
    """
    Log a file change to the changelog.
    
    Args:
        changelog: Changelog object.
        change_type: Type of change (new, changed, move).
        path: File path.
        category: Category name.
        metadata: File metadata.
        old_path: Previous path for move transactions.
        
    Raises:
        ScanError: If there is no open changelog.
    """
    current_changelog = changelog.get_current_changelog()
    if not current_changelog:
        raise ScanError("No open changelog file. Run 'start' command first.")
        
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    entry = {
        "timestamp": timestamp,
        "transaction_type": change_type,
        "path": path,
        "category": category,
        "size": metadata["size"],
        "ctime": metadata["ctime"],
        "mtime": metadata["mtime"],
        "sha256": metadata["sha256"],
        "blake3": old_path if change_type == "move" else metadata["blake3"]
    }
    
    changelog.csv_manager.append_entry(current_changelog, entry)

def log_deletion(changelog: Changelog, path: str, category: str, file_info: Dict[str, str]) -> None:
    """
    Log a file deletion to the changelog.
    
    Args:
        changelog: Changelog object.
        path: File path.
        category: Category name.
        file_info: Information about the deleted file.
        
    Raises:
        ScanError: If there is no open changelog.
    """
    current_changelog = changelog.get_current_changelog()
    if not current_changelog:
        raise ScanError("No open changelog file. Run 'start' command first.")
        
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    entry = {
        "timestamp": timestamp,
        "transaction_type": "deleted",
        "path": path,
        "category": category,
        "size": "",
        "ctime": "",
        "mtime": "",
        "sha256": "",
        "blake3": file_info["hash"]  # Store the last known hash
    }
    
    changelog.csv_manager.append_entry(current_changelog, entry)

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
        "changed": 0,
        "unchanged": 0,
        "deleted": 0,
        "moved": 0,
        "error": 0
    }
    
    try:
        # Build current file map from all changelogs
        current_files = {}  # Map of path to {hash, size, mtime}
        
        # Process all changelogs to build the current state
        changelog_files = sorted(changelog.changes_dir.glob("changelog-*.csv"))
        for changelog_file in changelog_files:
            try:
                entries = changelog.csv_manager.read_entries(changelog_file)
                
                for entry in entries:
                    if entry["category"] != category:
                        continue
                        
                    path = entry["path"]
                    
                    if entry["transaction_type"] == "new" or entry["transaction_type"] == "changed":
                        current_files[path] = {
                            "hash": entry["blake3"],
                            "size": entry["size"],
                            "mtime": entry["mtime"]
                        }
                    elif entry["transaction_type"] == "deleted" and path in current_files:
                        del current_files[path]
                    elif entry["transaction_type"] == "move":
                        # For moves, the old path is stored in blake3 field
                        old_path = entry["blake3"]
                        if old_path in current_files:
                            del current_files[old_path]
                            current_files[path] = {
                                "hash": entry.get("sha256", ""),  # Fallback if blake3 is used for old_path
                                "size": entry["size"],
                                "mtime": entry["mtime"]
                            }
            except Exception as e:
                logger.warning(f"Error processing changelog {changelog_file}: {e}")
        
        # Get current files on disk
        files_on_disk = {}
        for file_path in walk_directory(category_path):
            try:
                rel_path = str(file_path.relative_to(category_path))
                metadata = get_file_metadata(file_path)
                files_on_disk[rel_path] = metadata
            except Exception as e:
                logger.error(f"Error processing file {file_path}: {e}")
                counts["error"] += 1
        
        # Compare files and detect changes
        
        # Process files on disk (new, changed, unchanged)
        for path, metadata in files_on_disk.items():
            try:
                if path in current_files:
                    # File exists in history - check if changed
                    if metadata["blake3"] != current_files[path]["hash"]:
                        # File content changed
                        log_change(changelog, "changed", path, category, metadata)
                        counts["changed"] += 1
                    else:
                        # File unchanged
                        counts["unchanged"] += 1
                else:
                    # Check if it's a moved file (same hash exists elsewhere)
                    moved = False
                    for old_path, old_info in list(current_files.items()):
                        if old_info["hash"] == metadata["blake3"] and old_path != path:
                            # Same file moved to new location
                            log_change(changelog, "move", path, category, metadata, old_path=old_path)
                            current_files.pop(old_path)  # Remove old path
                            current_files[path] = {"hash": metadata["blake3"], "size": metadata["size"], "mtime": metadata["mtime"]}
                            counts["moved"] += 1
                            moved = True
                            break
                    
                    if not moved:
                        # Truly new file
                        log_change(changelog, "new", path, category, metadata)
                        counts["new"] += 1
            except Exception as e:
                logger.error(f"Error processing path {path}: {e}")
                counts["error"] += 1
        
        # Process deleted files
        for path in list(current_files.keys()):
            if path not in files_on_disk:
                try:
                    # File in history but not on disk - it's been deleted
                    log_deletion(changelog, path, category, {"hash": current_files[path]["hash"]})
                    counts["deleted"] += 1
                except Exception as e:
                    logger.error(f"Error processing deletion for {path}: {e}")
                    counts["error"] += 1
    
    except Exception as e:
        logger.error(f"Error during scan of category {category}: {e}")
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
