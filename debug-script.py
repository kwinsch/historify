#!/usr/bin/env python
"""
Debug script for investigating the hash chain issue in historify.

Usage:
  python debug_historify.py /path/to/repository
"""

import os
import sys
import csv
from pathlib import Path
import logging
from historify.hash import hash_file
from historify.config import RepositoryConfig
from historify.csv_manager import CSVManager
from historify.minisign import minisign_verify

# Configure logging
logging.basicConfig(level=logging.DEBUG, 
                   format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def debug_changelogs(repo_path):
    """
    Debug the changelogs in a repository to find hash chain issues.
    
    Args:
        repo_path: Path to the repository.
    """
    repo_path = Path(repo_path).resolve()
    logger.info(f"Analyzing repository at {repo_path}")
    
    # Get repository configuration
    try:
        config = RepositoryConfig(str(repo_path))
        changes_dir = repo_path / config.get("changes.directory", "changes")
        csv_manager = CSVManager(str(repo_path))
        
        minisign_pub = config.get("minisign.pub", None)
        if minisign_pub:
            logger.info(f"Minisign public key: {minisign_pub}")
        
        # Get all changelog files sorted by date
        changelog_files = sorted(changes_dir.glob("changelog-*.csv"))
        
        if not changelog_files:
            logger.warning("No changelog files found in repository")
            return
        
        logger.info(f"Found {len(changelog_files)} changelog files")
        
        # Analyze the seed file first
        seed_file = repo_path / "db" / "seed.bin"
        seed_sig_file = seed_file.with_suffix(".bin.minisig")
        
        if seed_file.exists():
            seed_hash = hash_file(seed_file)["blake3"]
            logger.info(f"Seed file: {seed_file}")
            logger.info(f"Seed hash (blake3): {seed_hash}")
            
            if seed_sig_file.exists():
                logger.info(f"Seed signature file exists: {seed_sig_file}")
                
                # Verify the signature if minisign_pub is available
                if minisign_pub:
                    try:
                        success, message = minisign_verify(seed_file, minisign_pub)
                        if success:
                            logger.info("Seed signature verification: SUCCESS")
                        else:
                            logger.error(f"Seed signature verification failed: {message}")
                    except Exception as e:
                        logger.error(f"Error verifying seed signature: {e}")
            else:
                logger.warning("Seed signature file missing")
        else:
            logger.error("Seed file missing")
            return
        
        # Process each changelog file
        previous_hash = seed_hash  # Start with seed hash
        previous_file = "db/seed.bin"
        
        for i, changelog_file in enumerate(changelog_files):
            logger.info(f"\nAnalyzing changelog {i+1}/{len(changelog_files)}: {changelog_file.name}")
            
            # Calculate the file's hash for verification
            current_hash = hash_file(changelog_file)["blake3"]
            logger.info(f"Current hash (blake3): {current_hash}")
            
            # Check for signature
            sig_file = changelog_file.with_suffix(".csv.minisig")
            if sig_file.exists():
                logger.info(f"Signature file exists: {sig_file}")
                
                # Verify the signature if minisign_pub is available
                if minisign_pub:
                    try:
                        success, message = minisign_verify(changelog_file, minisign_pub)
                        if success:
                            logger.info("Signature verification: SUCCESS")
                        else:
                            logger.error(f"Signature verification failed: {message}")
                    except Exception as e:
                        logger.error(f"Error verifying signature: {e}")
            else:
                logger.warning("No signature file (open changelog)")
            
            # Read the closing transaction to check the hash chain
            try:
                entries = csv_manager.read_entries(changelog_file)
                
                if not entries:
                    logger.error("Changelog file is empty")
                    continue
                
                # First entry should be a closing transaction
                first_entry = entries[0]
                if first_entry["transaction_type"] != "closing":
                    logger.error(f"First entry is not a closing transaction: {first_entry['transaction_type']}")
                    continue
                
                stored_previous_path = first_entry["path"]
                stored_previous_hash = first_entry["blake3"]
                
                logger.info(f"Closing transaction references: {stored_previous_path}")
                logger.info(f"Stored previous hash: {stored_previous_hash}")
                logger.info(f"Expected previous hash: {previous_hash}")
                
                if stored_previous_hash == previous_hash:
                    logger.info("Hash chain verification: SUCCESS")
                else:
                    logger.error("Hash chain verification: FAILED - Hashes don't match")
                    
                    # More detailed analysis of the mismatch
                    logger.info(f"Previous file referenced: {previous_file}")
                    logger.info(f"Previous file in transaction: {stored_previous_path}")
                    
                    # Check if the hash algorithm or calculation might be different
                    if previous_file == "db/seed.bin" and stored_previous_path == "db/seed.bin":
                        logger.info("Both reference the seed file, but hashes are different")
                    elif previous_file.startswith("changes/") and stored_previous_path.startswith("changes/"):
                        logger.info("Both reference changelog files, but hashes are different")
                    else:
                        logger.info("References to different files in the chain")
                
                # Other transactions for informational purposes
                logger.info(f"Total entries in file: {len(entries)}")
                
                # Summarize transaction types
                transaction_types = {}
                for entry in entries:
                    t_type = entry["transaction_type"]
                    transaction_types[t_type] = transaction_types.get(t_type, 0) + 1
                
                logger.info(f"Transaction types: {transaction_types}")
                
            except Exception as e:
                logger.error(f"Error reading changelog entries: {e}")
            
            # Update previous hash for next iteration
            previous_hash = current_hash
            previous_file = f"changes/{changelog_file.name}"
        
        logger.info("\nSummary:")
        logger.info(f"Repository: {repo_path}")
        logger.info(f"Changelogs analyzed: {len(changelog_files)}")
        
    except Exception as e:
        logger.error(f"Error analyzing repository: {e}")

def analyze_file_content(file_path):
    """
    Analyze the raw content of a file to identify potential issues.
    
    Args:
        file_path: Path to the file to analyze.
    """
    try:
        file_path = Path(file_path)
        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            return
        
        logger.info(f"\nDetailed analysis of: {file_path}")
        
        # Get file stats
        stats = file_path.stat()
        logger.info(f"File size: {stats.st_size} bytes")
        
        # Calculate hash without any transformations
        hash_values = hash_file(file_path)
        logger.info(f"Raw blake3 hash: {hash_values['blake3']}")
        logger.info(f"Raw sha256 hash: {hash_values['sha256']}")
        
        # Read file as text if it's likely a text file
        if file_path.suffix.lower() in ['.csv', '.txt', '.md']:
            with open(file_path, 'r', errors='replace') as f:
                content = f.read(1024)  # Read first 1KB
                
            logger.info(f"First 1KB of content (text mode):\n{content}")
            
            # If it's a CSV, analyze the structure
            if file_path.suffix.lower() == '.csv':
                with open(file_path, 'r', newline='') as f:
                    reader = csv.reader(f)
                    header = next(reader, None)
                    
                    if header:
                        logger.info(f"CSV header: {header}")
                        
                        # Read a few rows
                        rows = []
                        for i, row in enumerate(reader):
                            if i >= 5:  # Limit to first 5 rows
                                break
                            rows.append(row)
                        
                        logger.info(f"First {len(rows)} data rows:")
                        for row in rows:
                            logger.info(f"  {row}")
                    else:
                        logger.warning("CSV file has no header")
        else:
            # For binary files, just show a hex dump of the first 128 bytes
            with open(file_path, 'rb') as f:
                binary_content = f.read(128)
                
            hex_dump = ' '.join(f'{b:02x}' for b in binary_content)
            logger.info(f"First 128 bytes (hex): {hex_dump}")
    
    except Exception as e:
        logger.error(f"Error analyzing file content: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python debug_historify.py /path/to/repository [file_to_analyze]")
        sys.exit(1)
    
    repo_path = sys.argv[1]
    
    # Run the debug analysis
    debug_changelogs(repo_path)
    
    # If a specific file is provided, analyze it in detail
    if len(sys.argv) > 2:
        analyze_file_content(sys.argv[2])
