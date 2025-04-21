import click
from historify.config import HistorifyConfig, ConfigError
from historify.tools import get_blake3_hash, minisign_verify
import os
import secrets
from pathlib import Path
from datetime import datetime, UTC
import csv

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
        
        # Generate seed
        seed_file = historify_dir / "seed.bin"
        with seed_file.open("wb") as f:
            f.write(secrets.token_bytes(1024 * 1024))  # 1MB random data
        
        # Compute seed hash
        seed_hash = get_blake3_hash(str(seed_file))
        
        # Create initial transaction log
        log_file = repo_path / f"translog-{datetime.now(UTC).strftime('%Y-%m')}.csv"
        with log_file.open("w", newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "transaction_type", "hash", "path", "metadata"])
            writer.writerow([
                datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC"),
                "config",
                "",
                "",
                f"hash_algorithm=blake3,random_source=/dev/urandom,tools.b3sum=/usr/bin/b3sum,tools.minisign=/usr/bin/minisign"
            ])
            writer.writerow([
                datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC"),
                "seed",
                seed_hash,
                str(seed_file.relative_to(repo_path)),
                ""
            ])
        
        click.echo(f"Initialized repository '{repo_name}' in {repo_path}")
        click.echo(f"Seed file created at {seed_file}. Sign manually with:")
        click.echo(f"  minisign -Sm {seed_file} -s <private_key>")
        click.echo(f"Transaction log created at {log_file}. Sign manually with:")
        click.echo(f"  minisign -Sm {log_file} -s <private_key>")
        click.echo("Generate a key pair if needed:")
        click.echo("  minisign -G -p <public_key> -s <private_key>")
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
def log():
    """Show the current month's transaction log."""
    click.echo("Current month's log")

@main.command()
@click.argument("message")
def comment(message):
    """Add an administrative comment."""
    click.echo(f"Adding comment: {message}")

@main.command()
def verify():
    """Verify the integrity of the hash chain and SQLite database."""
    click.echo("Verifying integrity")

if __name__ == "__main__":
    main()
