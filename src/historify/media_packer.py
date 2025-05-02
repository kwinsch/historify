# src/historify/media_packer.py
"""
Media packing functionality for historify snapshot archives.

This module provides functions to pack archives into ISO images for optical media.
"""
import os
import logging
import tempfile
import shutil
from pathlib import Path
from typing import List, Optional, Tuple
from datetime import datetime
import pycdlib

from historify.config import RepositoryConfig

logger = logging.getLogger(__name__)

class MediaPackError(Exception):
    """Exception raised for media packing errors."""
    pass

# BD-R single layer capacity in bytes (25GB)
BD_R_SINGLE_LAYER_CAPACITY = 25 * 1024 * 1024 * 1024

def calculate_archives_size(archives: List[Path]) -> int:
    """
    Calculate the total size of all archives.
    
    Args:
        archives: List of archive paths.
        
    Returns:
        Total size in bytes.
    """
    return sum(archive.stat().st_size for archive in archives if archive.exists())

def create_iso_image(archives: List[Path], output_path: Path, repo_path: Optional[str] = None) -> Path:
    """
    Create an ISO image containing the archives.
    
    Args:
        archives: List of archives to include in the ISO.
        output_path: Base path for the output ISO file.
        repo_path: Optional repository path to get configuration from.
        
    Returns:
        Path to the created ISO file.
        
    Raises:
        MediaPackError: If creating the ISO fails.
    """
    try:
        # The output_path is now the base filename without extension
        # Add .iso extension to create the ISO path
        iso_path = output_path.with_suffix('.iso')
        
        # Get a basic name from output_path for volume identification
        vol_basename = output_path.stem
        
        # Get the current date for metadata
        date_str = datetime.now().strftime('%Y-%m-%d')
        
        # ISO9660 volume identifiers are limited to 32 characters
        # Try to fit both basename and date if possible
        vol_ident = vol_basename
        if len(vol_ident) > 26:  # Leave room for date and separator
            vol_ident = vol_ident[:26]
        vol_ident = f"{vol_ident}_{date_str}"
        if len(vol_ident) > 32:  # Final safety check
            vol_ident = vol_ident[:32]
        
        # Get publisher from config if available
        publisher = "historify archive"
        if repo_path:
            try:
                config = RepositoryConfig(repo_path)
                pub = config.get("iso.publisher")
                if pub:
                    publisher = pub
            except Exception as e:
                logger.warning(f"Could not get publisher from config: {e}")
        
        # Create a new ISO with UDF 2.60 (explicitly setting UDF version)
        iso = pycdlib.PyCdlib()
        
        # Initialize with UDF 2.60 and add proper metadata
        iso.new(
            udf="2.60",                      # UDF 2.60 for BD-R compatibility
            interchange_level=4,             # Most permissive level for filenames
            joliet=3,                        # Joliet level 3 for extended filename support
            sys_ident="historify",           # System identifier (lowercase)
            vol_ident=vol_ident,             # Volume identifier with basename and date
            pub_ident_str=publisher,         # Publisher identifier from config or default
            preparer_ident_str=f"historify {date_str}", # Preparer with date
            app_ident_str="https://github.com/kwinsch/historify" # GitHub URL
        )
        
        # Create a temporary directory for staging
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir_path = Path(temp_dir)
            
            # Copy all archives to the temporary directory
            for archive in archives:
                if archive.exists():
                    shutil.copy2(archive, temp_dir_path / archive.name)
                    
                    # Add file to ISO using UDF path (avoid ISO9660 restrictions)
                    iso.add_file(
                        str(temp_dir_path / archive.name),
                        f"/{archive.name}",
                        udf_path=f"/{archive.name}"
                    )
            
            # Write the ISO
            iso.write(str(iso_path))
            iso.close()
            
        logger.info(f"Created ISO image at {iso_path}")
        return iso_path
        
    except Exception as e:
        logger.error(f"Error creating ISO image: {e}")
        raise MediaPackError(f"Failed to create ISO image: {e}")

def split_archives_for_media(archives: List[Path], media_capacity: int) -> List[List[Path]]:
    """
    Split archives into groups that fit within the media capacity.
    
    Args:
        archives: List of archive paths.
        media_capacity: Capacity of the media in bytes.
        
    Returns:
        List of archive groups that fit within the capacity.
    """
    archive_groups = []
    current_group = []
    current_size = 0
    
    # Sort archives by size (largest first) for better packing
    sorted_archives = sorted(archives, key=lambda a: a.stat().st_size if a.exists() else 0, reverse=True)
    
    for archive in sorted_archives:
        if not archive.exists():
            continue
            
        archive_size = archive.stat().st_size
        
        # If adding this archive would exceed capacity, start a new group
        if current_size + archive_size > media_capacity and current_group:
            archive_groups.append(current_group)
            current_group = []
            current_size = 0
        
        # Add archive to current group
        current_group.append(archive)
        current_size += archive_size
    
    # Add the last group if not empty
    if current_group:
        archive_groups.append(current_group)
    
    return archive_groups

def pack_for_bd_r(archives: List[Path], output_base_path: Path, repo_path: Optional[str] = None) -> List[Path]:
    """
    Pack archives for BD-R media.
    
    Args:
        archives: List of archives to pack.
        output_base_path: Base path for output ISO files.
        repo_path: Optional repository path to get configuration from.
        
    Returns:
        List of paths to created ISO files.
        
    Raises:
        MediaPackError: If packing fails.
    """
    total_size = calculate_archives_size(archives)
    logger.info(f"Total archives size: {total_size / (1024 * 1024 * 1024):.2f} GB")
    
    # Check if all archives fit on a single BD-R
    if total_size <= BD_R_SINGLE_LAYER_CAPACITY:
        # Create a single ISO
        iso_path = create_iso_image(archives, output_base_path, repo_path)
        return [iso_path]
    else:
        # Split archives into groups that fit on BD-R
        archive_groups = split_archives_for_media(archives, BD_R_SINGLE_LAYER_CAPACITY)
        logger.info(f"Archives need to be split into {len(archive_groups)} BD-R discs")
        
        # Create an ISO for each group
        iso_paths = []
        for i, group in enumerate(archive_groups, 1):
            # Create path with appropriate disc numbering
            # The output_base_path is now just the base filename without extension
            group_output = output_base_path.parent / f"{output_base_path.name}-disc{i}"
            iso_path = create_iso_image(group, group_output, repo_path)
            iso_paths.append(iso_path)
            
        return iso_paths

def pack_archives_for_media(
    archives: List[Path], output_base_path: Path, media_type: str = "bd-r", repo_path: Optional[str] = None
) -> List[Path]:
    """
    Pack archives for the specified media type.
    
    Args:
        archives: List of archives to pack.
        output_base_path: Base path for output media files.
        media_type: Type of media to pack for (default: "bd-r").
        repo_path: Optional repository path to get configuration from.
        
    Returns:
        List of paths to created media files.
        
    Raises:
        MediaPackError: If packing fails or media type is not supported.
    """
    if not archives:
        raise MediaPackError("No archives to pack")
    
    # Check if all archives exist
    missing_archives = [a for a in archives if not a.exists()]
    if missing_archives:
        missing_paths = ", ".join(str(a) for a in missing_archives)
        raise MediaPackError(f"Archives not found: {missing_paths}")
    
    # Handle different media types
    if media_type.lower() == "bd-r":
        return pack_for_bd_r(archives, output_base_path, repo_path)
    else:
        raise MediaPackError(f"Unsupported media type: {media_type}")