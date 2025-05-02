#!/usr/bin/env python
"""
Command-line interface for historify - a tool for revision-safe logging of file changes.
"""
import click
import os
import logging
from pathlib import Path
from historify.cli_init import handle_init_command
from historify.cli_config import handle_config_command, handle_check_config_command
from historify.cli_comment import handle_comment_command
from historify.cli_log import handle_log_command
from historify.cli_lifecycle import handle_start_command, handle_closing_command
from historify.cli_scan import cli_scan_command
from historify.cli_category import handle_add_category_command
from historify.cli_duplicates import handle_duplicates_command
from historify.cli_verify import cli_verify_command
from historify.cli_snapshot import handle_snapshot_command
from historify.cli_status import cli_status_command


# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
def cli(verbose):
    """
    historify: track file history with cryptographic integrity verification.
    
    historify is a command-line tool for tracking file changes in a repository,
    logging changes with cryptographic hashes (BLAKE3 and SHA256), and securing
    logs with minisign signatures.
    """
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        click.echo("Verbose mode enabled")
    logger.debug("historify CLI starting")

@cli.command()
@click.argument("repo_path", type=click.Path())
@click.option("--name", help="Repository name (defaults to directory name)")
def init(repo_path, name):
    """
    Initialize a new repository at REPO_PATH.
    
    Creates a configuration file (db/config), integrity CSV (db/integrity.csv),
    and random seed file (db/seed.bin) at the specified repository path.
    """
    handle_init_command(repo_path, name)
    
@cli.command()
@click.argument("key", required=True)
@click.argument("value", required=True)
@click.argument("repo_path", type=click.Path(exists=True), default=".")
def config(key, value, repo_path):
    """
    Set a configuration KEY to VALUE in the repository.
    
    Keys use section.option format (e.g., category.default.path, hash.algorithms, minisign.key).
    """
    handle_config_command(repo_path, key, value)

@cli.command()
@click.argument("repo_path", type=click.Path(exists=True), default=".")
def check_config(repo_path):
    """
    Verify the configuration of the repository.
    """
    handle_check_config_command(repo_path)

@cli.command()
@click.argument("category_name", required=True)
@click.argument("data_path", type=click.Path(), required=True)
@click.argument("repo_path", type=click.Path(exists=True), default=".")
def add_category(category_name, data_path, repo_path):
    """
    Add a data category with specified path for organizing content.
    
    The DATA_PATH can be a relative path within the repository or an absolute path
    to an external location.
    """
    handle_add_category_command(repo_path, category_name, data_path)

@cli.command("start")
@click.argument("repo_path", type=click.Path(exists=True), default=".")
def start_transaction(repo_path):
    """
    Sign the current state and prepare for new changes.
    
    Signs db/seed.bin in case of a new repo or the latest changelog file.
    On successful signing, the first/next changelog file is created.
    The command issues an implicit prior 'verify'.
    """
    handle_start_command(repo_path)

@cli.command()
@click.argument("repo_path", type=click.Path(exists=True), default=".")
def closing(repo_path):
    """
    Close the current changelog and prepare for the next period.
    
    Functionally equivalent to the 'start' command.
    """
    handle_closing_command(repo_path)

@cli.command()
@click.argument("repo_path", type=click.Path(exists=True), default=".")
@click.option("--category", help="Filter scan to specific category")
def scan(repo_path, category):
    """
    Scan the repository's data categories for file changes.
    
    Logs changes (new, move, deleted) with cryptographic hashes
    to the latest open changelog file. Use the 'duplicates' command
    to identify files with identical content.
    """
    cli_scan_command(repo_path, category)

@cli.command()
@click.argument("repo_path", type=click.Path(exists=True), default=".")
@click.option("--full-chain", is_flag=True, help="Verify the entire change log chain")
def verify(repo_path, full_chain):
    """
    Verify the integrity of change logs.
    
    By default, verifies from the latest signed changelog forward.
    With --full-chain, verifies the entire chain of logs.
    """
    exit_code = cli_verify_command(repo_path, full_chain)
    if exit_code != 0:
        raise click.Abort()

@cli.command()
@click.argument("repo_path", type=click.Path(exists=True), default=".")
@click.option("--category", help="Filter status to specific category")
def status(repo_path, category):
    """
    Display the current repository status.
    
    Shows counts of tracked files, recent changes, and signature status.
    """
    exit_code = cli_status_command(repo_path, category)
    if exit_code != 0:
        raise click.Abort()

@cli.command()
@click.argument("repo_path", type=click.Path(exists=True), default=".")
@click.option("--file", help="Specify a particular change log file")
@click.option("--category", help="Filter logs by category")
def log(repo_path, file, category):
    """
    Display change history from logs.
    
    By default, shows the current log. Use --file to specify a different
    changelog and --category to filter by category.
    """
    handle_log_command(repo_path, file, category)

@cli.command()
@click.argument("message", required=True)
@click.argument("repo_path", type=click.Path(exists=True), default=".")
def comment(message, repo_path):
    """
    Add an administrative comment to the change log.
    
    Useful for documenting important events or changes.
    """
    handle_comment_command(repo_path, message)

@cli.command()
@click.argument("repo_path", type=click.Path(exists=True), default=".")
@click.option("--category", help="Filter duplicates to specific category")
def duplicates(repo_path, category):
    """
    Find and display duplicate files in the repository.
    
    Identifies files with identical content (same hash) and displays them
    grouped by hash value with information about size and wasted space.
    """
    handle_duplicates_command(repo_path, category)

@cli.command()
@click.argument("output_dir", type=click.Path(), required=True)
@click.argument("repo_path", type=click.Path(exists=True), default=".")
@click.option("--name", help="Base name for output files (defaults to repository name)")
@click.option("--full", is_flag=True, help="Include external category data in separate archives")
@click.option("--media", is_flag=True, default=False, help="Create ISO image for media (default: bd-r)")
def snapshot(output_dir, repo_path, name, full, media):
    """
    Create a compressed archive of the current repository state.
    
    Saves output to OUTPUT_DIR with automatically generated filenames including date.
    The base name can be customized with --name, otherwise the repository name is used.
    
    Includes all data files, change logs, seed, signatures, and configuration.
    With --full, creates separate archives for external categories.
    With --media, creates ISO images suitable for optical media (BD-R).
    """
    handle_snapshot_command(output_dir, repo_path, name, full, media)

def main():
    """Entry point for the CLI."""
    cli()

if __name__ == "__main__":
    main()
