import click
from historify.config import HistorifyConfig, ConfigError
from historify.tools import get_blake3_hash, minisign_sign, minisign_verify
import os
import secrets
from pathlib import Path
from datetime import datetime
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
        
        # Skip minisign key generation and signing until Step 7
        # key_file = historify_dir / "test.key"
        # pubkey_file = historify_dir / "test.pub"
        # os.system(f"minisign -G -p {pubkey_file} -s {key_file}")
        # sig_path = minisign_sign(str(seed_file), str(key_file))
        
        # Create initial transaction log
        log_file = repo_path / f"translog-{datetime.utcnow().strftime('%Y-%m')}.csv"
        with log_file.open("w", newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "transaction_type", "hash", "path", "metadata"])
            writer.writerow([
                datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
                "config",
                "",
                "",
                f"hash_algorithm=blake3,random_source=/dev/urandom,tools.b3sum=/usr/bin/b3sum,tools.minisign=/usr/bin/minisign"
            ])
            writer.writerow([
                datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
                "seed",
                seed_hash,
                str(seed_file.relative_to(repo_path)),
                ""
            ])
        
        # Skip log signing
        # minisign_sign(str(log_file), str(key_file))
        
        click.echo(f"Initialized repository '{repo_name}' in {repo_path}")
    except (ConfigError, FileNotFoundError) as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()

@main.command()
@click.argument("key")
@click.argument("value")
@click.option("--scope", type=click.Choice(['global', 'user', 'local']), default='local',
              help="Configuration scope (global, user, local)")
def config(key, value, scope):
    """Set configuration values."""
    try:
        repo_name = HistorifyConfig().get_default_repo()
        config = HistorifyConfig(repo_name=repo_name, repo_path='.' if scope == 'local' else None)
        section = f"repo.{repo_name}" if repo_name and scope == 'local' else 'DEFAULT'
        config.set(key, value, section=section, scope=scope)
        click.echo(f"Set {key} = {value} in {scope} scope")
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

@main.command()
def sign():
    """Sign a monthly CSV log with a minisign-compatible signature."""
    click.echo("Signing log")

if __name__ == "__main__":
    main()

