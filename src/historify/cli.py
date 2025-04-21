import click


@click.group()
@click.option(
    "--repo",
    "-r",
    help="Specify the repository name (required for multiple repositories)",
)
def main(repo):
    """historify: Revision-safe logging of file changes."""
    pass


@main.command()
@click.argument("directory", default=".")
def init(directory):
    """Initialize a new historify repository."""
    click.echo(f"Initializing repository in {directory}")


@main.command()
@click.argument("key")
@click.argument("value")
def config(key, value):
    """Set configuration values."""
    click.echo(f"Setting {key} to {value}")


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
