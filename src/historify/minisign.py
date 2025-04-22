"""
Minisign module for historify providing digital signature functionality.
"""
import subprocess
import logging
import pexpect
from pathlib import Path
from typing import Union, Optional, Tuple

# Configure logging
logger = logging.getLogger(__name__)

class MinisignError(Exception):
    """Custom exception for minisign-related errors."""
    pass

def minisign_sign(
    file_path: Union[str, Path], 
    key_path: Union[str, Path], 
    password: Optional[str] = None,
    unencrypted: bool = False,
    tool_path: str = "minisign",
    timeout: int = 10
) -> bool:
    """
    Sign a file using minisign.
    
    Args:
        file_path: Path to the file to sign.
        key_path: Path to the minisign private key.
        password: Optional password for encrypted keys.
        unencrypted: Whether the key is unencrypted (use -W flag).
        tool_path: Path to the minisign binary (default: "minisign").
        timeout: Timeout for password prompt in seconds.
        
    Returns:
        True if signing succeeded, False otherwise.
        
    Raises:
        MinisignError: If signing fails or files don't exist.
    """
    file_path = Path(file_path)
    key_path = Path(key_path)
    
    if not file_path.is_file():
        raise MinisignError(f"File does not exist: {file_path}")
    if not key_path.is_file():
        raise MinisignError(f"Private key file does not exist: {key_path}")
    
    # Build the command
    cmd = [tool_path, "-Sm", str(file_path), "-s", str(key_path)]
    
    if unencrypted:
        cmd.append("-W")
    
    cmd_str = " ".join(cmd)
    logger.debug(f"Executing minisign command: {cmd_str}")
    
    # If we have a password and the key is not marked as unencrypted,
    # use pexpect for interactive mode
    if password is not None and not unencrypted:
        try:
            child = pexpect.spawn(cmd_str, encoding='utf-8')
            # Wait for password prompt
            index = child.expect(['Password:', pexpect.EOF, pexpect.TIMEOUT], timeout=timeout)
            
            if index == 0:  # Password prompt found
                child.sendline(password)
                # Look for successful completion message
                child.expect(['done', pexpect.EOF, pexpect.TIMEOUT], timeout=timeout)
                child.expect(pexpect.EOF, timeout=timeout)
                child.close()
                
                if child.exitstatus == 0:
                    logger.info(f"Successfully signed {file_path}")
                    return True
                else:
                    logger.error(f"Signing failed with exit code {child.exitstatus}")
                    return False
            
            elif index == 1:  # EOF before password prompt
                child.close()
                if child.exitstatus == 0:
                    logger.info(f"Successfully signed {file_path} (no password required)")
                    return True
                else:
                    logger.error(f"Signing failed with exit code {child.exitstatus}")
                    return False
            
            else:  # Timeout
                child.close(force=True)
                logger.error("Signing timed out while waiting for password prompt")
                return False
                
        except pexpect.ExceptionPexpect as e:
            logger.error(f"Pexpect error: {e}")
            return False
    
    # For unencrypted keys or when no password is provided, use subprocess
    else:
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            logger.info(f"Successfully signed {file_path}")
            return True
        except FileNotFoundError:
            logger.error(f"Minisign tool not found: {tool_path}")
            raise MinisignError(f"Minisign tool not found: {tool_path}")
        except subprocess.CalledProcessError as e:
            logger.error(f"Signing failed: {e.stderr}")
            return False

def minisign_verify(
    file_path: Union[str, Path], 
    pubkey_path: Union[str, Path], 
    tool_path: str = "minisign",
    quiet: bool = False
) -> Tuple[bool, str]:
    """
    Verify a minisign signature.

    Args:
        file_path: Path to the signed file.
        pubkey_path: Path to the minisign public key.
        tool_path: Path to the minisign binary (default: "minisign").
        quiet: Whether to use the quiet flag (-q).

    Returns:
        Tuple of (success: bool, message: str)

    Raises:
        MinisignError: If the tool fails, file/key doesn't exist.
    """
    file_path = Path(file_path)
    pubkey_path = Path(pubkey_path)
    sig_path = Path(f"{file_path}.minisig")
    
    if not file_path.is_file():
        raise MinisignError(f"File does not exist: {file_path}")
    if not pubkey_path.is_file():
        raise MinisignError(f"Public key file does not exist: {pubkey_path}")
    if not sig_path.is_file():
        raise MinisignError(f"Signature file does not exist: {sig_path}")

    # Build the command
    cmd = [tool_path, "-Vm", str(file_path), "-p", str(pubkey_path)]
    
    if quiet:
        cmd.append("-q")
    
    logger.debug(f"Executing minisign verification command: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode == 0:
            logger.info(f"Successfully verified signature for {file_path}")
            return True, result.stdout.strip()
        else:
            logger.error(f"Verification failed: {result.stderr}")
            return False, result.stderr.strip()
    except FileNotFoundError:
        logger.error(f"Minisign tool not found: {tool_path}")
        raise MinisignError(f"Minisign tool not found: {tool_path}")
    except subprocess.SubprocessError as e:
        logger.error(f"Subprocess error during verification: {e}")
        return False, str(e)
