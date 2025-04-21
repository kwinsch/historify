import click
from historify.config import HistorifyConfig, ConfigError
from historify.tools import get_blake3_hash, minisign_verify
from historify.log import LogManager
from historify.db import DatabaseManager
from historify.monitor import FileMonitor
import os
import secrets
from pathlib import Path
from datetime import datetime, UTC
import csv
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

@click.group()
@click.option("--repo", "-r", help="Specify the repository name (required for multiple repositories)")
def main(repo):
    """historify: Revision-safe logging of file changes."""
    pass

@main.command()
@click.argument("directory", default=".")
@click.option("--name", help="Repository name (defaults to directory name)")
def init(directory, name):
    """Initialize a new historify repository."""
    try:
        repo_path = Path(directory).resolve()
        repo_name = name or repo_path.name
        
        # Create .historify directory
        historify_dir = repo_path / ".historify"
        historify_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize configuration
        config = HistorifyConfig(repo_name=repo_name, repo_path=str(repo_path))
        
        # Set default configuration
        config.set("hash_algorithm", "blake3", section=f"repo.{repo_name}", scope="local")
        config.set("random_source", "/dev/urandom", section=f"repo.{repo_name}", scope="local")
        config.set("tools.b3sum", "/usr/bin/b3sum", section=f"repo.{repo_name}", scope="local")
        config.set("tools.minisign", "/usr/bin/minisign", section=f"repo.{repo_name}", scope="local")
        
        # Initialize database
        db_manager = DatabaseManager(str(repo_path))
        db_manager.initialize()
        
        # Generate seed
        seed_file = historify_dir / "seed.bin"
        with seed_file.open("wb") as f:
            f.write(secrets.token_bytes(1024 * 1024))  # 1MB random data
        
        # Add seed to database
        db_manager.add_file(str(seed_file))
        
        # Initialize log manager
        log_manager = LogManager(str(repo_path))
        
        # Log config transaction
        log_manager.write_transaction(
            transaction_type="config",
            metadata={
                "hash_algorithm": "blake3",
                "random_source": "/dev/urandom",
                "tools.b3sum": "/usr/bin/b3sum",
                "tools.minisign": "/usr/bin/minisign"
            }
        )
        
        # Log seed transaction
        log_manager.write_transaction(
            transaction_type="seed",
            file_path=str(seed_file.relative_to(repo_path))
        )
        
        click.echo(f"Initialized repository '{repo_name}' in {repo_path}")
    except (ConfigError, FileNotFoundError) as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()

@main.command()
@click.argument("log-file")
def sign(log_file):
    """Instruct user to sign a file with minisign."""
    try:
        log_path = Path(log_file).resolve()
        if not log_path.is_file():
            raise ConfigError(f"File does not exist: {log_path}")
        
        click.echo(f"Sign the file manually with:")
        click.echo(f"  minisign -Sm {log_path} -s <private_key>")
        click.echo(f"Signature will be saved as {log_path}.minisig")
        logging.debug(f"Instructed manual signing for {log_path}")
    except ConfigError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()

@main.command("add-category")
@click.argument("data-dir")
@click.argument("category-name")
def add_category(data_dir, category_name):
    """Add a data directory with a category name."""
    click.echo(f"Adding category {category_name} for {data_dir}")

@main.command()
def status():
    """Display repository status."""
    click.echo("Repository status")

@main.command()
@click.argument("repo-path", default=".")
def log(repo_path):
    """Show the current month's transaction log."""
    try:
        log_manager = LogManager(repo_path)
        transactions = log_manager.read_log()
        for t in transactions:
            click.echo(f"{t['timestamp']} {t['transaction_type']} {t['path']} {t['hash']} {t['metadata']}")
    except ConfigError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()

@main.command()
@click.argument("message")
@click.argument("repo-path", default=".")
def comment(message, repo_path):
    """Add an administrative comment."""
    try:
        log_manager = LogManager(repo_path)
        log_manager.write_transaction(transaction_type="comment", metadata={"message": message})
        click.echo(f"Added comment: {message}")
    except ConfigError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()

@main.command()
@click.argument("repo-path", default=".")
def verify(repo_path):
    """Verify the integrity of the hash chain and SQLite database."""
    try:
        db_manager = DatabaseManager(repo_path)
        log_manager = LogManager(repo_path)
        
        # Verify database integrity
        issues = db_manager.verify_integrity()
        if issues:
            click.echo("Database integrity issues found:")
            for file_hash, path in issues:
                click.echo(f"Hash: {file_hash}, Path: {path} (missing or mismatched)")
        else:
            click.echo("Database integrity verified successfully.")
        
        # Verify hash chain
        log_file = log_manager.get_current_log_file()
        if log_manager.validate_hash_chain(str(log_file)):
            click.echo("Hash chain verified successfully.")
        else:
            click.echo("Hash chain verification failed.")
        
        log_manager.write_transaction(transaction_type="verify")
    except ConfigError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()
    finally:
        db_manager.close()
        log_manager.write_transaction(transaction_type="closing_db")

@main.command()
@click.argument("repo-path", default=".")
def scan(repo_path):
    """Scan data directories for file changes."""
    try:
        repo_path = Path(repo_path).resolve()
        config = HistorifyConfig(repo_name=None, repo_path=str(repo_path))
        db_manager = DatabaseManager(str(repo_path))
        log_manager = LogManager(str(repo_path))
        monitor = FileMonitor(str(repo_path), db_manager)
        
        # Get data directories from configuration
        data_dirs = []
        for section in config.config.sections():
            if section.startswith("repo."):
                repo_name = section.split(".", 1)[1]
                data_dir = config.get("data_dir", section)
                if data_dir:
                    data_dirs.append(data_dir)
                # Add category directories
                for key in config.config[section]:
                    if key.startswith("categories."):
                        category_dir = config.config[section][key]
                        if category_dir:
                            data_dirs.append(category_dir)
        
        if not data_dirs:
            click.echo("No data directories configured. Set repo.<name>.data_dir or repo.<name>.categories.<catname>.")
            return
        
        # Scan for changes
        transactions = monitor.scan(data_dirs)
        for t in transactions:
            log_manager.write_transaction(
                transaction_type=t["type"],
                file_path=t["path"],
                metadata=t["metadata"]
            )
            click.echo(f"Logged {t['type']} transaction for {t['path']}")
        
    except ConfigError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()

@main.command()
@click.option("--scope", type=click.Choice(["global", "local"]), default="local", help="Configuration scope")
@click.argument("key")
@click.argument("value")
@click.argument("repo-path", default=".")
def config(scope, key, value, repo_path):
    """Set a configuration option."""
    try:
        repo_path = Path(repo_path).resolve()
        config = HistorifyConfig(repo_name=None, repo_path=str(repo_path))
        
        # Parse key to determine section
        parts = key.split(".", 2)
        if len(parts) < 2:
            raise ConfigError("Key must be in format section.key or repo.<name>.key")
        
        section, option = parts[0], parts[-1]
        if section != "repo":
            section = f"repo.{parts[1]}" if len(parts) > 2 else section
        
        config.set(option, value, section=section, scope=scope)
        click.echo(f"Set {key} = {value} in {scope} configuration")
        logging.debug(f"Set config: {section}.{option} = {value} in {scope} scope")
    except ConfigError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()

if __name__ == "__main__":
    main()