"""
Implementation of the comment command for historify.
"""
import logging
import click
from pathlib import Path
from historify.changelog import Changelog, ChangelogError

logger = logging.getLogger(__name__)

def handle_comment_command(repo_path: str, message: str) -> None:
    """
    Handle the comment command from the CLI.
    
    This adds an administrative comment to the change log.
    
    Args:
        repo_path: Path to the repository.
        message: Comment text to add to the changelog.
    """
    try:
        repo_path = Path(repo_path).resolve()
        changelog = Changelog(str(repo_path))
        
        # Get the current changelog
        current_changelog = changelog.get_current_changelog()
        if not current_changelog:
            click.echo("Error: No open changelog file. Run 'start' command first.", err=True)
            raise click.Abort()
        
        # Write the comment transaction
        success = changelog.write_comment(message)
        
        if success:
            click.echo(f"Comment added to changelog: {current_changelog.name}")
        else:
            click.echo("Failed to add comment to changelog", err=True)
            raise click.Abort()
            
    except ChangelogError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()
