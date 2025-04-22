# Historify

A tool for revision-safe logging of file changes with cryptographic integrity verification.

## Overview

Historify is a command-line utility that tracks file changes in one or multiple data directories while maintaining a secure and verifiable record of all modifications. It logs changes with cryptographic hashes (BLAKE3 and SHA256) and secures logs with minisign signatures, ensuring data authenticity and auditability.

### Key Features

- **Secure Tracking**: Uses BLAKE3 and SHA256 hashing with minisign signatures
- **Multiple Categories**: Organize content with logical categorization of data
- **Integrity Verification**: Full chain verification ensures tamper-evident history
- **Comprehensive Logging**: Tracks new files, modifications, moves, deletions, and administrative events
- **Multiple Repositories**: Supports managing multiple independent repositories

## Installation

```bash
pip install historify
```

### Requirements

- Python 3.13 or later
- minisign (for signing and verification)
- b3sum (optional, for BLAKE3 hashing if native implementation is unavailable)

## Quick Start

### Initialize a Repository

```bash
# Create a new repository
historify init /path/to/repository --name "My Repository"

# Configure minisign keys
historify config minisign.key /path/to/minisign.key /path/to/repository
historify config minisign.pub /path/to/minisign.pub /path/to/repository

# Add a data category
historify add-category documents docs /path/to/repository

# Start tracking changes
historify start /path/to/repository
```

### Daily Usage

```bash
# Scan for changes
historify scan /path/to/repository

# Add a comment about recent activity
historify comment "Updated documentation files" /path/to/repository

# Close current changelog and start a new one
historify closing /path/to/repository

# Verify the integrity of your repository
historify verify /path/to/repository

# Verify the full chain from seed to the latest signed changelog
historify verify --full-chain /path/to/repository
```

### View Repository Information

```bash
# View repository status
historify status /path/to/repository

# View change history
historify log /path/to/repository

# Find duplicate files
historify duplicates /path/to/repository
```

## Setting Up Automated Tracking

You can set up automated scanning using cron:

```bash
# Add to crontab to run daily at 2am
0 2 * * * HISTORIFY_PASSWORD="mypassword" /usr/local/bin/historify scan /path/to/repository
```

## Environment Variables

- `HISTORIFY_PASSWORD`: Password for encrypted minisign key

## Documentation

For complete documentation on all commands and options, refer to the [manual page](docs/historify.1.md).

### Common Commands

| Command | Description |
|---------|-------------|
| `init` | Initialize a new repository |
| `config` | Set configuration options |
| `add-category` | Add a data category |
| `start` / `closing` | Sign current changelog and create a new one |
| `scan` | Scan for changes in tracked files |
| `verify` | Verify repository integrity |
| `log` | View change history |
| `comment` | Add administrative comments |
| `status` | Display repository status |
| `duplicates` | Find duplicate files |
| `snapshot` | Create a compressed archive of the repository |

## Change Detection

Historify automatically detects and tracks different types of file changes:

- **New Files**: Files that appear for the first time in a category
- **Changed Files**: Modifications to existing files (content changes)
- **Moved Files**: Files that have been renamed or moved to a different location
- **Deleted Files**: Files that no longer exist in the category

Each scan operation identifies these changes automatically and logs appropriate transactions in the changelog.

## Repository Structure

```
repository/
├── db/
│   ├── config                  # Repository configuration
│   ├── integrity.csv           # Integrity verification information
│   └── seed.bin                # Random seed file 
│   └── seed.bin.minisig        # Signature for seed
└── changes/
    ├── changelog-YYYY-MM-DD.csv       # Daily change logs
    └── changelog-YYYY-MM-DD.csv.minisig # Signatures for change 
```

## Integrity Verification

Historify provides two levels of integrity verification:

1. **File Integrity**: Verifies that files haven't been modified since scanning
2. **Log Integrity**: Verifies the changelog files themselves through:
   - Cryptographic signatures using minisign
   - Hash chaining where each changelog references the previous file

## Contributions

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
