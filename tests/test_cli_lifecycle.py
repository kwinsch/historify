"""
Tests for the lifecycle commands (start, closing) implementation.
"""
import pytest
import os
import sqlite3
import shutil
import csv
from pathlib import Path
from click.testing import CliRunner
from unittest.mock import patch, MagicMock

from historify.cli import init, config, start_transaction, closing
from historify.changelog import Changelog, ChangelogError
from historify.config import RepositoryConfig
from historify.cli_init import init_repository

class TestLifecycleImplementation:
    """Test the lifecycle command implementations."""
    
    def setup_method(self):
        """Set up test environment."""
        self.runner = CliRunner()
        self.test_repo_path = Path("test_repo_lifecycle").absolute()
        
        # Initialize a test repository
        if not self.test_repo_path.exists():
            init_repository(str(self.test_repo_path), "test-repo")
        
        # Create test minisign key files
        self.key_dir = Path("test_keys").absolute()
        self.key_dir.mkdir(parents=True, exist_ok=True)
        
        self.minisign_key = self.key_dir / "historify.key"
        self.minisign_pub = self.key_dir / "historify.pub"
        
        # Create mock minisign key files
        with open(self.minisign_key, "w") as f:
            f.write("untrusted comment: minisign unencrypted secret key\n")
            f.write("TESTKEY123456789\n")
        
        with open(self.minisign_pub, "w") as f:
            f.write("untrusted comment: minisign public key\n")
            f.write("TESTPUB987654321\n")
    
    def teardown_method(self):
        """Clean up test environment."""
        if self.test_repo_path.exists():
            shutil.rmtree(self.test_repo_path)
        if self.key_dir.exists():
            shutil.rmtree(self.key_dir)
    
    @patch('historify.changelog.minisign_sign')
    def test_changelog_init(self, mock_sign):
        """Test Changelog class initialization."""
        # Configure repository with minisign keys
        config = RepositoryConfig(str(self.test_repo_path))
        config.set("minisign.key", str(self.minisign_key))
        config.set("minisign.pub", str(self.minisign_pub))
        
        # Initialize changelog
        changelog = Changelog(str(self.test_repo_path))
        
        assert changelog.repo_path == self.test_repo_path
        assert changelog.changes_dir == self.test_repo_path / "changes"
        assert changelog.minisign_key == str(self.minisign_key)
        assert changelog.minisign_pub == str(self.minisign_pub)
    
    @patch('historify.changelog.minisign_sign')
    def test_start_initial(self, mock_sign):
        """Test initial start command on new repository."""
        # Set up mock
        mock_sign.return_value = True
        
        # Configure repository with minisign keys
        config = RepositoryConfig(str(self.test_repo_path))
        config.set("minisign.key", str(self.minisign_key))
        config.set("minisign.pub", str(self.minisign_pub))
        
        # Initialize changelog
        changelog = Changelog(str(self.test_repo_path))
        
        # Execute start command
        success, message = changelog.start_closing()
        
        assert success is True
        assert "Signed seed file and created first changelog" in message
        
        # Verify a new changelog was created
        changelog_files = list(self.test_repo_path.glob("changes/changelog-*.csv"))
        assert len(changelog_files) == 1
        
        # Verify minisign was called with the seed file (don't check unencrypted parameter)
        assert mock_sign.call_count == 1
        args, kwargs = mock_sign.call_args
        assert str(self.test_repo_path / "db" / "seed.bin") in args
        assert str(self.minisign_key) in args
        assert kwargs.get('password') is None
        
        # Check changelog content - verify it contains closing record
        with open(changelog_files[0], "r") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert len(rows) == 1
            assert rows[0]["transaction_type"] == "closing"
            assert rows[0]["path"] == "db/seed.bin"
            assert rows[0]["blake3"] != ""  # Check that the hash is present
    
    @patch('historify.changelog.minisign_sign')
    @patch('historify.changelog.Changelog.create_new_changelog')
    @patch('historify.changelog.Changelog.write_closing_transaction')
    @patch('historify.changelog.Changelog._update_integrity_record')
    @patch('historify.changelog.Changelog._record_transaction_in_db')
    def test_closing_and_new_start(self, mock_record, mock_update, mock_write, mock_create, mock_sign):
        """Test closing current changelog and starting a new one using extensive mocking."""
        # Set up all mocks
        mock_sign.return_value = True
        mock_create.return_value = Path("mock_changelog.csv")
        mock_write.return_value = True
        mock_update.return_value = None
        mock_record.return_value = None
        
        # Create a mock for get_current_changelog that returns different values on consecutive calls
        with patch('historify.changelog.Changelog.get_current_changelog') as mock_get_current:
            # First call returns None (no open changelog)
            # Second call returns a mock path (after first start)
            mock_get_current.side_effect = [None, Path("mock_changelog1.csv")]
            
            # Configure repository with minisign keys
            config = RepositoryConfig(str(self.test_repo_path))
            config.set("minisign.key", str(self.minisign_key))
            config.set("minisign.pub", str(self.minisign_pub))
            
            # First start
            changelog = Changelog(str(self.test_repo_path))
            first_result, first_message = changelog.start_closing()
            
            # Verify first start worked
            assert first_result is True
            assert "created first changelog" in first_message
            
        # Now test second start with different mock setup
        with patch('historify.changelog.Changelog.get_current_changelog') as mock_get_current:
            mock_get_current.return_value = Path("mock_changelog1.csv")
            
            # Reset sign mock to track new calls
            mock_sign.reset_mock()
            
            # Second start
            changelog2 = Changelog(str(self.test_repo_path))
            success, message = changelog2.start_closing()
            
            # Verify second start
            assert success is True
            assert "Signed" in message
            
            # Verify methods were called
            mock_sign.assert_called_once()
            mock_create.assert_called()
            mock_write.assert_called()
    
    @patch('historify.cli_lifecycle.Changelog')
    def test_cli_start_command(self, mock_changelog_class):
        """Test CLI start command."""
        # Set up mock
        mock_changelog = MagicMock()
        mock_changelog.start_closing.return_value = (True, "Success message")
        mock_changelog_class.return_value = mock_changelog
        
        with self.runner.isolated_filesystem():
            # Create a simple repository structure to pass basic validation
            os.makedirs("repo_dir/db")
            os.makedirs("repo_dir/changes")
            with open("repo_dir/db/config", "w") as f:
                f.write("[repository]\nname = test-repo\n")
            with open("repo_dir/db/cache.db", "w") as f:
                f.write("mock db file")
            
            # Run start command
            result = self.runner.invoke(start_transaction, ["repo_dir"])
            
            assert result.exit_code == 0
            assert "Starting new transaction period" in result.output
            assert "Success" in result.output
            
            # Verify the changelog method was called
            mock_changelog_class.assert_called_once()
            mock_changelog.start_closing.assert_called_once()
    
    @patch('historify.cli_lifecycle.Changelog')
    def test_cli_start_with_password(self, mock_changelog_class):
        """Test CLI start command with explicit password."""
        # Set up mock
        mock_changelog = MagicMock()
        mock_changelog.start_closing.return_value = (True, "Success message")
        mock_changelog_class.return_value = mock_changelog
        
        with self.runner.isolated_filesystem():
            # Create a simple repository structure to pass basic validation
            os.makedirs("repo_dir/db")
            os.makedirs("repo_dir/changes")
            with open("repo_dir/db/config", "w") as f:
                f.write("[repository]\nname = test-repo\n")
            with open("repo_dir/db/cache.db", "w") as f:
                f.write("mock db file")
            
            # Run start command with password
            result = self.runner.invoke(start_transaction, ["repo_dir", "--password", "test123"])
            
            assert result.exit_code == 0
            assert "Success" in result.output
            
            # Verify the changelog method was called with the password
            mock_changelog_class.assert_called_once()
            mock_changelog.start_closing.assert_called_once_with("test123")
    
    @patch('historify.cli_lifecycle.Changelog')
    def test_cli_closing_command(self, mock_changelog_class):
        """Test CLI closing command."""
        # Set up mock
        mock_changelog = MagicMock()
        mock_changelog.start_closing.return_value = (True, "Success message")
        mock_changelog_class.return_value = mock_changelog
        
        with self.runner.isolated_filesystem():
            # Create a simple repository structure to pass basic validation
            os.makedirs("repo_dir/db")
            os.makedirs("repo_dir/changes")
            with open("repo_dir/db/config", "w") as f:
                f.write("[repository]\nname = test-repo\n")
            with open("repo_dir/db/cache.db", "w") as f:
                f.write("mock db file")
            
            # Run closing command
            result = self.runner.invoke(closing, ["repo_dir"])
            
            assert result.exit_code == 0
            assert "Success" in result.output
            
            # Verify the changelog method was called
            mock_changelog_class.assert_called_once()
            mock_changelog.start_closing.assert_called_once()
