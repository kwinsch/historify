"""
Tests for the add-category command implementation.
"""
import pytest
import os
import csv
import shutil
import click
from pathlib import Path
from click.testing import CliRunner
from unittest.mock import patch, MagicMock

from historify.cli import add_category
from historify.cli_category import handle_add_category_command, CategoryError
from historify.config import RepositoryConfig
from historify.cli_init import init_repository

class TestCategoryImplementation:
    """Test the category command implementation."""
    
    def setup_method(self):
        """Set up test environment."""
        self.runner = CliRunner()
        self.test_repo_path = Path("test_repo_category").absolute()
        
        # Initialize a test repository
        if not self.test_repo_path.exists():
            init_repository(str(self.test_repo_path), "test-repo")
        
        # Create a changelog file
        self.changes_dir = self.test_repo_path / "changes"
        self.changes_dir.mkdir(exist_ok=True)
        self.test_changelog = self.changes_dir / "changelog-2025-04-22.csv"
        
        # Create a header row for the CSV
        with open(self.test_changelog, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "timestamp", "transaction_type", "path", "category", 
                "size", "ctime", "mtime", "sha256", "blake3"
            ])
    
    def teardown_method(self):
        """Clean up test environment."""
        if self.test_repo_path.exists():
            shutil.rmtree(self.test_repo_path)
    
    def test_add_category_internal(self):
        """Test adding an internal category."""
        # Call the handler directly
        internal_path = "docs"
        handle_add_category_command(str(self.test_repo_path), "documents", internal_path)
        
        # Verify category was added to config
        config = RepositoryConfig(str(self.test_repo_path))
        category_path = config.get("category.documents.path")
        assert category_path == internal_path
        
        # Verify directory was created
        category_dir = self.test_repo_path / internal_path
        assert category_dir.exists()
        assert category_dir.is_dir()
        
        # Verify changelog entry was added
        with open(self.test_changelog, "r", newline="") as f:
            reader = csv.DictReader(f)
            entries = list(reader)
            
            # Should have at least two entries (path and description)
            assert len(entries) >= 2
            
            # Check the path entry
            path_entry = next((e for e in entries if e["path"] == "category.documents.path"), None)
            assert path_entry is not None
            assert path_entry["transaction_type"] == "config"
            assert path_entry["category"] == "documents"
            assert path_entry["blake3"] == internal_path
    
    def test_add_category_external(self):
        """Test adding an external category with absolute path."""
        # Call the handler directly
        with self.runner.isolated_filesystem():
            # Create an external dir
            external_dir = Path(os.getcwd()) / "external_data"
            external_dir.mkdir(parents=True)
            
            # Add category with external path
            handle_add_category_command(str(self.test_repo_path), "external", str(external_dir))
            
            # Verify category was added to config
            config = RepositoryConfig(str(self.test_repo_path))
            category_path = config.get("category.external.path")
            assert category_path == str(external_dir)
            
            # Verify external directory exists
            assert external_dir.exists()
            assert external_dir.is_dir()
            
            # Clean up external dir
            shutil.rmtree(external_dir)
    
    def test_add_duplicate_category(self):
        """Test adding a category that already exists."""
        # Add a category first
        handle_add_category_command(str(self.test_repo_path), "documents", "docs")
        
        # Try adding it again (should fail)
        with pytest.raises(click.Abort):
            handle_add_category_command(str(self.test_repo_path), "documents", "other/path")
    
    def test_add_invalid_category_name(self):
        """Test adding a category with invalid name."""
        # Try with a name containing dots
        with pytest.raises(click.Abort):
            handle_add_category_command(str(self.test_repo_path), "invalid.name", "docs")
        
        # Try with empty name
        with pytest.raises(click.Abort):
            handle_add_category_command(str(self.test_repo_path), "", "docs")
    
    def test_cli_add_category_command(self):
        """Test CLI add-category command."""
        result = self.runner.invoke(add_category, ["documents", "docs", str(self.test_repo_path)])
        
        assert result.exit_code == 0
        assert "Added category 'documents'" in result.output
        assert "internal path" in result.output
        
        # Verify directory was created
        category_dir = self.test_repo_path / "docs"
        assert category_dir.exists()
        assert category_dir.is_dir()
