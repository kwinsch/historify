import configparser
import os
from pathlib import Path
from typing import Optional

class ConfigError(Exception):
    """Custom exception for configuration errors."""
    pass

class HistorifyConfig:
    """Manage historify configuration across global, user, and local files."""
    
    def __init__(self, repo_path: Optional[str] = None):
        self.config = configparser.ConfigParser()
        self.global_config = Path("/etc/historify/historify.conf")
        self.user_config = Path.home() / ".historify.conf"
        self.local_config = Path(repo_path) / ".historify/config" if repo_path else None
        self.load_configs()

    def load_configs(self):
        """Load configuration files in order: global, user, local."""
        files = [self.global_config, self.user_config]
        if self.local_config:
            files.append(self.local_config)
        
        # Only read existing files
        existing_files = [f for f in files if f.exists()]
        if existing_files:
            self.config.read(existing_files)
        else:
            # Initialize default section if no config files exist
            self.config['DEFAULT'] = {}

    def get(self, key: str, section: str = 'DEFAULT') -> Optional[str]:
        """Get a configuration value."""
        try:
            return self.config.get(section, key)
        except (configparser.NoSectionError, configparser.NoOptionError):
            return None

    def set(self, key: str, value: str, section: str = 'DEFAULT', scope: str = 'local'):
        """
        Set a configuration value in the specified scope.

        Args:
            key: Configuration key (e.g., 'hash_algorithm').
            value: Configuration value (e.g., 'blake3').
            section: Config section (e.g., 'DEFAULT', 'repo.invoices').
            scope: Where to store ('global', 'user', 'local').
        """
        if scope == 'local' and not self.local_config:
            raise ConfigError("Local configuration requires a repository path")
        
        # Ensure section exists
        if section not in self.config:
            self.config[section] = {}
        
        # Set value in memory
        self.config[section][key] = value
        
        # Write to appropriate file based on scope
        config_file = {
            'global': self.global_config,
            'user': self.user_config,
            'local': self.local_config
        }.get(scope)
        
        if not config_file:
            raise ConfigError(f"Invalid scope: {scope}")
        
        # Ensure parent directory exists
        config_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Write configuration
        try:
            with config_file.open('w') as f:
                self.config.write(f)
        except PermissionError:
            raise ConfigError(f"Permission denied writing to {config_file}")
        except OSError as e:
            raise ConfigError(f"Failed to write configuration: {e}")

def get_default_repo() -> Optional[str]:
    """
    Get the default repository name if only one exists.
    Placeholder: Implement repository discovery later.
    """
    return None  # Return None until repositories are implemented

