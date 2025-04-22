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

logger = logging.getLogger(__name__)

class SnapshotError(Exception):
    """Exception raised for snapshot-related errors."""
    pass

def create_snapshot(repo_path: str, output_path: str, verify_first: bool = True) -> bool:
    """
    Create a compressed snapshot archive of the repository.
    
    Args:
        repo_path: Path to the repository.
        output_path: Path where the snapshot archive should be saved.
        verify_first: Whether to verify the repository integrity before creating the snapshot.
        
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
        
        # Create the archive
        with tarfile.open(output_path, "w:gz") as tar:
            # Add the entire repository directory
            tar.add(repo_path, arcname=repo_path.name)
        
        logger.info(f"Created snapshot at {output_path}")
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

def handle_snapshot_command(output_path: str, repo_path: str) -> None:
    """
    Handle the snapshot command from the CLI.
    
    Args:
        output_path: Path where the snapshot archive should be saved.
        repo_path: Path to the repository.
    """
    try:
        repo_path = Path(repo_path).resolve()
        
        click.echo(f"Creating snapshot from {repo_path} to {output_path}")
        
        success = create_snapshot(str(repo_path), output_path)
        
        if success:
            click.echo(f"Snapshot created successfully: {output_path}")
        else:
            click.echo("Failed to create snapshot", err=True)
            raise click.Abort()
            
    except SnapshotError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()
