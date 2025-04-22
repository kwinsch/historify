import pytest
from click.testing import CliRunner
from historify.cli import snapshot

def test_snapshot_command():
    """Test the snapshot command."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(snapshot, ["/tmp/backup.tar.gz", "."])
        assert result.exit_code == 0
        assert "Creating snapshot from" in result.output
        assert "to /tmp/backup.tar.gz" in result.output

def test_snapshot_relative_path():
    """Test snapshot with relative output path."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(snapshot, ["./backup.tar.gz", "."])
        assert result.exit_code == 0
        assert "Creating snapshot from" in result.output
        assert "to ./backup.tar.gz" in result.output
