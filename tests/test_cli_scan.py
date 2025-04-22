def test_cli_scan_command(self):
    """Test CLI scan command through the main CLI interface."""
    # Use the correct patching target
    with patch('historify.cli.cli_scan_command') as mock_scan_command:
        mock_scan_command.return_value = None
        
        result = self.runner.invoke(scan, [str(self.test_repo_path)])
        
        assert result.exit_code == 0
        mock_scan_command.assert_called_once_with(str(self.test_repo_path), None)

def test_cli_scan_command_with_category(self):
    """Test CLI scan command with category filter through the main CLI interface."""
    # Use the correct patching target
    with patch('historify.cli.cli_scan_command') as mock_scan_command:
        mock_scan_command.return_value = None
        
        result = self.runner.invoke(scan, [str(self.test_repo_path), "--category", "docs"])
        
        assert result.exit_code == 0
        mock_scan_command.assert_called_once_with(str(self.test_repo_path), "docs")