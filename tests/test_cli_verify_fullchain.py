"""
Tests for the full chain verification functionality.
"""
import pytest
import os
import csv
import shutil
from pathlib import Path
from click.testing import CliRunner
from unittest.mock import patch, MagicMock

from historify.cli import verify
from historify.cli_verify import (
    verify_full_chain,
    handle_verify_command,
    cli_verify_command
)
from historify.cli_init import init_repository
from historify.config import RepositoryConfig
from historify.changelog import Changelog
from historify.hash import hash_file

class TestFullChainVerification:
    """Test the full chain verification functionality."""
    
    def setup_method(self):
        """Set up test environment."""
        self.runner = CliRunner()
        self.test_repo_path = Path("test_repo_full_chain").absolute()
        
        # Initialize a test repository
        if not self.test_repo_path.exists():
            init_repository(str(self.test_repo_path), "test-repo")
        
        # Create test minisign key files
        self.key_dir = Path("test_keys_verification").absolute()
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
            
        # Create repository structure
        self.db_dir = self.test_repo_path / "db"
        self.changes_dir = self.test_repo_path / "changes"
        
        # Configure repository with minisign keys
        config = RepositoryConfig(str(self.test_repo_path))
        config.set("minisign.key", str(self.minisign_key))
        config.set("minisign.pub", str(self.minisign_pub))
        
        # Create a seed signature file
        self.seed_file = self.db_dir / "seed.bin"
        self.seed_sig_file = self.seed_file.with_suffix(".bin.minisig")
        with open(self.seed_sig_file, "w") as f:
            f.write("Dummy seed signature")
    
    def teardown_method(self):
        """Clean up test environment."""
        if self.test_repo_path.exists():
            shutil.rmtree(self.test_repo_path)
        if self.key_dir.exists():
            shutil.rmtree(self.key_dir)
    
    def create_test_changelog(self, name, reference_path, reference_hash, add_signature=True):
        """
        Create a test changelog file with proper closing transaction.
        
        Args:
            name: Name of the changelog file
            reference_path: Path to reference in closing transaction
            reference_hash: Hash to include in closing transaction
            add_signature: Whether to create a signature file
        """
        changelog_file = self.changes_dir / name
        
        with open(changelog_file, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "timestamp", "transaction_type", "path", "category", 
                "size", "ctime", "mtime", "sha256", "blake3"
            ])
            writer.writeheader()
            writer.writerow({
                "timestamp": "2025-04-22 12:00:00 UTC",
                "transaction_type": "closing",
                "path": reference_path,
                "category": "",
                "size": "",
                "ctime": "",
                "mtime": "",
                "sha256": "",
                "blake3": reference_hash
            })
        
        if add_signature:
            sig_file = changelog_file.with_suffix(".csv.minisig")
            with open(sig_file, "w") as f:
                f.write("Dummy signature for testing")
    
    @patch('historify.cli_verify.minisign_verify')
    @patch('historify.cli_verify.hash_file')
    def test_valid_full_chain(self, mock_hash_file, mock_minisign_verify):
        """Test a valid chain of changelogs."""
        # Setup mocks for validation
        mock_minisign_verify.return_value = (True, "Signature verified")
        mock_hash_file.return_value = {"blake3": "test_hash_value"}
        
        # Create a valid chain
        seed_hash = "seed_hash_value"
        
        # Create changelog series
        self.create_test_changelog("changelog-2025-04-01.csv", "db/seed.bin", seed_hash)
        self.create_test_changelog("changelog-2025-04-10.csv", "changes/changelog-2025-04-01.csv", "test_hash_value")
        self.create_test_changelog("changelog-2025-04-20.csv", "changes/changelog-2025-04-10.csv", "test_hash_value")
        
        # Last changelog doesn't need a signature (current open changelog)
        self.create_test_changelog("changelog-2025-04-22.csv", "changes/changelog-2025-04-20.csv", "test_hash_value", add_signature=False)
        
        # Run verification
        success, issues = verify_full_chain(str(self.test_repo_path))
        
        # Assertions
        assert success is True
        assert not issues
        
        # Verify calls made
        assert mock_minisign_verify.call_count >= 4  # seed + 3 changelogs
    
    @patch('historify.cli_verify.minisign_verify')
    @patch('historify.cli_verify.hash_file')
    def test_missing_intermediate_signature(self, mock_hash_file, mock_minisign_verify):
        """Test chain with missing signature in the middle."""
        # Setup mocks
        mock_minisign_verify.return_value = (True, "Signature verified")
        mock_hash_file.return_value = {"blake3": "test_hash_value"}
        
        # Create a chain with missing signature
        seed_hash = "seed_hash_value"
        
        # Create changelog series
        self.create_test_changelog("changelog-2025-04-01.csv", "db/seed.bin", seed_hash)
        
        # Second changelog without signature
        self.create_test_changelog("changelog-2025-04-10.csv", "changes/changelog-2025-04-01.csv", "test_hash_value", add_signature=False)
        
        self.create_test_changelog("changelog-2025-04-20.csv", "changes/changelog-2025-04-10.csv", "test_hash_value")
        
        # Last changelog doesn't need a signature (current open changelog)
        self.create_test_changelog("changelog-2025-04-22.csv", "changes/changelog-2025-04-20.csv", "test_hash_value", add_signature=False)
        
        # Run verification
        success, issues = verify_full_chain(str(self.test_repo_path))
        
        # Assertions
        assert success is False
        assert len(issues) >= 1
        assert any("missing" in issue["issue"].lower() for issue in issues)
    
    @patch('historify.cli_verify.minisign_verify')
    @patch('historify.cli_verify.hash_file')
    def test_broken_hash_chain(self, mock_hash_file, mock_minisign_verify):
        """Test chain with incorrect hash reference."""
        # Setup mocks
        mock_minisign_verify.return_value = (True, "Signature verified")
        
        # Use a side effect to return different hash values for different files
        def hash_side_effect(file_path):
            if "changelog-2025-04-01.csv" in str(file_path):
                return {"blake3": "hash_1"}
            elif "changelog-2025-04-10.csv" in str(file_path):
                return {"blake3": "hash_2"}
            elif "changelog-2025-04-20.csv" in str(file_path):
                return {"blake3": "hash_3"}
            else:
                return {"blake3": "seed_hash"}
        
        mock_hash_file.side_effect = hash_side_effect
        
        # Create a chain with hash mismatch
        self.create_test_changelog("changelog-2025-04-01.csv", "db/seed.bin", "seed_hash")
        
        # This changelog references the correct hash
        self.create_test_changelog("changelog-2025-04-10.csv", "changes/changelog-2025-04-01.csv", "hash_1")
        
        # This changelog has incorrect hash reference (should be hash_2 but using hash_wrong)
        self.create_test_changelog("changelog-2025-04-20.csv", "changes/changelog-2025-04-10.csv", "hash_wrong")
        
        # Last changelog doesn't need a signature
        self.create_test_changelog("changelog-2025-04-22.csv", "changes/changelog-2025-04-20.csv", "hash_3", add_signature=False)
        
        # Run verification
        success, issues = verify_full_chain(str(self.test_repo_path))
        
        # Assertions
        assert success is False
        assert len(issues) >= 1
        assert any("hash" in issue["issue"].lower() for issue in issues)
    
    @patch('historify.cli_verify.minisign_verify')
    @patch('historify.cli_verify.hash_file')
    def test_valid_chain_with_open_changelog(self, mock_hash_file, mock_minisign_verify):
        """Test valid chain with current open changelog."""
        # Setup mocks
        mock_minisign_verify.return_value = (True, "Signature verified")
        mock_hash_file.return_value = {"blake3": "test_hash_value"}
        
        # Create a valid chain
        seed_hash = "seed_hash_value"
        
        # Create changelog series
        self.create_test_changelog("changelog-2025-04-01.csv", "db/seed.bin", seed_hash)
        self.create_test_changelog("changelog-2025-04-10.csv", "changes/changelog-2025-04-01.csv", "test_hash_value")
        
        # Create changelog without signature (current open)
        self.create_test_changelog("changelog-2025-04-20.csv", "changes/changelog-2025-04-10.csv", "test_hash_value", add_signature=False)
        
        # Patch get_current_changelog to return the open changelog
        with patch('historify.changelog.Changelog.get_current_changelog') as mock_get_current:
            mock_get_current.return_value = self.changes_dir / "changelog-2025-04-20.csv"
            
            # Run verification
            success, issues = verify_full_chain(str(self.test_repo_path))
            
            # Assertions
            assert success is True
            assert not issues
    
    @patch('historify.cli_verify.minisign_verify')
    @patch('historify.cli_verify.hash_file')
    def test_no_changelogs(self, mock_hash_file, mock_minisign_verify):
        """Test verification with only seed file (no changelogs)."""
        # Setup mocks
        mock_minisign_verify.return_value = (True, "Signature verified")
        mock_hash_file.return_value = {"blake3": "seed_hash_value"}
        
        # Run verification with only seed file (no changelogs)
        success, issues = verify_full_chain(str(self.test_repo_path))
        
        # Assertions
        assert success is True
        assert not issues or any("warning" in issue["issue"].lower() for issue in issues)
    
    @patch('historify.cli_verify.verify_repository_config')
    @patch('historify.cli_verify.verify_full_chain')
    def test_handle_verify_command_full_chain(self, mock_full_chain, mock_config):
        """Test handle_verify_command with full chain option."""
        # Setup mocks
        mock_config.return_value = []  # No config issues
        mock_full_chain.return_value = (True, [])  # Full chain verification success
        
        # Run command
        success, issues = handle_verify_command(str(self.test_repo_path), full_chain=True)
        
        # Assertions
        assert success is True
        assert not issues
        mock_config.assert_called_once()
        mock_full_chain.assert_called_once()
    
    def test_cli_verify_command_integration(self):
        """Test CLI verify command through Click interface."""
        # Setup a basic repository with valid chain for integration test
        self.create_test_changelog("changelog-2025-04-01.csv", "db/seed.bin", "seed_hash_value")
        
        # Create a signature for the existing seed file
        with open(self.seed_sig_file, "w") as f:
            f.write("Dummy seed signature")
        
        # Patch the core verification function
        with patch('historify.cli_verify.handle_verify_command') as mock_handle:
            mock_handle.return_value = (True, [])  # Success with no issues
            
            # Test with full chain flag
            result = self.runner.invoke(verify, ["--full-chain", str(self.test_repo_path)])
            
            assert result.exit_code == 0
            assert "Verification completed successfully" in result.output
            mock_handle.assert_called_once_with(str(self.test_repo_path), True)
            
            # Reset mock and test without flag
            mock_handle.reset_mock()
            mock_handle.return_value = (True, [])
            
            result = self.runner.invoke(verify, [str(self.test_repo_path)])
            
            assert result.exit_code == 0
            assert "Verification completed successfully" in result.output
            mock_handle.assert_called_once_with(str(self.test_repo_path), False)
    
    def test_cli_verify_command_with_issues(self):
        """Test CLI verify command with verification issues."""
        # Patch handle_verify_command to return issues
        with patch('historify.cli_verify.handle_verify_command') as mock_handle:
            mock_handle.return_value = (False, [
                {"file": "test.csv", "issue": "Test error message"}
            ])
            
            # Run command
            result = self.runner.invoke(verify, [str(self.test_repo_path)])
            
            # Assertions
            assert result.exit_code != 0
            assert "Verification issues found" in result.output
            assert "test.csv: Test error message" in result.output
    
    @patch('historify.cli_verify.minisign_verify')
    def test_verify_signature_functions(self, mock_minisign_verify):
        """Test the verify_signature function."""
        from historify.cli_verify import verify_signature
        
        # Setup mock
        mock_minisign_verify.return_value = (True, "Signature verified")
        
        # Create test file and signature
        test_file = self.test_repo_path / "test.txt"
        with open(test_file, "w") as f:
            f.write("Test content")
        
        sig_file = test_file.with_suffix(".txt.minisig")
        with open(sig_file, "w") as f:
            f.write("Test signature")
        
        # Verify signature
        success, message = verify_signature(test_file, str(self.minisign_pub))
        
        # Assertions
        assert success is True
        assert message == "Signature verified"
        mock_minisign_verify.assert_called_once_with(test_file, str(self.minisign_pub))
