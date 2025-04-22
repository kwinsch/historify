import pytest
from click.testing import CliRunner
from historify.cli import config, check_config

def test_config_command():
    """Test the config command."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        # Create dummy repo
        result = runner.invoke(config, ["hash.algorithms", "blake3,sha256", "."])
        assert result.exit_code == 0
        assert "Setting hash.algorithms=blake3,sha256 in ." in result.output

def test_check_config_command():
    """Test the check-config command."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(check_config, ["."])
        assert result.exit_code == 0
        assert "Checking configuration in" in result.output
