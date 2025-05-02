"""
Tests for the media packing functionality.
"""
import pytest
import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

from historify.media_packer import (
    calculate_archives_size,
    split_archives_for_media,
    create_iso_image,
    pack_for_bd_r,
    pack_archives_for_media,
    BD_R_SINGLE_LAYER_CAPACITY,
    MediaPackError
)

class TestMediaPacker:
    """Test the media packing functionality."""
    
    def setup_method(self):
        """Set up test environment."""
        # Create a temporary directory
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
        
        # Create some test archive files of different sizes
        self.archive1 = self.temp_path / "archive1.tar.gz"
        self.archive2 = self.temp_path / "archive2.tar.gz"
        self.archive3 = self.temp_path / "archive3.tar.gz"
        
        # Create files with different content sizes
        with open(self.archive1, "wb") as f:
            f.write(b"a" * 1000)
            
        with open(self.archive2, "wb") as f:
            f.write(b"b" * 2000)
            
        with open(self.archive3, "wb") as f:
            f.write(b"c" * 3000)
    
    def teardown_method(self):
        """Clean up test environment."""
        shutil.rmtree(self.temp_dir)
    
    def test_calculate_archives_size(self):
        """Test calculating the total size of archives."""
        archives = [self.archive1, self.archive2, self.archive3]
        total_size = calculate_archives_size(archives)
        
        # Total size should be 1000 + 2000 + 3000 = 6000
        assert total_size == 6000
    
    def test_calculate_archives_size_with_missing(self):
        """Test calculating size with some missing archives."""
        # Add a non-existent archive
        missing_archive = self.temp_path / "missing.tar.gz"
        archives = [self.archive1, missing_archive, self.archive3]
        
        total_size = calculate_archives_size(archives)
        
        # Total size should be 1000 + 3000 = 4000 (missing archive ignored)
        assert total_size == 4000
    
    def test_split_archives_for_media(self):
        """Test splitting archives into groups that fit media capacity."""
        archives = [self.archive1, self.archive2, self.archive3]
        
        # Split with capacity that fits all (10000 > 6000)
        groups1 = split_archives_for_media(archives, 10000)
        assert len(groups1) == 1
        assert len(groups1[0]) == 3
        
        # Split with capacity that fits two archives (3500 > 3000)
        groups2 = split_archives_for_media(archives, 3500)
        assert len(groups2) == 2
        
        # Split with capacity that fits one archive per group
        groups3 = split_archives_for_media(archives, 2500)
        assert len(groups3) == 3
        
        # Verify sorting by size (larger archives first)
        assert self.archive3 in groups3[0]  # Largest archive (3000 bytes) in first group
        assert self.archive2 in groups3[1]  # Second largest (2000 bytes) in second group
        assert self.archive1 in groups3[2]  # Smallest (1000 bytes) in third group
    
    @patch('pycdlib.PyCdlib')
    def test_create_iso_image(self, mock_pycdlib):
        """Test creating an ISO image."""
        # Set up mock
        mock_iso = MagicMock()
        mock_pycdlib.return_value = mock_iso
        
        archives = [self.archive1, self.archive2]
        output_path = self.temp_path / "test_output"
        
        # Call the function
        iso_path = create_iso_image(archives, output_path)
        
        # Verify the result
        # We expect output_path with .iso extension
        assert iso_path == output_path.with_suffix('.iso')
        
        # Verify PyCdlib was used correctly - updated to match actual implementation
        mock_iso.new.assert_called_once_with(udf="2.60", interchange_level=4, joliet=3)
        assert mock_iso.add_file.call_count == 2  # Once for each archive
        expected_iso_path = output_path.with_suffix('.iso')
        mock_iso.write.assert_called_once_with(str(expected_iso_path))
        mock_iso.close.assert_called_once()
    
    @patch('historify.media_packer.create_iso_image')
    def test_pack_for_bd_r_single_disc(self, mock_create_iso):
        """Test packing archives for BD-R when all fit on one disc."""
        # Set up mock
        mock_create_iso.return_value = Path("/tmp/test.iso")
        
        # Set a small total size for testing
        with patch('historify.media_packer.calculate_archives_size') as mock_calc_size:
            mock_calc_size.return_value = 1000  # Much smaller than BD-R capacity
            
            archives = [self.archive1, self.archive2]
            output_base_path = self.temp_path / "output.tar.gz"
            
            # Call the function
            result = pack_for_bd_r(archives, output_base_path)
            
            # Verify the result
            assert len(result) == 1  # One ISO created
            mock_create_iso.assert_called_once_with(archives, output_base_path)
    
    @patch('historify.media_packer.create_iso_image')
    def test_pack_for_bd_r_multiple_discs(self, mock_create_iso):
        """Test packing archives for BD-R when they need multiple discs."""
        # Set up mock
        mock_create_iso.side_effect = [
            Path("/tmp/test-disc1.iso"),
            Path("/tmp/test-disc2.iso")
        ]
        
        # Set a large total size for testing
        with patch('historify.media_packer.calculate_archives_size') as mock_calc_size:
            mock_calc_size.return_value = BD_R_SINGLE_LAYER_CAPACITY * 1.5  # Larger than one BD-R
            
            # Also patch split_archives_for_media
            with patch('historify.media_packer.split_archives_for_media') as mock_split:
                mock_split.return_value = [
                    [self.archive1],  # First disc
                    [self.archive2, self.archive3]  # Second disc
                ]
                
                archives = [self.archive1, self.archive2, self.archive3]
                output_base_path = self.temp_path / "output.tar.gz"
                
                # Call the function
                result = pack_for_bd_r(archives, output_base_path)
                
                # Verify the result
                assert len(result) == 2  # Two ISOs created
                
                # Verify create_iso_image was called twice with correct paths
                assert mock_create_iso.call_count == 2
                
                # First call should use the first group
                args1, _ = mock_create_iso.call_args_list[0]
                assert args1[0] == [self.archive1]
                assert "disc1" in str(args1[1])
                
                # Second call should use the second group
                args2, _ = mock_create_iso.call_args_list[1]
                assert args2[0] == [self.archive2, self.archive3]
                assert "disc2" in str(args2[1])
    
    @patch('historify.media_packer.pack_for_bd_r')
    def test_pack_archives_for_media_bd_r(self, mock_pack_bd_r):
        """Test packing archives with bd-r media type."""
        # Set up mock
        mock_pack_bd_r.return_value = [Path("/tmp/test.iso")]
        
        archives = [self.archive1, self.archive2]
        output_base_path = self.temp_path / "output.tar.gz"
        
        # Call with bd-r media type
        result = pack_archives_for_media(archives, output_base_path, media_type="bd-r")
        
        # Verify the result
        assert len(result) == 1  # One ISO path returned
        mock_pack_bd_r.assert_called_once_with(archives, output_base_path)
    
    def test_pack_archives_for_media_unsupported(self):
        """Test packing archives with unsupported media type."""
        archives = [self.archive1, self.archive2]
        output_base_path = self.temp_path / "output.tar.gz"
        
        # Call with unsupported media type
        with pytest.raises(MediaPackError, match="Unsupported media type"):
            pack_archives_for_media(archives, output_base_path, media_type="dvd")
    
    def test_pack_archives_for_media_no_archives(self):
        """Test packing with no archives."""
        output_base_path = self.temp_path / "output.tar.gz"
        
        # Call with empty archives list
        with pytest.raises(MediaPackError, match="No archives to pack"):
            pack_archives_for_media([], output_base_path)
    
    def test_pack_archives_for_media_missing_archives(self):
        """Test packing with missing archives."""
        # Include a missing archive
        missing_archive = self.temp_path / "missing.tar.gz"
        archives = [self.archive1, missing_archive]
        output_base_path = self.temp_path / "output.tar.gz"
        
        # Call with list including missing archive
        with pytest.raises(MediaPackError, match="Archives not found"):
            pack_archives_for_media(archives, output_base_path)
