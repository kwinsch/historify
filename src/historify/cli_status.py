"""
Implementation of the status command for historify.
"""
import logging
import os
import csv
import click
from pathlib import Path
from datetime import datetime, timedelta, UTC
from typing import Dict, List, Optional, Tuple

from historify.config import RepositoryConfig, ConfigError
from historify.changelog import Changelog, ChangelogError
from historify.csv_manager import CSVManager

logger = logging.getLogger(__name__)

class StatusError(Exception):
    """Exception raised for status-related errors."""
    pass

def get_category_status(repo_path: str, category: str, cat_path: Path) -> Dict:
    """
    Get status information for a specific category.
    
    Args:
        repo_path: Path to the repository.
        category: Category name.
        cat_path: Path to the category directory.
        
    Returns:
        Dictionary with status information.
        
    Raises:
        StatusError: If retrieving status fails.
    """
    try:
        result = {
            "name": category,
            "path": str(cat_path),
            "is_external": cat_path.is_absolute(),
            "exists": cat_path.exists(),
            "file_count": 0,
            "total_size": 0,
        }
        
        # Get file counts and sizes if the directory exists
        if result["exists"]:
            try:
                file_count = 0
                total_size = 0
                
                for root, _, files in os.walk(cat_path):
                    for file in files:
                        file_path = Path(root) / file
                        if file_path.is_file():
                            file_count += 1
                            total_size += file_path.stat().st_size
                
                result["file_count"] = file_count
                result["total_size"] = total_size
                
            except OSError as e:
                logger.warning(f"Error walking directory {cat_path}: {e}")
                result["error"] = str(e)
        
        return result
        
    except Exception as e:
        logger.error(f"Error getting category status: {e}")
        raise StatusError(f"Failed to get status for category {category}: {e}")

def get_changelog_status(repo_path: str) -> Dict:
    """
    Get status information about changelogs.
    
    Args:
        repo_path: Path to the repository.
        
    Returns:
        Dictionary with changelog status information.
        
    Raises:
        StatusError: If retrieving status fails.
    """
    try:
        repo_path = Path(repo_path).resolve()
        changelog = Changelog(str(repo_path))
        
        result = {
            "current_changelog": None,
            "changelog_count": 0,
            "signed_count": 0,
            "recent_changes": 0,
            "last_activity": None,
        }
        
        # Get all changelogs
        changelog_files = sorted(changelog.changes_dir.glob("changelog-*.csv"))
        result["changelog_count"] = len(changelog_files)
        
        # Count signed changelogs
        for changelog_file in changelog_files:
            sig_file = changelog_file.with_suffix(".csv.minisig")
            if sig_file.exists():
                result["signed_count"] += 1
        
        # Get current changelog
        current_changelog = changelog.get_current_changelog()
        if current_changelog:
            result["current_changelog"] = current_changelog.name
            
            # Get recent changes count (last 24 hours)
            yesterday = datetime.now(UTC) - timedelta(days=1)
            
            # Read entries from current changelog
            try:
                entries = changelog.csv_manager.read_entries(current_changelog)
                
                recent_count = 0
                last_timestamp = None
                
                for entry in entries:
                    if entry.get("timestamp"):
                        try:
                            # Parse timestamp as UTC
                            ts_str = entry["timestamp"]
                            ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S UTC").replace(tzinfo=UTC)
                            
                            # Update last activity timestamp
                            if last_timestamp is None or ts > last_timestamp:
                                last_timestamp = ts
                            
                            # Count recent changes
                            if ts > yesterday:
                                recent_count += 1
                                
                        except ValueError:
                            # If timestamp parsing fails, just continue
                            pass
                
                result["recent_changes"] = recent_count
                if last_timestamp:
                    result["last_activity"] = last_timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")
                    
            except Exception as e:
                logger.warning(f"Error reading current changelog: {e}")
        
        return result
        
    except Exception as e:
        logger.error(f"Error getting changelog status: {e}")
        raise StatusError(f"Failed to get changelog status: {e}")

def handle_status_command(repo_path: str, category: Optional[str] = None) -> Dict:
    """
    Handle the status command from the CLI.
    
    Args:
        repo_path: Path to the repository.
        category: Optional category to filter by.
        
    Returns:
        Dictionary with status information.
        
    Raises:
        StatusError: If retrieving status fails.
    """
    try:
        repo_path = Path(repo_path).resolve()
        
        # Initialize config
        config = RepositoryConfig(str(repo_path))
        
        result = {
            "repository": {
                "path": str(repo_path),
                "name": config.get("repository.name", "Unnamed Repository"),
                "created": config.get("repository.created", "Unknown"),
            },
            "categories": {},
            "changelog": {},
        }
        
        # Get categories to check
        categories = {}
        all_config = config.list_all()
        
        for key, value in all_config.items():
            if key.startswith("category.") and key.endswith(".path"):
                cat_name = key.split(".")[1]
                if category and cat_name != category:
                    continue
                    
                categories[cat_name] = value
        
        # Get status for each category
        for cat_name, cat_path_str in categories.items():
            cat_path = Path(cat_path_str)
            if not cat_path.is_absolute():
                # Relative path to repository
                cat_path = repo_path / cat_path
                
            result["categories"][cat_name] = get_category_status(str(repo_path), cat_name, cat_path)
        
        # Get changelog status
        result["changelog"] = get_changelog_status(str(repo_path))
        
        return result
        
    except (ConfigError, ChangelogError, StatusError) as e:
        logger.error(f"Error handling status command: {e}")
        raise StatusError(f"Failed to get repository status: {e}")

def cli_status_command(repo_path: str, category: Optional[str] = None) -> int:
    """
    CLI handler for the status command.
    
    Args:
        repo_path: Path to the repository.
        category: Optional category to filter by.
        
    Returns:
        Exit code: 0 for success, 1 for error.
    """
    try:
        category_str = f" for category '{category}'" if category else ""
        click.echo(f"Status of repository at {repo_path}{category_str}")
        
        status = handle_status_command(repo_path, category)
        
        # Display repository info
        repo_info = status["repository"]
        click.echo(f"\nRepository: {repo_info['name']}")
        if repo_info.get("created"):
            click.echo(f"Created: {repo_info['created']}")
        
        # Display categories info
        if status["categories"]:
            click.echo("\nCategories:")
            for cat_name, cat_info in status["categories"].items():
                # Determine category type
                location_type = "external" if cat_info["is_external"] else "internal"
                
                click.echo(f"  - {cat_name} ({location_type})")
                click.echo(f"    Path: {cat_info['path']}")
                
                if cat_info["exists"]:
                    # Format size in human-readable format
                    size = cat_info["total_size"]
                    if size < 1024:
                        size_str = f"{size} bytes"
                    elif size < 1024 * 1024:
                        size_str = f"{size / 1024:.1f} KB"
                    elif size < 1024 * 1024 * 1024:
                        size_str = f"{size / (1024 * 1024):.1f} MB"
                    else:
                        size_str = f"{size / (1024 * 1024 * 1024):.1f} GB"
                        
                    click.echo(f"    Files: {cat_info['file_count']} ({size_str})")
                else:
                    click.echo(f"    Warning: Directory does not exist")
        
        # Display changelog info
        changelog_info = status["changelog"]
        click.echo("\nChangelog Status:")
        click.echo(f"  Total changelogs: {changelog_info['changelog_count']}")
        click.echo(f"  Signed changelogs: {changelog_info['signed_count']}")
        
        if changelog_info.get("current_changelog"):
            click.echo(f"  Current changelog: {changelog_info['current_changelog']}")
            click.echo(f"  Recent changes (24h): {changelog_info['recent_changes']}")
            
            if changelog_info.get("last_activity"):
                click.echo(f"  Last activity: {changelog_info['last_activity']}")
        else:
            click.echo("  No open changelog. Run 'start' command to create one.")
        
        click.echo("\nDone.")
        return 0
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        return 1
