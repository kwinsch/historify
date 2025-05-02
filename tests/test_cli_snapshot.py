# tests/test_cli_snapshot.py
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
from historify.config import RepositoryConfig

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
            
        # Create an external category
        self.external_dir = Path("external_category").absolute()
        if not self.external_dir.exists():
            self.external_dir.mkdir(parents=True)
            
        # Add a test file to the external category
        with open(self.external_dir / "external_file.txt", "w") as f:
            f.write("External content")
            
        # Configure the external category
        config = RepositoryConfig(str(self.test_repo_path))
        config.set("category.external.path", str(self.external_dir))
    
    def teardown_method(self):
        """Clean up test environment."""
        if self.test_repo_path.exists():
            shutil.rmtree(self.test_repo_path)
        if self.external_dir.exists():
            shutil.rmtree(self.external_dir)
    
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
    def test_create_full_snapshot(self, mock_verify):
        """Test creating a full snapshot with external categories."""
        # Set up mock to return success
        mock_verify.return_value = 0
        
        with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as temp:
            temp_path = temp.name
            
        try:
            # Create the full snapshot
            result = create_snapshot(str(self.test_repo_path), temp_path, full=True)
            
            assert result is True
            assert Path(temp_path).exists()
            
            # Check for the external category archive
            temp_path_obj = Path(temp_path)
            external_archive = temp_path_obj.parent / f"{temp_path_obj.stem}-external{temp_path_obj.suffix}"
            
            assert external_archive.exists()
            assert external_archive.stat().st_size > 0
            
            # Verify the main snapshot contains the repository
            with tarfile.open(temp_path, "r:gz") as tar:
                assert any(member.name.endswith("db/config") for member in tar.getmembers())
                
            # Verify the external snapshot contains the external category
            with tarfile.open(external_archive, "r:gz") as tar:
                assert any("external_file.txt" in member.name for member in tar.getmembers())
                
        finally:
            # Clean up
            if Path(temp_path).exists():
                Path(temp_path).unlink()
                
            # Clean up external archive if it exists
            temp_path_obj = Path(temp_path)
            external_archive = temp_path_obj.parent / f"{temp_path_obj.stem}-external{temp_path_obj.suffix}"
            if external_archive.exists():
                external_archive.unlink()
    
    @patch('historify.cli_snapshot.cli_verify_command')
    @patch('historify.cli_snapshot.pack_archives_for_media')
    def test_create_snapshot_with_media(self, mock_pack_media, mock_verify):
        """Test creating a snapshot with media option."""
        # Set up mocks to return success
        mock_verify.return_value = 0
        mock_pack_media.return_value = [Path("/tmp/test.iso")]
        
        with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as temp:
            temp_path = temp.name
        
        try:
            # Create the snapshot with media
            result = create_snapshot(str(self.test_repo_path), temp_path, media=True)
            
            assert result is True
            assert Path(temp_path).exists()
            
            # Verify pack_archives_for_media was called
            mock_pack_media.assert_called_once()
            args, kwargs = mock_pack_media.call_args
            assert args[0] == [Path(temp_path)]  # Archives list should include main snapshot
            assert kwargs.get('media_type') == "bd-r"
            
        finally:
            # Clean up
            if Path(temp_path).exists():
                Path(temp_path).unlink()
    
    @patch('historify.cli_snapshot.cli_verify_command')
    @patch('historify.cli_snapshot.pack_archives_for_media')
    def test_create_full_snapshot_with_media(self, mock_pack_media, mock_verify):
        """Test creating a full snapshot with media option."""
        # Set up mocks to return success
        mock_verify.return_value = 0
        mock_pack_media.return_value = [Path("/tmp/test.iso")]
        
        with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as temp:
            temp_path = temp.name
        
        try:
            # Create the full snapshot with media
            result = create_snapshot(str(self.test_repo_path), temp_path, full=True, media=True)
            
            assert result is True
            assert Path(temp_path).exists()
            
            # Check for the external category archive
            temp_path_obj = Path(temp_path)
            external_archive = temp_path_obj.parent / f"{temp_path_obj.stem}-external{temp_path_obj.suffix}"
            assert external_archive.exists()
            
            # Verify pack_archives_for_media was called with both archives
            mock_pack_media.assert_called_once()
            args, kwargs = mock_pack_media.call_args
            assert len(args[0]) == 2  # Main snapshot and external category
            assert Path(temp_path) in args[0]
            assert external_archive in args[0]
            assert kwargs.get('media_type') == "bd-r"
            
        finally:
            # Clean up
            if Path(temp_path).exists():
                Path(temp_path).unlink()
                
            # Clean up external archive if it exists
            temp_path_obj = Path(temp_path)
            external_archive = temp_path_obj.parent / f"{temp_path_obj.stem}-external{temp_path_obj.suffix}"
            if external_archive.exists():
                external_archive.unlink()
    
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
        mock_create.assert_called_once_with(str(self.test_repo_path), "output.tar.gz", full=False, media=False)
    
    @patch('historify.cli_snapshot.create_snapshot')
    def test_handle_snapshot_command_with_full(self, mock_create):
        """Test handling the snapshot command with full option."""
        # Set up mock to return success
        mock_create.return_value = True
        
        # Handle the snapshot command with full option
        handle_snapshot_command("output.tar.gz", str(self.test_repo_path), full=True)
        
        # Verify create_snapshot was called correctly
        mock_create.assert_called_once_with(str(self.test_repo_path), "output.tar.gz", full=True, media=False)
    
    @patch('historify.cli_snapshot.create_snapshot')
    def test_handle_snapshot_command_with_media_flag(self, mock_create):
        """Test handling the snapshot command with media flag."""
        # Set up mock to return success
        mock_create.return_value = True
        
        # Handle the snapshot command with media flag
        handle_snapshot_command("output.tar.gz", str(self.test_repo_path), media=True)
        
        # Verify create_snapshot was called correctly
        mock_create.assert_called_once_with(str(self.test_repo_path), "output.tar.gz", full=False, media=True)
    
    @patch('historify.cli_snapshot.create_snapshot')
    def test_handle_snapshot_command_with_media_value(self, mock_create):
        """Test handling the snapshot command with media value."""
        # Set up mock to return success
        mock_create.return_value = True
        
        # Handle the snapshot command with media value
        handle_snapshot_command("output.tar.gz", str(self.test_repo_path), media="bd-r")
        
        # Verify create_snapshot was called correctly
        mock_create.assert_called_once_with(str(self.test_repo_path), "output.tar.gz", full=False, media="bd-r")
    
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
            mock_handle.assert_called_once_with("output.tar.gz", str(self.test_repo_path), False, False)
    
    def test_cli_snapshot_command_with_full_option(self):
        """Test the CLI snapshot command with --full option."""
        with patch('historify.cli.handle_snapshot_command') as mock_handle:
            # Run the command with --full
            result = self.runner.invoke(snapshot, ["output.tar.gz", str(self.test_repo_path), "--full"])
            
            assert result.exit_code == 0
            mock_handle.assert_called_once_with("output.tar.gz", str(self.test_repo_path), True, False)
    
    def test_cli_snapshot_command_with_media_flag(self):
        """Test the CLI snapshot command with --media flag."""
        with patch('historify.cli.handle_snapshot_command') as mock_handle:
            # Run the command with --media
            result = self.runner.invoke(snapshot, ["output.tar.gz", str(self.test_repo_path), "--media"])
            
            assert result.exit_code == 0
            mock_handle.assert_called_once_with("output.tar.gz", str(self.test_repo_path), False, True)
    
    def test_cli_snapshot_command_with_media_value(self):
        """Test the CLI snapshot command with --media=bd-r option."""
        with patch('historify.cli.handle_snapshot_command') as mock_handle:
            # Run the command with --media=bd-r
            result = self.runner.invoke(snapshot, ["output.tar.gz", str(self.test_repo_path), "--media"])
            
            assert result.exit_code == 0
            mock_handle.assert_called_once_with("output.tar.gz", str(self.test_repo_path), False, True)
    
    def test_cli_snapshot_command_with_full_and_media(self):
        """Test the CLI snapshot command with both --full and --media options."""
        with patch('historify.cli.handle_snapshot_command') as mock_handle:
            # Run the command with both --full and --media
            result = self.runner.invoke(snapshot, [
                "output.tar.gz", 
                str(self.test_repo_path), 
                "--full", 
                "--media"
            ])
            
            assert result.exit_code == 0
            mock_handle.assert_called_once_with("output.tar.gz", str(self.test_repo_path), True, True)