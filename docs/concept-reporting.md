# historify Reporting Concept

This document outlines a minimal, focused approach to implementing reporting capabilities in historify with an emphasis on simplicity and minimal dependencies.

## Goals

1. Provide standardized evidence of file integrity for compliance purposes
2. Generate human-readable reports from historify data
3. Support basic regulatory compliance documentation
4. Maintain simplicity and minimal dependencies

## Phase 1: Basic Text Reports

The initial implementation will focus on simple text-based reports that can be generated directly from the command line with no additional dependencies beyond what historify already uses.

### Command Structure

```
historify report [report_type] [repo_path] [--options]
```

### Report Types

#### 1. Integrity Report

**Command**: `historify report integrity [repo_path] [--category CATEGORY]`

**Purpose**: Verify and document the integrity status of files

**Output Format**: Text/Markdown

**Content**:
- Repository name and path
- Verification timestamp
- Verification status (pass/fail)
- Count of verified files by category
- List of any integrity issues found
- Hash of the latest changelog
- Signature verification status

**Example Usage**:
```bash
# Generate integrity report
historify report integrity /path/to/repo > integrity_report.txt

# Generate category-specific report
historify report integrity /path/to/repo --category financial > financial_integrity.txt
```

#### 2. Activity Report

**Command**: `historify report activity [repo_path] [--from DATE] [--to DATE] [--category CATEGORY]`

**Purpose**: Summarize file activity during a specific period

**Output Format**: Text/Markdown/CSV

**Content**:
- Time period covered
- Summary counts by operation type (new, changed, moved, deleted)
- List of most active files
- Daily/weekly activity totals

**Example Usage**:
```bash
# Generate quarterly activity report
historify report activity /path/to/repo --from 2025-01-01 --to 2025-03-31 > q1_activity.txt

# Export activity as CSV
historify report activity /path/to/repo --from 2025-01-01 --to 2025-03-31 --format csv > q1_activity.csv
```

#### 3. File History Report

**Command**: `historify report file-history [repo_path] --file FILE_PATH`

**Purpose**: Show complete history for a specific file

**Output Format**: Text/Markdown

**Content**:
- File identification (path, current hash)
- Chronological list of all operations affecting the file
- Hash values at each change point
- Timestamps of all changes

**Example Usage**:
```bash
# Generate file history
historify report file-history /path/to/repo --file data/financial/report.pdf > report_history.txt
```

### Implementation Approach

1. **Minimal Dependencies**:
   - Use standard library text formatting
   - Leverage existing CSV handling code
   - Avoid introducing external dependencies

2. **Data Sources**:
   - Use existing changelog parsing code
   - Leverage verification functions from the `verify` command
   - Read integrity data from existing CSVs

3. **Output Options**:
   - Default to stdout for piping to files or other tools
   - Support direct file output with `--output` flag
   - Include basic Markdown formatting for improved readability

## Future Directions (Phase 2)

While maintaining our commitment to simplicity, potential future enhancements could include:

1. **PDF/A Output**:
   - Add optional PDF generation for formal documentation
   - Focus on PDF/A format for archival compliance
   - Consider using a minimal PDF generation library with few dependencies

2. **Report Signing**:
   - Leverage existing minisign capabilities to sign reports
   - Include verification instructions in the report

3. **Templated Reports**:
   - Simple text-based templates for different compliance standards
   - Customizable headers/footers for organizational branding

## Development Priorities

1. Implement `report integrity` command first (highest compliance value)
2. Add `report activity` command
3. Add `report file-history` command
4. Add output format options (text, markdown, csv)
5. Document usage in man pages

## Command-Line Integration

The reporting commands will be implemented as extensions to the existing CLI structure:

```python
@cli.command()
@click.argument("repo_path", type=click.Path(exists=True))
@click.option("--category", help="Limit report to specific category")
@click.option("--format", type=click.Choice(["text", "markdown", "csv"]), default="text", 
              help="Output format")
@click.option("--output", type=click.Path(), help="Output file path (defaults to stdout)")
def report_integrity(repo_path, category, format, output):
    """Generate an integrity verification report."""
    # Implementation
```

## Technical Considerations

1. **Performance**: Reports should handle large repositories efficiently
2. **Accuracy**: All reporting data must reflect the actual state of files and logs
3. **Completeness**: Reports should contain all information needed for compliance
4. **Consistency**: Report formats should remain stable between versions