"""
Implementation of the add-category command for historify.
"""
import logging
import click
import os
from pathlib import Path
from datetime import datetime, UTC
from historify.config import RepositoryConfig, ConfigError
from historify.changelog import Changelog, ChangelogError

logger = logging.getLogger(__name__)

class CategoryError(Exception):
    """Exception raised for category-related errors."""
    pass

def handle_add_category_command(repo_path: str, category_name: str, data_path: str) -> None:
    """
    Handle the add-category command from the CLI.
    
    Args:
        repo_path: Path to the repository.
        category_name: Name of the category to add.
        data_path: Path to the category data directory.
    """
    try:
        repo_path = Path(repo_path).resolve()
        
        # Validate category name
        if not category_name or '.' in category_name:
            raise CategoryError(f"Invalid category name: '{category_name}'. "
                             f"Name should not be empty or contain dots.")

        # Get repository configuration
        try:
            config = RepositoryConfig(str(repo_path))
        except ConfigError as e:
            raise CategoryError(f"Repository configuration error: {e}")
        
        # Check if category already exists
        all_config = config.list_all()
        category_path_key = f"category.{category_name}.path"
        
        if category_path_key in all_config:
            raise CategoryError(f"Category '{category_name}' already exists with path: {all_config[category_path_key]}")
        
        # Resolve data path - could be relative to repo or absolute
        data_path_obj = Path(data_path)
        if not data_path_obj.is_absolute():
            # If relative, make it relative to the repository
            full_data_path = repo_path / data_path
        else:
            full_data_path = data_path_obj
        
        # Store the path as given by the user, not the resolved path
        # This allows relative paths to be stored correctly
        config.set(category_path_key, data_path)
        
        # Add an optional description config entry (empty for now, can be set later)
        config.set(f"category.{category_name}.description", "")
        
        # Create the directory if it doesn't exist
        full_data_path.mkdir(parents=True, exist_ok=True)
        
        # Log the category transaction
        try:
            changelog = Changelog(str(repo_path))
            current_changelog = changelog.get_current_changelog()
            
            if current_changelog:
                # Add a config transaction entry in the changelog
                timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
                entry = {
                    "timestamp": timestamp,
                    "transaction_type": "config",
                    "path": f"category.{category_name}.path",
                    "category": category_name,
                    "size": "",
                    "ctime": "",
                    "mtime": "",
                    "sha256": "",
                    "blake3": data_path  # Store the path value in blake3 field
                }
                changelog.csv_manager.append_entry(current_changelog, entry)
                
                # Also log the description entry
                entry = {
                    "timestamp": timestamp,
                    "transaction_type": "config",
                    "path": f"category.{category_name}.description",
                    "category": category_name,
                    "size": "",
                    "ctime": "",
                    "mtime": "",
                    "sha256": "",
                    "blake3": ""  # Empty description
                }
                changelog.csv_manager.append_entry(current_changelog, entry)
                
            else:
                logger.warning("No open changelog file. Configuration changes not logged.")
                
        except ChangelogError as e:
            # We still consider the command successful if only the logging fails
            logger.warning(f"Failed to log category addition: {e}")
        
        is_external = data_path_obj.is_absolute()
        location_type = "external" if is_external else "internal"
        
        click.echo(f"Added category '{category_name}' with {location_type} path: {data_path}")
        click.echo(f"Data directory created at: {full_data_path}")
        
    except (CategoryError, ConfigError) as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()
