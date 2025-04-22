"""
Implementation of lifecycle commands (start, closing) for historify.
"""
import logging
import getpass
import click
from pathlib import Path
from historify.changelog import Changelog, ChangelogError

logger = logging.getLogger(__name__)

def handle_start_command(repo_path: str, password: str = None) -> None:
    """
    Handle the start command from the CLI.
    
    This signs the current state and creates a new changelog file.
    
    Args:
        repo_path: Path to the repository.
        password: Optional password for the minisign key.
    """
    try:
        repo_path = Path(repo_path).resolve()
        changelog = Changelog(str(repo_path))
        
        # Check if password is needed but not provided
        if password is None and changelog.minisign_key:
            # Check if the key appears to be encrypted
            with open(changelog.minisign_key, "r") as f:
                first_line = f.readline()
                # Keys with 'encrypted' in the comment are encrypted
                if "encrypted" in first_line.lower():
                    password = getpass.getpass("Minisign key password: ")
        
        # Start a new period
        click.echo(f"Starting new transaction period in {repo_path}")
        success, message = changelog.start_closing(password)
        
        if success:
            click.echo(f"Success: {message}")
        else:
            click.echo(f"Error: {message}", err=True)
            raise click.Abort()
            
    except ChangelogError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()

def handle_closing_command(repo_path: str, password: str = None) -> None:
    """
    Handle the closing command from the CLI.
    
    This is functionally equivalent to the start command.
    
    Args:
        repo_path: Path to the repository.
        password: Optional password for the minisign key.
    """
    # The closing command is functionally the same as start
    handle_start_command(repo_path, password)
