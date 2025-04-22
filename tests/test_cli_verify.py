"""
Tests for the verify command implementation.
"""
import pytest
import os
import csv
import shutil
from pathlib import Path
from datetime import datetime, UTC
from click.testing import CliRunner
from unittest.mock import patch, MagicMock

from historify.cli import verify
from historify.cli_verify import (
    verify_repository_config, 
    verify_signature, 
    verify_changelog_hash_chain,
    rebuild_integrity_csv,
    verify_full_chain,
    verify_recent_logs,
    handle_verify_command,
    cli_verify_command,
    VerifyError
)
from historify.config import RepositoryConfig
from historify.changelog import Changelog
from historify.cli_init import init_repository
from historify.hash import hash_file

class TestVerifyImplementation:
    """Test the verify command implementation."""
    
    def setup_method(self):
        """Set up test environment."""
        self.runner = CliRunner()
        self.test_repo_path = Path("test_repo_verify").absolute()
        
        # Initialize a test repository
        if not self.test_repo_path.exists():
            init_repository(str(self.test_repo_path), "test-repo")
        
        # Create test minisign key files
        self.key_dir = Path("test_keys_verify").absolute()
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
            
        # Create a changes directory
        self.changes_dir = self.test_repo_path / "changes"
        self.changes_dir.mkdir(exist_ok=True)
        
        # Configure repository with minisign keys and hash algorithms
        config = RepositoryConfig(str(self.test_repo_path))
        config.set("minisign.key", str(self.minisign_key))
        config.set("minisign.pub", str(self.minisign_pub))
        config.set("hash.algorithms", "blake3,sha256")  # Make sure hash algorithms are set
        
        # Create sample changelog files
        self.changelog1 = self.changes_dir / "changelog-2025-04-01.csv"
        self.changelog2 = self.changes_dir / "changelog-2025-04-10.csv"
        self.changelog3 = self.changes_dir / "changelog-2025-04-20.csv"
        
        # Create the changelog files with proper headers
        self._create_test_changelog(self.changelog1)
        self._create_test_changelog(self.changelog2)
        self._create_test_changelog(self.changelog3)
        
        # Create mock signature files
        open(self.changelog1.with_suffix(".csv.minisig"), "w").close()
        open(self.changelog2.with_suffix(".csv.minisig"), "w").close()
        # No signature for changelog3, simulating an open changelog
    
    def teardown_method(self):
        """Clean up test environment."""
        if self.test_repo_path.exists():
            shutil.rmtree(self.test_repo_path)
        if self.key_dir.exists():
            shutil.rmtree(self.key_dir)
    
    def _create_test_changelog(self, filepath, entries=None):
        """Create a test changelog file with the specified entries."""
        with open(filepath, "w", newline="") as f:
            fieldnames = [
                "timestamp", "transaction_type", "path", "category", 
                "size", "ctime", "mtime", "sha256", "blake3"
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            # Write a closing transaction as the first entry
            timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
            writer.writerow({
                "timestamp": timestamp,
                "transaction_type": "closing",
                "path": "test/path",
                "category": "",
                "size": "",
                "ctime": "",
                "mtime": "",
                "sha256": "",
                "blake3": "previous_hash_value"  # This would be the hash of the previous file
            })
            
            # Add any additional entries
            if entries:
                for entry in entries:
                    writer.writerow(entry)
    
    def test_verify_repository_config(self):
        """Test verifying repository configuration."""
        # Mock RepositoryConfig.check method
        with patch('historify.cli_verify.RepositoryConfig') as mock_config_class:
            mock_config = MagicMock()
            mock_config.check.return_value = []  # No issues
            mock_config_class.return_value = mock_config
            
            issues = verify_repository_config(str(self.test_repo_path))
            
            assert isinstance(issues, list)
            assert len(issues) == 0
            mock_config.check.assert_called_once()
            
            # Test with issues
            mock_config.check.return_value = [("test.key", "Test issue")]
            
            issues = verify_repository_config(str(self.test_repo_path))
            
            assert isinstance(issues, list)
            assert len(issues) == 1
            assert issues[0] == ("test.key", "Test issue")
    
    @patch('historify.cli_verify.minisign_verify')
    def test_verify_signature(self, mock_minisign_verify):
        """Test verifying a file signature."""
        # Create a test file and signature
        test_file = self.test_repo_path / "test_file.txt"
        with open(test_file, "w") as f:
            f.write("Test content")
        
        sig_file = test_file.with_suffix(".txt.minisig")
        with open(sig_file, "w") as f:
            f.write("Test signature")
        
        # Mock minisign_verify to return success
        mock_minisign_verify.return_value = (True, "Signature verified")
        
        # Test successful verification
        success, message = verify_signature(test_file, str(self.minisign_pub))
        
        assert success is True
        assert message == "Signature verified"
        mock_minisign_verify.assert_called_once_with(test_file, str(self.minisign_pub))
        
        # Test failed verification
        mock_minisign_verify.reset_mock()
        mock_minisign_verify.return_value = (False, "Signature verification failed")
        
        success, message = verify_signature(test_file, str(self.minisign_pub))
        
        assert success is False
        assert message == "Signature verification failed"
        mock_minisign_verify.assert_called_once_with(test_file, str(self.minisign_pub))
        
        # Test with nonexistent file
        with pytest.raises(VerifyError, match="File does not exist"):
            verify_signature(self.test_repo_path / "nonexistent.txt", str(self.minisign_pub))
        
        # Test with nonexistent signature
        os.remove(sig_file)
        with pytest.raises(VerifyError, match="Signature file does not exist"):
            verify_signature(test_file, str(self.minisign_pub))
    
    def test_verify_changelog_hash_chain(self):
        """Test verifying the changelog hash chain."""
        # Create a test changelog with specific hash
        test_changelog = self.test_repo_path / "test_changelog.csv"
        with open(test_changelog, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "timestamp", "transaction_type", "path", "category", 
                "size", "ctime", "mtime", "sha256", "blake3"
            ])
            writer.writeheader()
            # Write a closing transaction with a specific hash
            writer.writerow({
                "timestamp": "2025-04-22 12:00:00 UTC",
                "transaction_type": "closing",
                "path": "db/seed.bin",
                "category": "",
                "size": "",
                "ctime": "",
                "mtime": "",
                "sha256": "",
                "blake3": "test_prev_hash_value"
            })
        
        # Test with matching hash
        success, message = verify_changelog_hash_chain(test_changelog, "test_prev_hash_value")
        
        assert success is True
        assert "verified successfully" in message
        
        # Test with non-matching hash
        success, message = verify_changelog_hash_chain(test_changelog, "different_hash_value")
        
        assert success is False
        assert "Hash chain broken" in message
        
        # Test with nonexistent file
        with pytest.raises(VerifyError, match="Changelog file does not exist"):
            verify_changelog_hash_chain(self.test_repo_path / "nonexistent.csv", "test_hash")
        
        # Test with empty file
        empty_changelog = self.test_repo_path / "empty_changelog.csv"
        with open(empty_changelog, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "timestamp", "transaction_type", "path", "category", 
                "size", "ctime", "mtime", "sha256", "blake3"
            ])
            writer.writeheader()
            # No rows
        
        with pytest.raises(VerifyError, match="Changelog file is empty"):
            verify_changelog_hash_chain(empty_changelog, "test_hash")
        
        # Test with wrong first transaction type
        wrong_type_changelog = self.test_repo_path / "wrong_type_changelog.csv"
        with open(wrong_type_changelog, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "timestamp", "transaction_type", "path", "category", 
                "size", "ctime", "mtime", "sha256", "blake3"
            ])
            writer.writeheader()
            # Write a non-closing transaction
            writer.writerow({
                "timestamp": "2025-04-22 12:00:00 UTC",
                "transaction_type": "new",  # Not a closing transaction
                "path": "test.txt",
                "category": "docs",
                "size": "100",
                "ctime": "2025-04-22",
                "mtime": "2025-04-22",
                "sha256": "sha256_hash",
                "blake3": "blake3_hash"
            })
        
        with pytest.raises(VerifyError, match="is not a 'closing' transaction"):
            verify_changelog_hash_chain(wrong_type_changelog, "test_hash")
    
    @patch('historify.cli_verify.hash_file')
    @patch('historify.cli_verify.minisign_verify')
    def test_rebuild_integrity_csv(self, mock_minisign_verify, mock_hash_file):
        """Test rebuilding the integrity CSV file."""
        # Setup mocks
        mock_hash_file.return_value = {"blake3": "test_hash_value"}
        mock_minisign_verify.return_value = (True, "Signature verified")
        
        # Test rebuilding
        result = rebuild_integrity_csv(str(self.test_repo_path))
        
        assert result is True
        
        # Verify the integrity file was created
        integrity_file = self.test_repo_path / "db" / "integrity.csv"
        assert integrity_file.exists()
    
    @patch('historify.cli_verify.verify_repository_config')
    @patch('historify.cli_verify.minisign_verify')
    @patch('historify.cli_verify.hash_file')
    @patch('historify.cli_verify.rebuild_integrity_csv')
    def test_verify_full_chain(self, mock_rebuild, mock_hash_file, mock_minisign_verify, mock_config):
        """Test verifying the full chain of changelogs."""
        # Setup mocks
        mock_config.return_value = []  # No configuration issues
        mock_minisign_verify.return_value = (True, "Signature verified")
        mock_hash_file.return_value = {"blake3": "test_hash_value"}
        mock_rebuild.return_value = True
        
        # Create a seed signature file
        seed_sig = self.test_repo_path / "db" / "seed.bin.minisig"
        with open(seed_sig, "w") as f:
            f.write("Test signature")
        
        # Create proper changelog files for the test
        # These need to form a valid chain when the mocks return the same hash value
        self._create_chain_changelogs()
        
        # Test verification
        success, issues = verify_full_chain(str(self.test_repo_path))
        
        assert success is True
        assert len(issues) == 0
        
        # Test with broken chain
        mock_minisign_verify.side_effect = [
            (True, "Signature verified"),  # Seed verification
            (False, "Signature verification failed"),  # First changelog verification
            (True, "Signature verified")  # Second changelog verification
        ]
        
        success, issues = verify_full_chain(str(self.test_repo_path))
        
        assert success is False
        assert len(issues) > 0
        assert "Signature verification failed" in issues[0]["issue"]
        
        # Verify rebuild was called
        mock_rebuild.assert_called_once_with(str(self.test_repo_path))
    
    def _create_chain_changelogs(self):
        """Create a set of changelogs that form a proper chain."""
        # Clean existing test changelogs
        for file in self.changes_dir.glob("changelog-*.csv"):
            os.remove(file)
            sig_file = file.with_suffix(".csv.minisig")
            if sig_file.exists():
                os.remove(sig_file)
        
        # Create new changelogs with proper chain
        changelogs = [
            self.changes_dir / "changelog-2025-04-01.csv",
            self.changes_dir / "changelog-2025-04-10.csv",
            self.changes_dir / "changelog-2025-04-20.csv"
        ]
        
        # Get the seed hash (or mock one)
        seed_hash = "seed_hash_value"
        
        # First changelog references seed
        with open(changelogs[0], "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "timestamp", "transaction_type", "path", "category", 
                "size", "ctime", "mtime", "sha256", "blake3"
            ])
            writer.writeheader()
            writer.writerow({
                "timestamp": "2025-04-01 12:00:00 UTC",
                "transaction_type": "closing",
                "path": "db/seed.bin",
                "category": "",
                "size": "",
                "ctime": "",
                "mtime": "",
                "sha256": "",
                "blake3": seed_hash
            })
        
        # Create signature file
        open(changelogs[0].with_suffix(".csv.minisig"), "w").close()
        
        # Second changelog references first
        with open(changelogs[1], "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "timestamp", "transaction_type", "path", "category", 
                "size", "ctime", "mtime", "sha256", "blake3"
            ])
            writer.writeheader()
            writer.writerow({
                "timestamp": "2025-04-10 12:00:00 UTC",
                "transaction_type": "closing",
                "path": f"changes/{changelogs[0].name}",
                "category": "",
                "size": "",
                "ctime": "",
                "mtime": "",
                "sha256": "",
                "blake3": "test_hash_value"  # This matches the mock hash_file return value
            })
        
        # Create signature file
        open(changelogs[1].with_suffix(".csv.minisig"), "w").close()
        
        # Third changelog references second
        with open(changelogs[2], "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "timestamp", "transaction_type", "path", "category", 
                "size", "ctime", "mtime", "sha256", "blake3"
            ])
            writer.writeheader()
            writer.writerow({
                "timestamp": "2025-04-20 12:00:00 UTC",
                "transaction_type": "closing",
                "path": f"changes/{changelogs[1].name}",
                "category": "",
                "size": "",
                "ctime": "",
                "mtime": "",
                "sha256": "",
                "blake3": "test_hash_value"  # This matches the mock hash_file return value
            })
        
        # No signature file for the last one (simulating open changelog)
    
    @patch('historify.cli_verify.minisign_verify')
    @patch('historify.cli_verify.hash_file')
    def test_verify_recent_logs(self, mock_hash_file, mock_minisign_verify):
        """Test verifying only recent logs."""
        # Setup mocks
        mock_minisign_verify.return_value = (True, "Signature verified")
        mock_hash_file.return_value = {"blake3": "test_hash_value"}
        
        # Create proper chain for this test
        self._create_chain_changelogs()
        
        # Test verification
        success, issues = verify_recent_logs(str(self.test_repo_path))
        
        assert success is True
        assert len(issues) == 0
        
        # Verify only the latest signed changelog was verified
        assert mock_minisign_verify.call_count == 1
        
        # Test with verification failure
        mock_minisign_verify.reset_mock()
        mock_minisign_verify.return_value = (False, "Signature verification failed")
        
        success, issues = verify_recent_logs(str(self.test_repo_path))
        
        assert success is False
        assert len(issues) > 0
        assert "Signature verification failed" in issues[0]["issue"]
    
    @patch('historify.cli_verify.verify_repository_config')
    @patch('historify.cli_verify.verify_full_chain')
    @patch('historify.cli_verify.verify_recent_logs')
    def test_handle_verify_command(self, mock_recent, mock_full, mock_config):
        """Test handling the verify command."""
        # Setup mocks
        mock_config.return_value = []  # No config issues
        mock_full.return_value = (True, [])  # Full chain verification success
        mock_recent.return_value = (True, [])  # Recent logs verification success
        
        # Test with full chain
        success, issues = handle_verify_command(str(self.test_repo_path), full_chain=True)
        
        assert success is True
        assert len(issues) == 0
        mock_config.assert_called_once()
        mock_full.assert_called_once()
        mock_recent.assert_not_called()
        
        # Reset mocks
        mock_config.reset_mock()
        mock_full.reset_mock()
        
        # Test with recent logs
        success, issues = handle_verify_command(str(self.test_repo_path), full_chain=False)
        
        assert success is True
        assert len(issues) == 0
        mock_config.assert_called_once()
        mock_full.assert_not_called()
        mock_recent.assert_called_once()
        
        # Test with config issues
        mock_config.reset_mock()
        mock_recent.reset_mock()
        mock_config.return_value = [("test.key", "Test issue")]
        
        success, issues = handle_verify_command(str(self.test_repo_path), full_chain=False)
        
        assert success is False
        assert len(issues) == 1
        assert issues[0]["file"] == "config"
        mock_config.assert_called_once()
        mock_full.assert_not_called()
        mock_recent.assert_not_called()
    
    @patch('historify.cli_verify.handle_verify_command')
    def test_cli_verify_command(self, mock_handle):
        """Test the CLI verify command function."""
        # Setup mock
        mock_handle.return_value = (True, [])  # Success with no issues
        
        # Test with success
        exit_code = cli_verify_command(str(self.test_repo_path), full_chain=False)
        
        assert exit_code == 0
        mock_handle.assert_called_once_with(str(self.test_repo_path), False)
        
        # Test with warnings
        mock_handle.reset_mock()
        mock_handle.return_value = (True, [{"file": "test.txt", "issue": "Warning"}])
        
        exit_code = cli_verify_command(str(self.test_repo_path), full_chain=False)
        
        assert exit_code == 0  # Still success with warnings
        mock_handle.assert_called_once()
        
        # Test with failure
        mock_handle.reset_mock()
        mock_handle.return_value = (False, [{"file": "test.txt", "issue": "Error"}])
        
        exit_code = cli_verify_command(str(self.test_repo_path), full_chain=False)
        
        assert exit_code == 3  # Error code for integrity error
        mock_handle.assert_called_once()
        
        # Test with exception
        mock_handle.reset_mock()
        mock_handle.side_effect = VerifyError("Test error")
        
        exit_code = cli_verify_command(str(self.test_repo_path), full_chain=False)
        
        assert exit_code == 3  # Error code
        mock_handle.assert_called_once()
    
    def test_cli_command(self):
        """Test the CLI command through Click."""
        with patch('historify.cli.cli_verify_command') as mock_verify:
            mock_verify.return_value = 0
            
            # Test without full-chain option
            result = self.runner.invoke(verify, [str(self.test_repo_path)])
            
            assert result.exit_code == 0
            mock_verify.assert_called_once_with(str(self.test_repo_path), False)
            
            # Test with full-chain option
            mock_verify.reset_mock()
            result = self.runner.invoke(verify, ["--full-chain", str(self.test_repo_path)])
            
            assert result.exit_code == 0
            mock_verify.assert_called_once_with(str(self.test_repo_path), True)
