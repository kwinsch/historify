import configparser
import os
from pathlib import Path

class ConfigError(Exception):
    """Custom exception for configuration errors."""
    pass

class HistorifyConfig:
    """Manage historify configuration."""

    def __init__(self, repo_name: str = None, repo_path: str = None):
        self.repo_name = repo_name
        self.repo_path = repo_path
        self.global_config = configparser.ConfigParser()
        self.local_config = configparser.ConfigParser()
        self.global_config.read(os.path.expanduser("~/.historify/config"))
        if repo_path:
            self.local_config.read(os.path.join(repo_path, ".historify/config"))

    def set(self, option: str, value: str, section: str, scope: str = "local"):
        """
        Set a configuration option.

        Args:
            option: Configuration option name.
            value: Value to set.
            section: Configuration section (e.g., 'repo.<name>').
            scope: 'global' or 'local'.

        Raises:
            ConfigError: If scope is invalid or write fails.
        """
        if scope not in ["global", "local"]:
            raise ConfigError(f"Invalid scope: {scope}")

        config = self.global_config if scope == "global" else self.local_config
        if section not in config:
            config[section] = {}
        config[section][option] = value

        try:
            if scope == "global":
                os.makedirs(os.path.expanduser("~/.historify"), exist_ok=True)
                with open(os.path.expanduser("~/.historify/config"), "w") as f:
                    self.global_config.write(f)
            else:
                if not self.repo_path:
                    raise ConfigError("Repository path required for local config")
                os.makedirs(os.path.join(self.repo_path, ".historify"), exist_ok=True)
                with open(os.path.join(self.repo_path, ".historify/config"), "w") as f:
                    self.local_config.write(f)
        except OSError as e:
            raise ConfigError(f"Failed to write config: {e}")

    def get(self, option: str, section: str, default: str = None) -> str:
        """
        Get a configuration option.

        Args:
            option: Configuration option name.
            section: Configuration section (e.g., 'repo.<name>').
            default: Default value if option or section is missing.

        Returns:
            The option value or default if not found.

        Raises:
            ConfigError: If neither local nor global config contains the option and no default is provided.
        """
        if self.local_config.has_option(section, option):
            return self.local_config[section][option]
        if self.global_config.has_option(section, option):
            return self.global_config[section][option]
        if default is not None:
            return default
        raise ConfigError(f"Option {option} not found in section {section}")