#!/usr/bin/env python
"""
Specialized script to analyze the verification logic in the historify codebase.

Usage:
  python analyze_verification.py /path/to/repository
"""

import os
import sys
import csv
import inspect
import logging
from pathlib import Path

# Import historify modules
from historify.hash import hash_file
from historify.config import RepositoryConfig
from historify.csv_manager import CSVManager
from historify.changelog import Changelog
from historify.cli_verify import (
    verify_repository_config,
    verify_signature,
    verify_changelog_hash_chain,
    verify_full_chain,
    verify_recent_logs,
    handle_verify_command
)

# Configure logging
logging.basicConfig(level=logging.DEBUG, 
                   format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def trace_function_calls(func, *args, **kwargs):
    """
    Trace a function call with arguments and return value for debugging.
    
    Args:
        func: The function to trace.
        *args: Positional arguments for the function.
        **kwargs: Keyword arguments for the function.
        
    Returns:
        The return value of the function.
    """
    arg_str = ", ".join([repr(a) for a in args] + [f"{k}={repr(v)}" for k, v in kwargs.items()])
    logger.debug(f"CALL: {func.__name__}({arg_str})")
    
    try:
        result = func(*args, **kwargs)
        logger.debug(f"RETURN: {func.__name__} -> {repr(result)}")
        return result
    except Exception as e:
        logger.debug(f"EXCEPTION: {func.__name__} -> {type(e).__name__}: {e}")
        raise

def analyze_verification_logic(repo_path):
    """
    Analyze the verification logic for a repository.
    
    Args:
        repo_path: Path to the repository.
    """
    repo_path = Path(repo_path).resolve()
    logger.info(f"Analyzing verification logic for repository at {repo_path}")
    
    # First, get the configuration and changelogs
    try:
        config = RepositoryConfig(str(repo_path))
        changelog = Changelog(str(repo_path))
        
        # Get all changelog files
        changes_dir = changelog.changes_dir
        changelog_files = sorted(changes_dir.glob("changelog-*.csv"))
        
        if not changelog_files:
            logger.warning("No changelog files found in repository")
            return
        
        logger.info(f"Found {len(changelog_files)} changelog files")
        
        # Get the seed file
        seed_file = repo_path / "db" / "seed.bin"
        seed_sig_file = seed_file.with_suffix(".bin.minisig")
        
        # Examine the function that verifies the hash chain
        logger.info("\nExamining verify_changelog_hash_chain function")
        logger.info(f"Function signature: {inspect.signature(verify_changelog_hash_chain)}")
        
        # Generate a hash for the seed file for comparison
        seed_hash = hash_file(seed_file)["blake3"]
        logger.info(f"Seed file hash (blake3): {seed_hash}")
        
        # Try to verify the hash chain in the first changelog
        first_changelog = changelog_files[0]
        
        # Manually check the first entry of the first changelog
        logger.info(f"\nManually checking first entry in {first_changelog}")
        with open(first_changelog, "r", newline="") as f:
            reader = csv.DictReader(f)
            try:
                first_row = next(reader)
                logger.info(f"First entry type: {first_row.get('transaction_type', 'unknown')}")
                logger.info(f"First entry path: {first_row.get('path', 'unknown')}")
                logger.info(f"First entry blake3: {first_row.get('blake3', 'unknown')}")
                
                # Compare with the seed hash
                if first_row.get("path") == "db/seed.bin":
                    if first_row.get("blake3") == seed_hash:
                        logger.info("First changelog correctly references seed hash")
                    else:
                        logger.error(f"First changelog has incorrect seed hash reference")
                        logger.error(f"  Expected: {seed_hash}")
                        logger.error(f"  Found: {first_row.get('blake3', 'unknown')}")
            except StopIteration:
                logger.error("Changelog is empty")
        
        # Check each changelog against its referenced previous file
        logger.info("\nVerifying hash chain manually")
        prev_file = seed_file
        prev_hash = seed_hash
        
        for i, changelog_file in enumerate(changelog_files):
            logger.info(f"\nChecking changelog {i+1}/{len(changelog_files)}: {changelog_file.name}")
            
            # Calculate this file's hash
            current_hash = hash_file(changelog_file)["blake3"]
            logger.info(f"Calculated hash: {current_hash}")
            
            # Check the first entry's reference
            with open(changelog_file, "r", newline="") as f:
                reader = csv.DictReader(f)
                try:
                    first_row = next(reader)
                    
                    if first_row["transaction_type"] != "closing":
                        logger.error(f"First entry is not a closing transaction: {first_row['transaction_type']}")
                        continue
                    
                    reference_path = first_row["path"]
                    reference_hash = first_row["blake3"]
                    
                    logger.info(f"References path: {reference_path}")
                    logger.info(f"References hash: {reference_hash}")
                    
                    # Determine expected hash based on reference path
                    expected_hash = None
                    if reference_path == "db/seed.bin":
                        expected_hash = seed_hash
                        logger.info(f"References seed file, expected hash: {expected_hash}")
                    elif reference_path.startswith("changes/"):
                        ref_file = repo_path / reference_path
                        if ref_file.exists():
                            expected_hash = hash_file(ref_file)["blake3"]
                            logger.info(f"References changelog {reference_path}, expected hash: {expected_hash}")
                        else:
                            logger.error(f"Referenced file does not exist: {reference_path}")
                    else:
                        logger.error(f"Unknown reference path: {reference_path}")
                    
                    # Compare hashes
                    if expected_hash:
                        if reference_hash == expected_hash:
                            logger.info("Hash reference is correct")
                        else:
                            logger.error("Hash reference is incorrect")
                            logger.error(f"  Expected: {expected_hash}")
                            logger.error(f"  Found: {reference_hash}")
                    
                except StopIteration:
                    logger.error("Changelog is empty")
            
            # Set for next iteration
            prev_file = changelog_file
            prev_hash = current_hash
        
        # Test the built-in verification functions
        logger.info("\nTesting built-in verification functions")
        
        # Test verify_repository_config
        logger.info("\nTesting verify_repository_config")
        issues = trace_function_calls(verify_repository_config, str(repo_path))
        if issues:
            logger.warning(f"Configuration issues found: {issues}")
        else:
            logger.info("Configuration verification passed")
        
        # Test verify_full_chain
        logger.info("\nTesting verify_full_chain")
        success, issues = trace_function_calls(verify_full_chain, str(repo_path))
        if not success:
            logger.error(f"Full chain verification failed: {issues}")
            
            # Analyze the issues in more detail
            for issue in issues:
                file_path = issue.get("file")
                issue_msg = issue.get("issue")
                
                logger.info(f"\nAnalyzing issue with {file_path}")
                logger.info(f"Issue message: {issue_msg}")
                
                # If it's a hash chain issue, extract the expected and actual hashes
                if "Hash chain broken" in issue_msg:
                    import re
                    match = re.search(r"expected ([0-9a-f]+), got ([0-9a-f]+)", issue_msg)
                    if match:
                        expected_hash = match.group(1)
                        actual_hash = match.group(2)
                        
                        logger.info(f"Expected hash: {expected_hash}")
                        logger.info(f"Actual hash: {actual_hash}")
                        
                        # Try to find the file that should have this hash
                        if Path(file_path).exists():
                            file_hash = hash_file(file_path)["blake3"]
                            logger.info(f"Current file hash: {file_hash}")
                            
                            # Check if the first entry mentions the source of expected hash
                            with open(file_path, "r", newline="") as f:
                                reader = csv.DictReader(f)
                                try:
                                    first_row = next(reader)
                                    ref_path = first_row.get("path", "unknown")
                                    ref_hash = first_row.get("blake3", "unknown")
                                    
                                    logger.info(f"File references path: {ref_path}")
                                    logger.info(f"File references hash: {ref_hash}")
                                    
                                    # Find the file that should have this hash
                                    if ref_path == "db/seed.bin":
                                        seed_actual_hash = hash_file(seed_file)["blake3"]
                                        logger.info(f"Actual seed hash: {seed_actual_hash}")
                                        
                                        if ref_hash != seed_actual_hash:
                                            logger.error("Seed hash in transaction doesn't match actual seed hash")
                                    elif ref_path.startswith("changes/"):
                                        ref_file = repo_path / ref_path
                                        if ref_file.exists():
                                            ref_actual_hash = hash_file(ref_file)["blake3"]
                                            logger.info(f"Actual referenced file hash: {ref_actual_hash}")
                                            
                                            if ref_hash != ref_actual_hash:
                                                logger.error("Referenced hash doesn't match actual file hash")
                                        else:
                                            logger.error(f"Referenced file does not exist: {ref_path}")
                                except StopIteration:
                                    logger.error("File is empty")
                    
        else:
            logger.info("Full chain verification passed")
            
    except Exception as e:
        logger.error(f"Error analyzing verification logic: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python analyze_verification.py /path/to/repository")
        sys.exit(1)
    
    repo_path = sys.argv[1]
    
    # Run the verification logic analysis
    analyze_verification_logic(repo_path)
