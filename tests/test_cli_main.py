def test_scan_command():
    """Test the scan command."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        # Create a minimal repository structure for the test
        os.makedirs("repo_dir/db")
        os.makedirs("repo_dir/changes")
        
        # Mock the actual scan implementation to avoid errors
        with patch('historify.cli.cli_scan_command') as mock_scan_command:
            mock_scan_command.return_value = None
            
            result = runner.invoke(scan, ["repo_dir"])
            
            assert result.exit_code == 0
            mock_scan_command.assert_called_once_with("repo_dir", None)

def test_scan_with_category():
    """Test scan with category filter."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        # Create a minimal repository structure for the test
        os.makedirs("repo_dir/db")
        os.makedirs("repo_dir/changes")
        
        # Mock the actual scan implementation to avoid errors
        with patch('historify.cli.cli_scan_command') as mock_scan_command:
            mock_scan_command.return_value = None
            
            result = runner.invoke(scan, ["repo_dir", "--category", "documents"])
            
            assert result.exit_code == 0
            mock_scan_command.assert_called_once_with("repo_dir", "documents")