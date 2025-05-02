"""
Configuration module for historify that handles repository settings.
"""
import os
import logging
import csv
import configparser
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

logger = logging.getLogger(__name__)

class ConfigError(Exception):
    """Exception raised for configuration-related errors."""
    pass

class RepositoryConfig:
    """Manages historify repository configuration."""
    
    def __init__(self, repo_path: str):
        """
        Initialize a RepositoryConfig object.
        
        Args:
            repo_path: Path to the repository.
            
        Raises:
            ConfigError: If the repository is not properly initialized.
        """
        self.repo_path = Path(repo_path).resolve()
        self.db_dir = self.repo_path / "db"
        self.config_file = self.db_dir / "config"
        self.config_csv = self.db_dir / "config.csv"
        
        # Check if this is a valid repository
        if not self._is_valid_repository():
            raise ConfigError(f"Not a valid historify repository: {self.repo_path}")
        
        # Load configuration
        self.config = configparser.ConfigParser()
        if self.config_file.exists():
            self.config.read(self.config_file)
        
        # Ensure config.csv exists
        if not self.config_csv.exists():
            self._initialize_config_csv()
    
    def _is_valid_repository(self) -> bool:
        """
        Check if the path is a valid historify repository.
        
        Returns:
            True if this is a valid repository.
        """
        return (
            self.db_dir.exists() and
            self.config_file.exists()
        )
    
    def _initialize_config_csv(self) -> None:
        """
        Initialize the config.csv file with header.
        
        Raises:
            ConfigError: If initialization fails.
        """
        try:
            with open(self.config_csv, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=["key", "value"])
                writer.writeheader()
                
                # Write existing config from INI file
                for section in self.config.sections():
                    for option in self.config[section]:
                        key = f"{section}.{option}"
                        value = self.config[section][option]
                        writer.writerow({"key": key, "value": value})
                        
        except Exception as e:
            logger.error(f"Failed to initialize config.csv: {e}")
            raise ConfigError(f"Failed to initialize config.csv: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value.
        
        Args:
            key: Configuration key in format "section.option".
            default: Default value to return if key is not found.
            
        Returns:
            The configuration value or default.
            
        Raises:
            ConfigError: If the key format is invalid.
        """
        parts = key.split(".", 1)
        if len(parts) != 2:
            raise ConfigError(f"Invalid key format: {key}. Use 'section.option' format.")
        
        section, option = parts
        
        # First try from INI file
        if section in self.config and option in self.config[section]:
            return self.config[section][option]
        
        # Then try from CSV file
        try:
            if self.config_csv.exists():
                with open(self.config_csv, "r", newline="") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if row["key"] == key:
                            return row["value"]
        except Exception as e:
            logger.error(f"Error reading config.csv: {e}")
        
        return default
    
    def set(self, key: str, value: str) -> bool:
        """
        Set a configuration value.
        
        Args:
            key: Configuration key in format "section.option".
            value: Value to set.
            
        Returns:
            True if the value was set successfully.
            
        Raises:
            ConfigError: If the key format is invalid or setting fails.
        """
        parts = key.split(".", 1)
        if len(parts) != 2:
            raise ConfigError(f"Invalid key format: {key}. Use 'section.option' format.")
        
        section, option = parts
        
        # Handle special case for minisign.pub - create keys directory
        if key == "minisign.pub":
            try:
                # Ensure the db/keys directory exists
                keys_dir = self.repo_path / "db" / "keys"
                keys_dir.mkdir(parents=True, exist_ok=True)
                
                # Attempt to backup the key, but allow failure without stopping
                try:
                    from historify.key_manager import backup_public_key
                    backup_public_key(str(self.repo_path), value)
                except Exception as e:
                    logger.warning(f"Failed to backup public key during config set: {e}")
                    # Continue anyway, as this is not critical
            except Exception as e:
                logger.warning(f"Failed to create keys directory: {e}")
                # Continue anyway, setting the config is still useful
        
        # Update INI file
        if section not in self.config:
            self.config[section] = {}
        
        self.config[section][option] = value
        
        try:
            with open(self.config_file, "w") as f:
                self.config.write(f)
        except OSError as e:
            raise ConfigError(f"Failed to write config file: {e}")
        
        # Update CSV file
        try:
            # Read existing entries
            entries = []
            
            if self.config_csv.exists():
                with open(self.config_csv, "r", newline="") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if row["key"] != key:
                            entries.append(row)
            
            # Add new entry
            entries.append({"key": key, "value": value})
            
            # Write updated entries
            with open(self.config_csv, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=["key", "value"])
                writer.writeheader()
                writer.writerows(entries)
            
            logger.info(f"Set configuration {key} = {value}")
            return True
            
        except Exception as e:
            raise ConfigError(f"Failed to update config.csv: {e}")
    
    def check(self) -> List[Tuple[str, str]]:
        """
        Check the configuration for issues.
        
        Returns:
            List of (key, issue) tuples for any configuration issues found.
        """
        issues = []
        
        # Required configurations to check
        required_configs = {
            "repository.name": "Repository name is not set",
            "hash.algorithms": "Hash algorithms not configured (should include at least blake3)"
        }
        
        # Check required configurations - test both storage locations
        for key, issue in required_configs.items():
            # Split the key into section and option
            parts = key.split(".", 1)
            if len(parts) != 2:
                continue
                
            section, option = parts
            
            # Check if it exists in the INI file
            ini_exists = section in self.config and option in self.config[section]
            
            # Check if it exists in the CSV file
            csv_exists = False
            try:
                if self.config_csv.exists():
                    with open(self.config_csv, "r", newline="") as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            if row["key"] == key:
                                csv_exists = True
                                break
            except Exception:
                csv_exists = False
            
            # If missing from both locations, it's an issue
            if not ini_exists and not csv_exists:
                issues.append((key, issue))
        
        # Check hash algorithms
        hash_algorithms = self.get("hash.algorithms", "")
        if hash_algorithms and "blake3" not in hash_algorithms.lower().split(","):
            issues.append(("hash.algorithms", "blake3 must be included in hash algorithms"))
        
        # Check minisign key if specified
        minisign_key = self.get("minisign.key")
        minisign_pub = self.get("minisign.pub")
        
        if minisign_key and not Path(minisign_key).exists():
            issues.append(("minisign.key", f"Minisign key file not found: {minisign_key}"))
        
        if minisign_pub and not Path(minisign_pub).exists():
            issues.append(("minisign.pub", f"Minisign public key file not found: {minisign_pub}"))
        
        if (minisign_key and not minisign_pub) or (minisign_pub and not minisign_key):
            issues.append(("minisign", "Both minisign.key and minisign.pub must be set"))
        
        return issues

    def list_all(self) -> Dict[str, str]:
        """
        List all configuration values.
        
        Returns:
            Dictionary of key-value pairs.
        """
        config_values = {}
        
        # Get values from INI file
        for section in self.config.sections():
            for option in self.config[section]:
                key = f"{section}.{option}"
                config_values[key] = self.config[section][option]
        
        # Get values from CSV file
        try:
            if self.config_csv.exists():
                with open(self.config_csv, "r", newline="") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if row["key"] not in config_values:  # Prefer INI file values
                            config_values[row["key"]] = row["value"]
        except Exception as e:
            logger.error(f"Error reading config.csv: {e}")
        
        return config_values