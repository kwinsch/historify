"""
Implementation of the log command for historify.
"""
import logging
import csv
import click
from pathlib import Path
from typing import Optional, List, Dict
from historify.changelog import Changelog, ChangelogError

logger = logging.getLogger(__name__)

def handle_log_command(repo_path: str, log_file: Optional[str] = None, category: Optional[str] = None) -> None:
    """
    Handle the log command from the CLI.
    
    This displays change history from logs.
    
    Args:
        repo_path: Path to the repository.
        log_file: Optional specific changelog file to display.
        category: Optional category to filter by.
    """
    try:
        repo_path = Path(repo_path).resolve()
        changelog = Changelog(str(repo_path))
        
        # Get the changes directory
        changes_dir = changelog.changes_dir
        
        # Determine which log file to show
        target_log = None
        if log_file:
            # Use specified log file
            if log_file.startswith("changelog-") and log_file.endswith(".csv"):
                target_log = changes_dir / log_file
            else:
                target_log = changes_dir / f"changelog-{log_file}.csv"
        else:
            # Use current log if available, otherwise use the latest log
            current_log = changelog.get_current_changelog()
            if current_log:
                target_log = current_log
            else:
                # Find the latest log
                log_files = sorted(changes_dir.glob("changelog-*.csv"))
                if log_files:
                    target_log = log_files[-1]
        
        if not target_log or not target_log.exists():
            click.echo(f"Error: No changelog file found.", err=True)
            raise click.Abort()
        
        # Read and display the log entries
        entries = read_log_entries(target_log, category)
        
        if not entries:
            log_info = f" ({target_log.name})"
            category_info = f" for category '{category}'" if category else ""
            click.echo(f"No entries found{log_info}{category_info}.")
            return
            
        # Display the log
        click.echo(f"Changelog: {target_log.name}")
        if category:
            click.echo(f"Filtered by category: {category}")
        click.echo("-" * 80)
        
        for i, entry in enumerate(entries, 1):
            display_log_entry(i, entry)
            if i < len(entries):
                click.echo("-" * 40)
        
    except ChangelogError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()

def read_log_entries(log_file: Path, category: Optional[str] = None) -> List[Dict[str, str]]:
    """
    Read entries from a changelog file.
    
    Args:
        log_file: Path to the changelog file.
        category: Optional category to filter by.
        
    Returns:
        List of entry dictionaries.
    """
    entries = []
    
    try:
        with open(log_file, "r", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Apply category filter if specified
                if category and (not row.get("category") or row["category"] != category):
                    continue
                entries.append(row)
    except Exception as e:
        logger.error(f"Error reading log file: {e}")
        raise ChangelogError(f"Failed to read log file: {e}")
    
    return entries

def display_log_entry(num: int, entry: Dict[str, str]) -> None:
    """
    Display a formatted log entry.
    
    Args:
        num: Entry number for display.
        entry: Entry dictionary.
    """
    # Format the output based on transaction type
    entry_type = entry.get("transaction_type", "unknown")
    
    # Basic info for all entry types
    click.echo(f"Entry #{num} - {entry.get('timestamp', 'No timestamp')}")
    click.echo(f"Type: {entry_type}")
    
    # Display fields relevant to each transaction type
    if entry_type == "closing":
        click.echo(f"Previous file: {entry.get('path', 'None')}")
        if entry.get("blake3"):
            click.echo(f"Previous hash: {entry.get('blake3')}")
    
    elif entry_type == "new":
        click.echo(f"Path: {entry.get('path', 'None')}")
        if entry.get("category"):
            click.echo(f"Category: {entry.get('category')}")
        if entry.get("size"):
            click.echo(f"Size: {entry.get('size')} bytes")
        if entry.get("blake3"):
            click.echo(f"BLAKE3: {entry.get('blake3')}")
        if entry.get("sha256"):
            click.echo(f"SHA256: {entry.get('sha256')}")
    
    elif entry_type == "changed":
        click.echo(f"Path: {entry.get('path', 'None')}")
        if entry.get("category"):
            click.echo(f"Category: {entry.get('category')}")
        if entry.get("size"):
            click.echo(f"Size: {entry.get('size')} bytes")
        if entry.get("blake3"):
            click.echo(f"BLAKE3: {entry.get('blake3')}")
        if entry.get("sha256"):
            click.echo(f"SHA256: {entry.get('sha256')}")
    
    elif entry_type == "move":
        click.echo(f"New path: {entry.get('path', 'None')}")
        if entry.get("category"):
            click.echo(f"Category: {entry.get('category')}")
        # Old path is stored in blake3 field
        if entry.get("blake3"):
            click.echo(f"Old path: {entry.get('blake3')}")
    
    elif entry_type == "deleted":
        click.echo(f"Deleted path: {entry.get('path', 'None')}")
        if entry.get("category"):
            click.echo(f"Category: {entry.get('category')}")
        # Sometimes the hash of deleted file is stored in blake3
        if entry.get("blake3"):
            click.echo(f"File hash: {entry.get('blake3')}")
    
    elif entry_type == "config":
        click.echo(f"Setting: {entry.get('path', 'None')}")
        click.echo(f"Value: {entry.get('blake3', 'None')}")
    
    elif entry_type == "comment":
        click.echo(f"Comment: {entry.get('blake3', 'None')}")
    
    elif entry_type == "verify":
        click.echo(f"Verification: {entry.get('blake3', 'Completed')}")
