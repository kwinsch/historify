import pytest
from click.testing import CliRunner
from historify.cli import add_category

def test_add_category_command():
    """Test the add-category command."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(add_category, ["documents", "docs", "."])
        assert result.exit_code == 0
        assert "Adding category 'documents' with path 'docs' to" in result.output

def test_add_category_absolute_path():
    """Test add-category with absolute path."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(add_category, ["external", "/tmp/external", "."])
        assert result.exit_code == 0
        assert "Adding category 'external' with path '/tmp/external' to" in result.output
