"""
Tests for the init command implementation.
"""
import pytest
import os
import csv
import shutil
from pathlib import Path
from click.testing import CliRunner
from unittest.mock import patch, MagicMock

from historify.cli import init
from historify.cli_init import init_repository, handle_init_command
from historify.repository import Repository, RepositoryError

class TestInitImplementation:
    """Test the initialization command implementation."""
    
    def setup_method(self):
        """Set up test environment."""
        self.runner = CliRunner()
        self.test_repo_path = Path("test_repo")
        
    def teardown_method(self):
        """Clean up test environment."""
        if self.test_repo_path.exists():
            shutil.rmtree(self.test_repo_path)
    
    def test_repository_init(self):
        """Test Repository class initialization."""
        repo = Repository(str(self.test_repo_path), "test-repo")
        assert repo.name == "test-repo"
        assert repo.path == self.test_repo_path.resolve()
        assert repo.db_dir == self.test_repo_path.resolve() / "db"
        assert repo.changes_dir == self.test_repo_path.resolve() / "changes"
    
    def test_init_repository_function(self):
        """Test init_repository function."""
        # Run the initialization
        result = init_repository(str(self.test_repo_path), "test-repo")
        assert result is True
        
        # Verify the repository structure
        assert self.test_repo_path.exists()
        assert (self.test_repo_path / "db").exists()
        assert (self.test_repo_path / "db" / "config").exists()
        assert (self.test_repo_path / "db" / "config.csv").exists()
        assert (self.test_repo_path / "db" / "seed.bin").exists()
        assert (self.test_repo_path / "db" / "integrity.csv").exists()
        assert (self.test_repo_path / "changes").exists()
        
        # Verify seed file size
        seed_size = (self.test_repo_path / "db" / "seed.bin").stat().st_size
        assert seed_size == 1024 * 1024  # 1MB
        
        # Verify config.csv structure
        with open(self.test_repo_path / "db" / "config.csv", "r", newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            # Check that we have at least the required config entries
            config_keys = [row["key"] for row in rows]
            assert "repository.name" in config_keys
            assert "hash.algorithms" in config_keys
            assert "changes.directory" in config_keys
        
        # Verify integrity.csv structure
        with open(self.test_repo_path / "db" / "integrity.csv", "r", newline="") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            assert "changelog_file" in fieldnames
            assert "blake3" in fieldnames
            assert "signature_file" in fieldnames
            assert "verified" in fieldnames
            assert "verified_timestamp" in fieldnames
        
    def test_init_repository_function_default_name(self):
        """Test init_repository function with default name."""
        result = init_repository(str(self.test_repo_path))
        assert result is True
        
        # Verify repository name in config.csv
        with open(self.test_repo_path / "db" / "config.csv", "r", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row["key"] == "repository.name":
                    assert row["value"] == "test_repo"  # Default to directory name
                    break
    
    def test_handle_init_command(self):
        """Test handle_init_command function."""
        # Create a temporary directory for the test
        with self.runner.isolated_filesystem():
            handle_init_command("./repo_dir", "test-repo")
            
            # Verify the repository was created
            assert Path("repo_dir").exists()
            assert Path("repo_dir/db").exists()
            assert Path("repo_dir/db/config").exists()
            assert Path("repo_dir/changes").exists()
    
    def test_cli_init_command(self):
        """Test CLI init command."""
        with self.runner.isolated_filesystem():
            result = self.runner.invoke(init, ["./repo_dir", "--name", "test-repo"])
            
            assert result.exit_code == 0
            assert "Initializing repository 'test-repo' at" in result.output
            assert "Repository 'test-repo' successfully initialized" in result.output
            assert "Next steps:" in result.output
            
            # Verify the repository was created
            assert Path("repo_dir").exists()
            assert Path("repo_dir/db").exists()
            assert Path("repo_dir/changes").exists()
    
    def test_init_existing_directory(self):
        """Test initialization in an existing directory."""
        # Create the directory first
        self.test_repo_path.mkdir(parents=True, exist_ok=True)
        
        result = init_repository(str(self.test_repo_path), "test-repo")
        assert result is True
        
        # Verify the repository structure
        assert (self.test_repo_path / "db").exists()
        assert (self.test_repo_path / "changes").exists()
    
    def test_cli_init_quiet(self):
        """Test CLI init command with minimal output."""
        with self.runner.isolated_filesystem():
            # Redirect stdout to minimize output for this test
            result = self.runner.invoke(init, ["./quiet_repo"], catch_exceptions=False)
            
            assert result.exit_code == 0
            assert Path("quiet_repo").exists()
            assert Path("quiet_repo/db").exists()
            assert Path("quiet_repo/changes").exists()
