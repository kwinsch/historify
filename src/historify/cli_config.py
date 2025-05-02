"""
Implementation of config commands for historify.
"""
import logging
import click
from pathlib import Path
from historify.config import RepositoryConfig, ConfigError
from historify.key_manager import backup_public_key, KeyError

logger = logging.getLogger(__name__)

def set_config(repo_path: str, key: str, value: str) -> bool:
    """
    Set a configuration option in the repository.
    
    Args:
        repo_path: Path to the repository.
        key: Configuration key in format "section.option".
        value: Value to set.
        
    Returns:
        True if the value was set successfully.
        
    Raises:
        ConfigError: If the key format is invalid or setting fails.
    """
    try:
        config = RepositoryConfig(repo_path)
        
        # Backup public key if this is setting minisign.pub
        if key == "minisign.pub":
            try:
                # Ensure the db/keys directory exists
                keys_dir = Path(repo_path) / "db" / "keys"
                keys_dir.mkdir(parents=True, exist_ok=True)
                
                backup_public_key(repo_path, value)
            except KeyError as e:
                logger.warning(f"Failed to backup public key: {e}")
                # Continue anyway, as this is not critical
        
        return config.set(key, value)
    except ConfigError as e:
        logger.error(f"Configuration error: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise ConfigError(f"Unexpected error: {e}")

def check_config(repo_path: str) -> bool:
    """
    Check the repository configuration for issues.
    
    Args:
        repo_path: Path to the repository.
        
    Returns:
        True if no issues were found.
        
    Raises:
        ConfigError: If the repository is not valid.
    """
    try:
        config = RepositoryConfig(repo_path)
        issues = config.check()
        
        if not issues:
            logger.info(f"Configuration check passed with no issues")
            return True
        else:
            for key, issue in issues:
                logger.warning(f"Configuration issue: {key} - {issue}")
            return False
    except ConfigError as e:
        logger.error(f"Configuration error: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise ConfigError(f"Unexpected error: {e}")

def list_config(repo_path: str) -> dict:
    """
    List all configuration values.
    
    Args:
        repo_path: Path to the repository.
        
    Returns:
        Dictionary of key-value pairs.
        
    Raises:
        ConfigError: If the repository is not valid.
    """
    try:
        config = RepositoryConfig(repo_path)
        return config.list_all()
    except ConfigError as e:
        logger.error(f"Configuration error: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise ConfigError(f"Unexpected error: {e}")

def handle_config_command(repo_path: str, key: str, value: str) -> None:
    """
    Handle the config command from the CLI.
    
    Args:
        repo_path: Path to the repository.
        key: Configuration key in format "section.option".
        value: Value to set.
    """
    try:
        repo_path = Path(repo_path).resolve()
        
        click.echo(f"Setting {key} = {value} in {repo_path}")
        
        if set_config(str(repo_path), key, value):
            click.echo(f"Configuration updated successfully")
        else:
            click.echo(f"Failed to update configuration")
            
    except ConfigError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()

def handle_check_config_command(repo_path: str) -> None:
    """
    Handle the check-config command from the CLI.
    
    Args:
        repo_path: Path to the repository.
    """
    try:
        repo_path = Path(repo_path).resolve()
        
        click.echo(f"Checking configuration in {repo_path}")
        
        issues = []
        try:
            config = RepositoryConfig(str(repo_path))
            issues = config.check()
        except ConfigError as e:
            click.echo(f"Error: {e}", err=True)
            raise click.Abort()
        
        if not issues:
            click.echo("Configuration check passed with no issues")
        else:
            click.echo("Configuration issues found:")
            for key, issue in issues:
                click.echo(f"  - {key}: {issue}")
            
    except ConfigError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()