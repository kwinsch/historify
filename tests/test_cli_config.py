"""
Tests for the config command implementation.
"""
import pytest
import os
import csv
import shutil
import configparser
from pathlib import Path
from click.testing import CliRunner
from unittest.mock import patch, MagicMock

from historify.cli import init, config, check_config
from historify.config import RepositoryConfig, ConfigError
from historify.cli_init import init_repository

class TestConfigImplementation:
    """Test the configuration command implementation."""
    
    def setup_method(self):
        """Set up test environment."""
        self.runner = CliRunner()
        self.test_repo_path = Path("test_repo_config")
        
        # Initialize a test repository
        if not self.test_repo_path.exists():
            init_repository(str(self.test_repo_path), "test-repo")
    
    def teardown_method(self):
        """Clean up test environment."""
        if self.test_repo_path.exists():
            shutil.rmtree(self.test_repo_path)
    
    def test_repository_config_init(self):
        """Test RepositoryConfig class initialization."""
        config = RepositoryConfig(str(self.test_repo_path))
        assert config.repo_path == self.test_repo_path.resolve()
        assert config.db_dir == self.test_repo_path.resolve() / "db"
        assert config.config_file == self.test_repo_path.resolve() / "db" / "config"
        assert config.config_csv == self.test_repo_path.resolve() / "db" / "config.csv"
    
    def test_repository_config_init_invalid(self):
        """Test RepositoryConfig with invalid repository."""
        invalid_path = Path("invalid_repo")
        if invalid_path.exists():
            shutil.rmtree(invalid_path)
        invalid_path.mkdir(parents=True)
        
        with pytest.raises(ConfigError, match="Not a valid historify repository"):
            RepositoryConfig(str(invalid_path))
        
        shutil.rmtree(invalid_path)
    
    def test_set_get_config(self):
        """Test setting and getting configuration values."""
        # Set a value
        config = RepositoryConfig(str(self.test_repo_path))
        result = config.set("test.value", "testing123")
        assert result is True
        
        # Get the value
        value = config.get("test.value")
        assert value == "testing123"
        
        # Check it was saved in INI file
        parser = configparser.ConfigParser()
        parser.read(self.test_repo_path / "db" / "config")
        assert "test" in parser
        assert "value" in parser["test"]
        assert parser["test"]["value"] == "testing123"
        
        # Check it was saved in CSV file
        with open(self.test_repo_path / "db" / "config.csv", "r", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row["key"] == "test.value":
                    assert row["value"] == "testing123"
                    break
            else:
                pytest.fail("Config value not found in CSV file")
    
    def test_set_config_invalid_key(self):
        """Test setting config with invalid key format."""
        config = RepositoryConfig(str(self.test_repo_path))
        with pytest.raises(ConfigError, match="Invalid key format"):
            config.set("invalid_key", "value")
    
    def test_check_config(self):
        """Test checking configuration."""
        config = RepositoryConfig(str(self.test_repo_path))
        
        # Initially, config should be valid (from repository initialization)
        issues = config.check()
        assert not issues
        
        # Remove a required config from both storage locations
        
        # Remove from INI file
        config_file = self.test_repo_path / "db" / "config"
        parser = configparser.ConfigParser()
        parser.read(config_file)
        if "hash" in parser and "algorithms" in parser["hash"]:
            del parser["hash"]["algorithms"]
            with open(config_file, "w") as f:
                parser.write(f)
        
        # Remove from CSV file
        config_csv = self.test_repo_path / "db" / "config.csv"
        rows = []
        with open(config_csv, "r", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row["key"] != "hash.algorithms":
                    rows.append(row)
        
        with open(config_csv, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["key", "value"])
            writer.writeheader()
            writer.writerows(rows)
        
        # Config should now have issues
        config = RepositoryConfig(str(self.test_repo_path))  # Re-read config
        issues = config.check()
        assert issues
        assert any(key == "hash.algorithms" for key, _ in issues)
    
    def test_list_config(self):
        """Test listing all configuration values."""
        config = RepositoryConfig(str(self.test_repo_path))
        
        # Set some test values
        config.set("test.one", "value1")
        config.set("test.two", "value2")
        
        # List all values
        all_config = config.list_all()
        
        # Check our test values are included
        assert "test.one" in all_config
        assert all_config["test.one"] == "value1"
        assert "test.two" in all_config
        assert all_config["test.two"] == "value2"
        
        # Check repository name is included
        assert "repository.name" in all_config
        assert all_config["repository.name"] == "test-repo"
    
    def test_cli_config_command(self):
        """Test CLI config command."""
        with self.runner.isolated_filesystem():
            # First initialize a repository
            self.runner.invoke(init, ["./repo_dir", "--name", "test-repo"])
            
            # Set a configuration value
            result = self.runner.invoke(config, ["test.cli", "cli-value", "./repo_dir"])
            
            assert result.exit_code == 0
            assert "Setting test.cli = cli-value in" in result.output
            assert "Configuration updated successfully" in result.output
            
            # Verify the value was set
            config_obj = RepositoryConfig("./repo_dir")
            assert config_obj.get("test.cli") == "cli-value"
    
    def test_cli_check_config_command(self):
        """Test CLI check-config command."""
        with self.runner.isolated_filesystem():
            # First initialize a repository
            self.runner.invoke(init, ["./repo_dir", "--name", "test-repo"])
            
            # Check configuration (should pass)
            result = self.runner.invoke(check_config, ["./repo_dir"])
            
            assert result.exit_code == 0
            assert "Checking configuration in" in result.output
            assert "Configuration check passed with no issues" in result.output
            
            # Modify both INI file and CSV files to remove a required config
            
            # Remove from INI file
            config_file = Path("./repo_dir/db/config")
            parser = configparser.ConfigParser()
            parser.read(config_file)
            if "repository" in parser and "name" in parser["repository"]:
                del parser["repository"]["name"]
                with open(config_file, "w") as f:
                    parser.write(f)
            
            # Remove from CSV file
            config_csv = Path("./repo_dir/db/config.csv")
            rows = []
            with open(config_csv, "r", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row["key"] != "repository.name":
                        rows.append(row)
            
            with open(config_csv, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=["key", "value"])
                writer.writeheader()
                writer.writerows(rows)
            
            # Check configuration again (should find issues)
            result = self.runner.invoke(check_config, ["./repo_dir"])
            
            assert result.exit_code == 0
            assert "Configuration issues found:" in result.output
            assert "repository.name" in result.output
