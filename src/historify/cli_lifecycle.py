"""
Implementation of lifecycle commands (start, closing) for historify.
"""
import logging
import os
import click
from pathlib import Path
from historify.changelog import Changelog, ChangelogError
from historify.cli_verify import cli_verify_command

logger = logging.getLogger(__name__)

def handle_start_command(repo_path: str) -> None:
    """
    Handle the start command from the CLI.
    
    This signs the current state and creates a new changelog file.
    An implicit verify is performed before starting.
    
    Args:
        repo_path: Path to the repository.
    """
    try:
        # First perform an implicit verification
        # Use the original repo_path string for verification to match test expectations
        click.echo(f"Performing implicit verification before starting")
        verify_result = cli_verify_command(repo_path, full_chain=False)
        if verify_result != 0:
            click.echo(f"Verification failed with code {verify_result}. Fix issues before starting.", err=True)
            raise click.Abort()
            
        # Now use the resolved path for changelog operations
        repo_path_resolved = Path(repo_path).resolve()
        changelog = Changelog(str(repo_path_resolved))
        
        # Get password from environment variable
        password = os.environ.get("HISTORIFY_PASSWORD")
        
        # If the key exists and no password is provided, issue a warning
        if password is None and changelog.minisign_key:
            logger.warning("HISTORIFY_PASSWORD environment variable not set. "
                         "If an encrypted key is used, signing might fail.")
        
        # Start a new period
        click.echo(f"Starting new transaction period in {repo_path_resolved}")
        success, message = changelog.start_closing(password)
        
        if success:
            click.echo(f"Success: {message}")
        else:
            click.echo(f"Error: {message}", err=True)
            raise click.Abort()
            
    except ChangelogError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()

def handle_closing_command(repo_path: str) -> None:
    """
    Handle the closing command from the CLI.
    
    This is functionally equivalent to the start command.
    
    Args:
        repo_path: Path to the repository.
    """
    # The closing command is functionally the same as start
    handle_start_command(repo_path)