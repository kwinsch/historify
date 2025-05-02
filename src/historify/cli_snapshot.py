# src/historify/cli_snapshot.py
"""
Implementation of the snapshot command for historify.
"""
import os
import logging
import tarfile
import shutil
import click
from pathlib import Path
from typing import List, Optional
from datetime import datetime, UTC

from historify.cli_verify import cli_verify_command
from historify.config import RepositoryConfig
from historify.media_packer import pack_archives_for_media, MediaPackError

logger = logging.getLogger(__name__)

class SnapshotError(Exception):
    """Exception raised for snapshot-related errors."""
    pass

def create_snapshot(repo_path: str, output_path: str, base_filename: str, verify_first: bool = True, full: bool = False, media: Optional[str] = None) -> bool:
    """
    Create a compressed snapshot archive of the repository.
    
    Args:
        repo_path: Path to the repository.
        output_path: Path where the main snapshot archive should be saved.
        base_filename: Base filename (without extension) for all generated files.
        verify_first: Whether to verify the repository integrity before creating the snapshot.
        full: Whether to include external category data in separate archives.
        media: Media type for creating ISO image (currently only bd-r supported).
        
    Returns:
        True if the snapshot was created successfully.
        
    Raises:
        SnapshotError: If creating the snapshot fails.
    """
    try:
        repo_path = Path(repo_path).resolve()
        output_path = Path(output_path)
        output_dir = output_path.parent
        
        # Verify repository integrity first if requested
        if verify_first:
            logger.info("Verifying repository integrity before creating snapshot")
            exit_code = cli_verify_command(str(repo_path), full_chain=False)
            if exit_code != 0:
                raise SnapshotError("Repository integrity check failed. Aborting snapshot creation.")
        
        # Get repository configuration to find categories
        external_categories = {}
        if full:
            config = RepositoryConfig(str(repo_path))
            all_config = config.list_all()
            categories = {}
            
            # Find all categories
            for key, value in all_config.items():
                if key.startswith("category.") and key.endswith(".path"):
                    cat_name = key.split(".")[1]
                    categories[cat_name] = value
            
            # Separate internal and external categories
            for cat_name, cat_path in categories.items():
                cat_path_obj = Path(cat_path)
                if cat_path_obj.is_absolute() and not str(cat_path_obj).startswith(str(repo_path)):
                    # External category (absolute path outside repository)
                    external_categories[cat_name] = cat_path_obj
            
            logger.info(f"Found {len(external_categories)} external categories")
        
        # Create the main repository archive
        with tarfile.open(output_path, "w:gz") as tar:
            # Add the entire repository directory
            tar.add(repo_path, arcname=repo_path.name)
        
        logger.info(f"Created main snapshot at {output_path}")
        
        # List of all archives (main + external categories)
        all_archives = [output_path]
        
        # Create separate archives for external categories if requested
        if full:
            # Create archive for each external category using consistent naming
            created_category_archives = []
            for cat_name, cat_path in external_categories.items():
                if not cat_path.exists():
                    logger.warning(f"External category path doesn't exist: {cat_path}")
                    continue
                
                # Use base_filename for consistent naming
                cat_archive_path = output_dir / f"{base_filename}-{cat_name}.tar.gz"
                
                try:
                    with tarfile.open(cat_archive_path, "w:gz") as tar:
                        # Add the external category directory with its actual name as the root
                        tar.add(cat_path, arcname=cat_path.name)
                    
                    logger.info(f"Created external category snapshot for '{cat_name}' at {cat_archive_path}")
                    created_category_archives.append(cat_archive_path)
                    all_archives.append(cat_archive_path)
                except Exception as e:
                    logger.error(f"Error creating archive for category '{cat_name}': {e}")
        
        # Handle media creation if requested
        if media:
            try:
                # For BD-R media or when just --media is specified (default to bd-r)
                media_type = "bd-r"
                if isinstance(media, str) and media.lower() != "bd-r":
                    media_type = media.lower()
                
                logger.info(f"Packing archives for {media_type} media")
                
                # Create base ISO path
                iso_base_path = output_dir / f"{base_filename}"
                
                # Create ISO image(s) for BD-R with repository path for metadata
                iso_files = pack_archives_for_media(all_archives, iso_base_path, media_type=media_type, repo_path=str(repo_path))
                
                if iso_files:
                    logger.info(f"Created {len(iso_files)} ISO image(s) for {media_type} media")
                    for iso_file in iso_files:
                        logger.info(f"  - {iso_file}")
            except MediaPackError as e:
                logger.warning(f"Failed to create media image: {e}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error creating snapshot: {e}")
        if output_path.exists():
            # Clean up partial snapshot file on error
            try:
                output_path.unlink()
            except:
                pass
        raise SnapshotError(f"Failed to create snapshot: {e}")

def handle_snapshot_command(output_dir: str, repo_path: str, name: Optional[str] = None, full: bool = False, media = False) -> None:
    """
    Handle the snapshot command from the CLI.
    
    Args:
        output_dir: Directory where output files will be saved.
        repo_path: Path to the repository.
        name: Base name for output files (defaults to repository name).
        full: Whether to include external category data in separate archives.
        media: Media type for creating ISO image (default: "bd-r").
    """
    try:
        # Resolve paths
        repo_path = Path(repo_path).resolve()
        output_dir = Path(output_dir).resolve()
        
        # Ensure output directory exists
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Get repo name if name is not provided
        if not name:
            try:
                config = RepositoryConfig(str(repo_path))
                name = config.get("repository.name")
                if not name:
                    name = repo_path.name
            except Exception as e:
                logger.warning(f"Could not get repository name: {e}")
                name = repo_path.name

        # Sanitize name (ASCII, no spaces, etc.)
        sanitized_name = "".join(c for c in name if c.isalnum() or c in "-_").strip()
        if not sanitized_name:
            sanitized_name = "snapshot"  # Fallback if name is empty after sanitization
            
        # Add date to base name (YYYY-MM-DD format)
        date_str = datetime.now(UTC).strftime("%Y-%m-%d")
        base_filename = f"{sanitized_name}_{date_str}"
        
        # Create paths for output files
        main_archive_path = output_dir / f"{base_filename}.tar.gz"
        
        # Log info
        if full:
            click.echo(f"Creating full snapshot from {repo_path} to {output_dir}/ (including external categories)")
        else:
            click.echo(f"Creating snapshot from {repo_path} to {output_dir}/")
        click.echo(f"Using base name: {base_filename}")
        
        if media:
            media_type = "bd-r"
            if isinstance(media, str) and media.lower() != "true":
                media_type = media.lower()
            click.echo(f"Will create media image of type: {media_type}")
        
        # Create the snapshot with new parameters
        success = create_snapshot(str(repo_path), str(main_archive_path), base_filename, full=full, media=media)
        
        if success:
            click.echo(f"Snapshot created successfully: {main_archive_path}")
            
            # Count files created for logging
            archive_count = 1  # Main archive always exists
            
            if full:
                # List all category archives that were created
                category_archives = list(output_dir.glob(f"{base_filename}-*.tar.gz"))
                if category_archives:
                    click.echo("External category archives created:")
                    for archive in category_archives:
                        if archive.name != main_archive_path.name:
                            click.echo(f"  - {archive.name}")
                    archive_count += len(category_archives)
            
            iso_count = 0
            if media:
                # Look for ISO files that were created
                iso_files = list(output_dir.glob(f"{base_filename}*.iso"))
                if iso_files:
                    click.echo("Media image files created:")
                    for iso_file in iso_files:
                        click.echo(f"  - {iso_file.name}")
                    iso_count = len(iso_files)
            
            # Log the snapshot action in the changelog
            try:
                from historify.changelog import Changelog
                changelog = Changelog(str(repo_path))
                
                snapshot_type = []
                if full:
                    snapshot_type.append("full")
                if media:
                    snapshot_type.append("media")
                
                type_str = " ".join(snapshot_type) if snapshot_type else "basic"
                details = f"{archive_count} archive(s), {iso_count} ISO(s), '{base_filename}' to {output_dir}"
                
                changelog.log_action(f"Snapshot {type_str}", details)
            except Exception as e:
                # Just log this but don't alter the function's behavior
                logger.warning(f"Failed to log snapshot action: {e}")
        else:
            click.echo("Failed to create snapshot", err=True)
            raise click.Abort()
            
    except SnapshotError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()