"""
Tests for the snapshot command implementation.
"""
import pytest
import os
import shutil
import tarfile
import tempfile
import click
from pathlib import Path
from click.testing import CliRunner
from unittest.mock import patch, MagicMock

from historify.cli import snapshot
from historify.cli_snapshot import create_snapshot, handle_snapshot_command, SnapshotError
from historify.cli_init import init_repository

class TestSnapshotImplementation:
    """Test the snapshot command implementation."""
    
    def setup_method(self):
        """Set up test environment."""
        self.runner = CliRunner()
        self.test_repo_path = Path("test_repo_snapshot").absolute()
        
        # Initialize a test repository
        if not self.test_repo_path.exists():
            init_repository(str(self.test_repo_path), "test-repo")
        
        # Create some sample files in the repository
        test_file = self.test_repo_path / "db" / "test_file.txt"
        with open(test_file, "w") as f:
            f.write("Test content")
    
    def teardown_method(self):
        """Clean up test environment."""
        if self.test_repo_path.exists():
            shutil.rmtree(self.test_repo_path)
    
    @patch('historify.cli_snapshot.cli_verify_command')
    def test_create_snapshot(self, mock_verify):
        """Test creating a snapshot archive."""
        # Set up mock to return success
        mock_verify.return_value = 0
        
        with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as temp:
            temp_path = temp.name
        
        try:
            # Create the snapshot
            result = create_snapshot(str(self.test_repo_path), temp_path)
            
            assert result is True
            assert Path(temp_path).exists()
            assert Path(temp_path).stat().st_size > 0
            
            # Verify the snapshot was created with the correct structure
            with tarfile.open(temp_path, "r:gz") as tar:
                # Check that the repository structure is preserved
                assert any(member.name.endswith("db/config") for member in tar.getmembers())
                assert any(member.name.endswith("db/seed.bin") for member in tar.getmembers())
                
                # Check our test file is included
                assert any(member.name.endswith("db/test_file.txt") for member in tar.getmembers())
            
            # Verify that verify was called
            mock_verify.assert_called_once_with(str(self.test_repo_path), full_chain=False)
        finally:
            # Clean up
            if Path(temp_path).exists():
                Path(temp_path).unlink()
    
    @patch('historify.cli_snapshot.cli_verify_command')
    def test_create_snapshot_with_verify_failure(self, mock_verify):
        """Test creating a snapshot when verification fails."""
        # Set up mock to return failure
        mock_verify.return_value = 3  # Error code for verification failure
        
        with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as temp:
            temp_path = temp.name
        
        try:
            # Create the snapshot (should fail)
            with pytest.raises(SnapshotError, match="Repository integrity check failed"):
                create_snapshot(str(self.test_repo_path), temp_path)
            
            # Verify that the snapshot was not created
            assert not Path(temp_path).exists()
            
            # Verify that verify was called
            mock_verify.assert_called_once_with(str(self.test_repo_path), full_chain=False)
        finally:
            # Clean up
            if Path(temp_path).exists():
                Path(temp_path).unlink()
    
    @patch('historify.cli_snapshot.create_snapshot')
    def test_handle_snapshot_command(self, mock_create):
        """Test handling the snapshot command."""
        # Set up mock to return success
        mock_create.return_value = True
        
        # Handle the snapshot command
        handle_snapshot_command("output.tar.gz", str(self.test_repo_path))
        
        # Verify create_snapshot was called correctly
        mock_create.assert_called_once_with(str(self.test_repo_path), "output.tar.gz")
    
    @patch('historify.cli_snapshot.create_snapshot')
    def test_handle_snapshot_command_error(self, mock_create):
        """Test handling the snapshot command with an error."""
        # Set up mock to raise an error
        mock_create.side_effect = SnapshotError("Test error")
        
        # Handle the snapshot command
        with pytest.raises(click.Abort):
            handle_snapshot_command("output.tar.gz", str(self.test_repo_path))
        
        # Verify create_snapshot was called
        mock_create.assert_called_once()
    
    def test_cli_snapshot_command(self):
        """Test the CLI snapshot command."""
        with patch('historify.cli.handle_snapshot_command') as mock_handle:
            # Run the command
            result = self.runner.invoke(snapshot, ["output.tar.gz", str(self.test_repo_path)])
            
            assert result.exit_code == 0
            mock_handle.assert_called_once_with("output.tar.gz", str(self.test_repo_path))
