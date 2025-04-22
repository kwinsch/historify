"""
Implementation of the init command for historify.
"""
import os
import logging
import click
from pathlib import Path
from historify.repository import Repository, RepositoryError
from historify.hash import hash_file

logger = logging.getLogger(__name__)

def init_repository(repo_path: str, repo_name: str = None) -> bool:
    """
    Initialize a new historify repository.
    
    Args:
        repo_path: Path where the repository should be initialized.
        repo_name: Repository name (defaults to directory name).
        
    Returns:
        True if initialization succeeded.
        
    Raises:
        RepositoryError: If initialization fails.
    """
    try:
        repo = Repository(repo_path, repo_name)
        success = repo.initialize()
        
        # Calculate and log the hash of the seed file
        seed_hash = hash_file(repo.seed_file, algorithms=["blake3", "sha256"])
        logger.info(f"Seed file created with blake3 hash: {seed_hash['blake3']}")
        
        # Note: seed signing would be added here in a real implementation
        # This would require the minisign module for signing
        
        return success
    except RepositoryError as e:
        logger.error(f"Repository initialization failed: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error during repository initialization: {e}")
        raise RepositoryError(f"Unexpected error: {e}")

def handle_init_command(repo_path: str, name: str = None) -> None:
    """
    Handle the init command from the CLI.
    
    Args:
        repo_path: Path where the repository should be initialized.
        name: Repository name (defaults to directory name).
    """
    try:
        repo_path = Path(repo_path).resolve()
        repo_name = name or repo_path.name
        
        click.echo(f"Initializing repository '{repo_name}' at {repo_path}")
        
        if init_repository(str(repo_path), repo_name):
            click.echo(f"Repository '{repo_name}' successfully initialized")
            click.echo(f"Next steps:")
            click.echo(f"  - Configure minisign keys with 'historify config minisign.key <path>'")
            click.echo(f"  - Add a data category with 'historify add-category <name> <path>'")
            click.echo(f"  - Start tracking changes with 'historify start'")
        else:
            click.echo(f"Repository initialization failed")
            
    except RepositoryError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()
