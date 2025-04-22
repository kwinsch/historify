"""
Implementation of the duplicates command for historify.
"""
import logging
import click
from pathlib import Path
from collections import defaultdict
from typing import Optional, Dict, List, Set, Tuple

from historify.changelog import Changelog, ChangelogError
from historify.config import RepositoryConfig, ConfigError
from historify.csv_manager import CSVManager

logger = logging.getLogger(__name__)

class DuplicatesError(Exception):
    """Exception raised for duplicates-related errors."""
    pass

def find_duplicates(repo_path: str, category: Optional[str] = None) -> Dict[str, List[Dict[str, str]]]:
    """
    Find duplicate files in the repository based on hash values.
    
    Args:
        repo_path: Path to the repository.
        category: Optional category to filter by.
        
    Returns:
        Dictionary with hash as key and list of files as value.
        
    Raises:
        DuplicatesError: If finding duplicates fails.
    """
    repo_path = Path(repo_path).resolve()
    
    try:
        # Initialize config and changelog
        config = RepositoryConfig(str(repo_path))
        changelog = Changelog(str(repo_path))
    except (ConfigError, ChangelogError) as e:
        raise DuplicatesError(f"Failed to initialize repository: {e}")
    
    # Group files by hash
    files_by_hash = defaultdict(list)
    
    # Get all changelog files
    changelog_files = sorted(changelog.changes_dir.glob("changelog-*.csv"))
    if not changelog_files:
        raise DuplicatesError("No changelog files found in repository")
    
    # Process all changelogs to build a map of current files and their hashes
    current_files = {}  # Map of path to {hash, category, size, ...}
    
    for changelog_file in changelog_files:
        try:
            entries = changelog.csv_manager.read_entries(changelog_file)
            
            for entry in entries:
                # Process only entries that describe files (new, move)
                if entry["transaction_type"] not in ["new", "move"]:
                    continue
                    
                # Skip if category filter is provided and doesn't match
                if category and entry["category"] != category:
                    continue
                
                path = entry["path"]
                hash_value = entry["blake3"]
                
                if entry["transaction_type"] == "new":
                    # Add new file
                    current_files[path] = {
                        "hash": hash_value,
                        "category": entry["category"],
                        "size": entry["size"],
                        "timestamp": entry["timestamp"],
                        "path": path
                    }
                elif entry["transaction_type"] == "move":
                    # For moves, the old path is stored in the blake3 field
                    old_path = entry["blake3"]
                    
                    # Remove the old path entry if it exists
                    if old_path in current_files:
                        file_info = current_files.pop(old_path)
                        
                        # Update the path and add back the entry
                        file_info["path"] = path
                        current_files[path] = file_info
                
        except Exception as e:
            logger.warning(f"Error processing changelog {changelog_file}: {e}")
    
    # Now organize files by hash to find duplicates
    for path, file_info in current_files.items():
        hash_value = file_info["hash"]
        files_by_hash[hash_value].append(file_info)
    
    # Keep only hashes with multiple files (duplicates)
    duplicates = {hash_value: files for hash_value, files in files_by_hash.items() 
                 if len(files) > 1}
    
    return duplicates

def handle_duplicates_command(repo_path: str, category: Optional[str] = None) -> None:
    """
    Handle the duplicates command from the CLI.
    
    This finds and displays duplicate files in the repository.
    
    Args:
        repo_path: Path to the repository.
        category: Optional category to filter by.
    """
    try:
        repo_path = Path(repo_path).resolve()
        
        click.echo(f"Finding duplicates in {repo_path}")
        if category:
            click.echo(f"Filtering by category: {category}")
        
        duplicates = find_duplicates(str(repo_path), category)
        
        if not duplicates:
            click.echo("No duplicates found.")
            return
        
        click.echo(f"Found {len(duplicates)} unique file contents with duplicates:")
        click.echo("")
        
        total_duplicates = 0
        wasted_space = 0
        
        # Sort hashes by total size of duplicates (largest first)
        sorted_hashes = sorted(
            duplicates.keys(),
            key=lambda h: sum(int(f["size"]) for f in duplicates[h] if f["size"].isdigit()),
            reverse=True
        )
        
        for i, hash_value in enumerate(sorted_hashes, 1):
            files = duplicates[hash_value]
            total_duplicates += len(files) - 1  # Count duplicates (not the original)
            
            # Calculate wasted space if size is available
            file_size = 0
            if files[0]["size"].isdigit():
                file_size = int(files[0]["size"])
                wasted_space += file_size * (len(files) - 1)
            
            # Display the group
            size_str = f"({file_size} bytes)" if file_size > 0 else ""
            click.echo(f"Group {i}: {len(files)} identical files {size_str}")
            click.echo(f"Hash: {hash_value[:16]}...")
            
            # Sort files by timestamp (oldest first)
            sorted_files = sorted(files, key=lambda f: f["timestamp"])
            
            for j, file_info in enumerate(sorted_files, 1):
                prefix = "Original" if j == 1 else "Duplicate"
                path = file_info["path"]
                category = file_info["category"]
                timestamp = file_info["timestamp"]
                
                click.echo(f"  {prefix}: {path} (Category: {category}, Added: {timestamp})")
            
            # Add a separator between groups unless it's the last one
            if i < len(sorted_hashes):
                click.echo("")
        
        # Display summary
        click.echo("")
        click.echo(f"Summary: {total_duplicates} duplicate files found")
        
        if wasted_space > 0:
            # Format wasted space in human-readable format
            if wasted_space < 1024:
                space_str = f"{wasted_space} bytes"
            elif wasted_space < 1024 * 1024:
                space_str = f"{wasted_space / 1024:.1f} KB"
            elif wasted_space < 1024 * 1024 * 1024:
                space_str = f"{wasted_space / (1024 * 1024):.1f} MB"
            else:
                space_str = f"{wasted_space / (1024 * 1024 * 1024):.1f} GB"
                
            click.echo(f"Wasted space: {space_str}")
        
    except (DuplicatesError, ConfigError, ChangelogError) as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()
