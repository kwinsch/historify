# historify

A tool for revision-safe logging of file changes with cryptographic integrity verification.

## Overview

historify is a command-line utility that tracks file changes in one or multiple data directories while maintaining a secure and verifiable record of all modifications. It logs changes with cryptographic hashes (BLAKE3 and SHA256) and secures logs with minisign signatures, ensuring data authenticity and auditability.

It's particularly well-suited for adding compliance and audit capabilities to cloud storage systems like Nextcloud, where cryptographic proof of file integrity is required for regulatory purposes.

### What historify IS

- A cryptographic audit trail for file changes
- A tamper-evident logging system
- A compliance tool for proving file integrity
- A complement to existing storage and backup systems

### What historify is NOT

- **Not a version control system** like Git (no branching, merging, code-focused features)
- **Not a protection mechanism** that prevents files from being altered
- **Not a backup solution** (though it can create snapshots)
- **Not a replacement for access controls** (such as those in Nextcloud or filesystem permissions)

historify detects and logs changes but cannot prevent them. It provides evidence of what has changed and when, but relies on other systems for access control and protection.

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

```bash
# Setup
historify init /path/to/repository --name "My Repository"
historify config minisign.key /path/to/minisign.key /path/to/repository
historify config minisign.pub /path/to/minisign.pub /path/to/repository
historify add-category documents docs /path/to/repository
historify start /path/to/repository

# Daily operations
historify scan /path/to/repository          # Detect and log changes
historify comment "Updated docs" /path/to/repository  # Add a comment
historify closing /path/to/repository       # Sign and create new log
historify verify /path/to/repository        # Verify integrity

# Information and export
historify status /path/to/repository        # Show repository status
historify log /path/to/repository           # View change history
historify snapshot /path/to/backup/dir /path/to/repository  # Create dated backup archive
```

## Automation

Example of secure daily automated scanning:

```bash
# 1. Create a secure credentials file
sudo mkdir -p /etc/historify
echo 'HISTORIFY_PASSWORD="your_password"' | sudo tee /etc/historify/credentials > /dev/null
sudo chmod 600 /etc/historify/credentials

# 2. Create a wrapper script that sources credentials
sudo tee /usr/local/bin/historify-scan > /dev/null << 'EOF'
#!/bin/bash
source /etc/historify/credentials
/usr/local/bin/historify scan "$@"
EOF
sudo chmod 700 /usr/local/bin/historify-scan

# 3. Add to crontab (without exposing password)
# 0 2 * * * /usr/local/bin/historify-scan /path/to/repository
```

## Environment Variables

- `HISTORIFY_PASSWORD`: Password for encrypted minisign key

## Documentation

For complete documentation on all commands, options, and repository structure, refer to the [manual page](docs/historify.1.md).

For specific implementation scenarios and deployment patterns, see the [use cases guide](docs/use-cases.md).

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
| `status` | Display repository status |
| `snapshot` | Create a compressed archive of the repository |

## Concepts

historify provides secure file tracking through:

- **Automatic Change Detection**: Identifies new, changed, moved, and deleted files
- **Cryptographic Hashing**: Uses BLAKE3 and SHA256 for reliable content verification
- **Signature Chain**: Creates a verifiable chain of custody with minisign signatures
- **Logical Categorization**: Organizes content through flexible category definitions

## Integrity Verification

historify combines file hashing and cryptographic signatures to create a tamper-evident chain of custody:

- **File Integrity**: Verifies files against stored hash values
- **Chain Verification**: Links changelogs through hash references
- **Cryptographic Signatures**: Secures change history with minisign

## Contributions

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
