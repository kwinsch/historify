"""
Integration tests for the scan command.
"""
import pytest
import os
import csv
import shutil
import time
from pathlib import Path
from click.testing import CliRunner
from unittest.mock import patch, MagicMock

from historify.cli import init, config, add_category, start_transaction, scan
from historify.cli_init import init_repository
from historify.config import RepositoryConfig
from historify.changelog import Changelog
from historify.csv_manager import CSVManager

class TestScanIntegration:
    """Integration tests for the scan command using the CLI."""
    
    def setup_method(self):
        """Set up test environment."""
        self.runner = CliRunner()
        self.test_dir = Path("scan_integration_test")
        
        # Clean up previous test directory if it exists
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
            
        # Create test directory
        self.test_dir.mkdir()
        
        # Create test minisign keys
        self.key_dir = self.test_dir / "keys"
        self.key_dir.mkdir()
        
        # Create mock key files
        self.minisign_key = self.key_dir / "test.key"
        self.minisign_pub = self.key_dir / "test.pub"
        
        with open(self.minisign_key, "w") as f:
            f.write("untrusted comment: minisign unencrypted secret key\n")
            f.write("TESTKEY123456789\n")
        
        with open(self.minisign_pub, "w") as f:
            f.write("untrusted comment: minisign public key\n")
            f.write("TESTPUB987654321\n")
        
        # Initialize repository through CLI
        self.repo_path = self.test_dir / "repo"
        self.runner.invoke(init, [str(self.repo_path), "--name", "test-repo"])
        
        # Configure minisign keys
        self.runner.invoke(config, ["minisign.key", str(self.minisign_key), str(self.repo_path)])
        self.runner.invoke(config, ["minisign.pub", str(self.minisign_pub), str(self.repo_path)])
        
        # Create data directories
        self.data_dir = self.repo_path / "data"
        self.data_dir.mkdir()
        
        # Add category
        self.runner.invoke(add_category, ["data", "data", str(self.repo_path)])
        
        # Create the changes directory
        changes_dir = self.repo_path / "changes"
        changes_dir.mkdir(exist_ok=True)
        
        # Manually create a changelog file for testing
        self.changelog_file = changes_dir / "changelog-2025-04-22.csv"
        
        # Create the CSV file with headers
        with open(self.changelog_file, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "timestamp", "transaction_type", "path", "category", 
                "size", "ctime", "mtime", "sha256", "blake3"
            ])
    
    def teardown_method(self):
        """Clean up test environment."""
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
    
    @patch('historify.cli_verify.minisign_verify', return_value=(True, "Signature verified"))
    @patch('historify.minisign.minisign_sign', return_value=True)
    def test_complete_workflow(self, mock_sign, mock_verify):
        """Test a complete workflow with the CLI."""
        # Create test files
        file1 = self.data_dir / "test1.txt"
        file2 = self.data_dir / "test2.txt"
        
        with open(file1, "w") as f:
            f.write("Test file 1")
        with open(file2, "w") as f:
            f.write("Test file 2")
        
        # 1. First scan - detect new files
        result1 = self.runner.invoke(scan, [str(self.repo_path)])
        assert result1.exit_code == 0
        assert "New:" in result1.output
        
        # Verify changes are recorded
        with open(self.changelog_file, "r", newline="") as f:
            reader = csv.DictReader(f)
            entries = list(reader)
            
            # Should have entries for both files
            test1_entries = [e for e in entries if e["path"] == "test1.txt"]
            test2_entries = [e for e in entries if e["path"] == "test2.txt"]
            
            assert len(test1_entries) == 1
            assert len(test2_entries) == 1
            assert test1_entries[0]["transaction_type"] == "new"
            assert test2_entries[0]["transaction_type"] == "new"
        
        # 2. Modify file1
        with open(file1, "w") as f:
            f.write("Modified test file 1")
        
        # Wait briefly to ensure mtime changes
        time.sleep(0.1)
        
        # 3. Move file2
        file2_new = self.data_dir / "test2_moved.txt"
        shutil.move(file2, file2_new)
        
        # 4. Create file3
        file3 = self.data_dir / "test3.txt"
        with open(file3, "w") as f:
            f.write("Test file 3")
        
        # Second scan - detect changes
        result2 = self.runner.invoke(scan, [str(self.repo_path)])
        assert result2.exit_code == 0
        
        # Output should mention changed, moved, and new files
        output2 = result2.output
        assert any(x in output2 for x in ["Changed:", "Moved:", "New:"])
        
        # Verify changelog records
        with open(self.changelog_file, "r", newline="") as f:
            reader = csv.DictReader(f)
            entries = list(reader)
            
            # Find entries for each file
            entries1 = [e for e in entries if e["path"] == "test1.txt"]
            entries2_moved = [e for e in entries if e["path"] == "test2_moved.txt"]
            entries3 = [e for e in entries if e["path"] == "test3.txt"]
            
            # Verify operations
            assert len(entries1) >= 2
            assert entries1[0]["transaction_type"] == "new"
            assert entries1[1]["transaction_type"] == "changed"
            
            assert len(entries2_moved) >= 1
            assert entries2_moved[0]["transaction_type"] == "move"
            assert entries2_moved[0]["blake3"] == "test2.txt"
            
            assert len(entries3) >= 1
            assert entries3[0]["transaction_type"] == "new"
        
        # 5. Delete file1
        file1.unlink()
        
        # Third scan - detect deletion
        result3 = self.runner.invoke(scan, [str(self.repo_path)])
        assert result3.exit_code == 0
        assert "Deleted:" in result3.output
        
        # Verify deletion record
        with open(self.changelog_file, "r", newline="") as f:
            reader = csv.DictReader(f)
            entries = list(reader)
            
            # Find the latest entry for test1.txt
            entries1 = [e for e in entries if e["path"] == "test1.txt"]
            assert len(entries1) >= 3
            assert entries1[-1]["transaction_type"] == "deleted"

    @patch('historify.cli_config.backup_public_key')
    def test_key_backup_integration(self, mock_backup):
        """Test public key backup throughout the command workflow."""
        # Create a test public key with key ID in the comment
        pub_key_path = self.test_dir / "integration_test.pub"
        with open(pub_key_path, "w") as f:
            f.write("untrusted comment: minisign public key INTEGRATION123\n")
            f.write("TESTKEY123456789\n")
        
        # Make the mock return the key ID
        mock_backup.return_value = "INTEGRATION123"
        
        # 1. Configure the public key
        result = self.runner.invoke(config, ["minisign.pub", str(pub_key_path), str(self.repo_path)])
        assert result.exit_code == 0
        
        # Verify the backup_public_key was called with the absolute path to the repository
        repo_abs_path = self.repo_path.resolve()
        mock_backup.assert_called_once_with(str(repo_abs_path), str(pub_key_path))
        
        # Reset mock for next test
        mock_backup.reset_mock()
        
        # 2. Create a second key and update config
        pub_key2_path = self.test_dir / "integration_test2.pub"
        with open(pub_key2_path, "w") as f:
            f.write("untrusted comment: minisign public key INTEGRATION456\n")
            f.write("TESTKEY987654321\n")
            
        # Update the mock's return value
        mock_backup.return_value = "INTEGRATION456"
        
        # Configure the new key
        result = self.runner.invoke(config, ["minisign.pub", str(pub_key2_path), str(self.repo_path)])
        assert result.exit_code == 0
        
        # Verify the backup_public_key was called again with the absolute path
        mock_backup.assert_called_once_with(str(repo_abs_path), str(pub_key2_path))