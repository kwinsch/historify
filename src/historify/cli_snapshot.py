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

from historify.cli_verify import cli_verify_command
from historify.config import RepositoryConfig
from historify.media_packer import pack_archives_for_media, MediaPackError

logger = logging.getLogger(__name__)

class SnapshotError(Exception):
    """Exception raised for snapshot-related errors."""
    pass

def create_snapshot(repo_path: str, output_path: str, verify_first: bool = True, full: bool = False, media: Optional[str] = None) -> bool:
    """
    Create a compressed snapshot archive of the repository.
    
    Args:
        repo_path: Path to the repository.
        output_path: Path where the snapshot archive should be saved.
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
        
        # Verify repository integrity first if requested
        if verify_first:
            logger.info("Verifying repository integrity before creating snapshot")
            exit_code = cli_verify_command(str(repo_path), full_chain=False)
            if exit_code != 0:
                raise SnapshotError("Repository integrity check failed. Aborting snapshot creation.")
        
        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Ensure output has .tar.gz extension
        if not output_path.name.endswith('.tar.gz'):
            output_path = output_path.with_suffix('.tar.gz')
        
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
            output_stem = output_path.stem
            output_suffix = output_path.suffix
            output_parent = output_path.parent
            
            # Create archive for each external category
            created_category_archives = []
            for cat_name, cat_path in external_categories.items():
                if not cat_path.exists():
                    logger.warning(f"External category path doesn't exist: {cat_path}")
                    continue
                
                cat_archive_path = output_parent / f"{output_stem}-{cat_name}{output_suffix}"
                
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
                
                # Create ISO image(s) for BD-R
                iso_files = pack_archives_for_media(all_archives, output_path, media_type=media_type)
                
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

def handle_snapshot_command(output_path: str, repo_path: str, full: bool = False, media = False) -> None:
    """
    Handle the snapshot command from the CLI.
    
    Args:
        output_path: Path where the snapshot archive should be saved.
        repo_path: Path to the repository.
        full: Whether to include external category data in separate archives.
        media: Media type for creating ISO image (default: "bd-r").
    """
    try:
        repo_path = Path(repo_path).resolve()
        
        if full:
            click.echo(f"Creating full snapshot from {repo_path} to {output_path} (including external categories)")
        else:
            click.echo(f"Creating snapshot from {repo_path} to {output_path}")
        
        if media:
            media_type = "bd-r"
            if isinstance(media, str) and media.lower() != "true":
                media_type = media.lower()
            click.echo(f"Will create media image of type: {media_type}")
        
        success = create_snapshot(str(repo_path), output_path, full=full, media=media)
        
        if success:
            click.echo(f"Snapshot created successfully: {output_path}")
            if full:
                # Get base name for showing additional archives
                output_path_obj = Path(output_path)
                output_stem = output_path_obj.stem
                output_suffix = output_path_obj.suffix
                output_parent = output_path_obj.parent
                
                # List all category archives that might have been created
                category_archives = list(output_parent.glob(f"{output_stem}-*{output_suffix}"))
                if category_archives:
                    click.echo("External category archives created:")
                    for archive in category_archives:
                        click.echo(f"  - {archive.name}")
            
            if media:
                # Look for ISO files that were created
                output_path_obj = Path(output_path)
                output_stem = output_path_obj.stem
                output_parent = output_path_obj.parent
                
                iso_files = list(output_parent.glob(f"{output_stem}*.iso"))
                if iso_files:
                    click.echo("Media image files created:")
                    for iso_file in iso_files:
                        click.echo(f"  - {iso_file.name}")
        else:
            click.echo("Failed to create snapshot", err=True)
            raise click.Abort()
            
    except SnapshotError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()