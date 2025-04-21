# HISTORIFY(1) Manual Page

## NAME
historify - track file history with cryptographic integrity verification

## SYNOPSIS
`historify` *command* [*options*] [*arguments*]

## DESCRIPTION
**Historify** is a command-line tool for tracking file changes in a repository, logging changes with cryptographic hashes (BLAKE3 and SHA256), and securing logs with `minisign` signatures. It ensures data authenticity and auditability through automated signing and verification, supporting multiple repositories and logical categorization of data.

Historify is designed for secure tracking of files that require a high level of integrity protection, such as critical documents, scientific data, or any materials that should remain tamper-evident.

## REPOSITORY STRUCTURE
A historify repository contains:

- `.historify/config`: Repository configuration file
- `.historify/historify.db`: SQLite database for file metadata (can be regenerated from logs)
- `.historify/seed.bin`: Random seed file for integrity
- `changes/`: Directory containing change logs
- `changes/changelog-YYYY-MM.csv`: Monthly change logs
- `changes/changelog-YYYY-MM.csv.minisig`: Signature files for change logs

## COMMANDS

**init** *repo_path* `--name` *name*
: Initialize a new repository at *repo_path* with name *name*. Creates a configuration file (`.historify/config`), SQLite database (`.historify/historify.db`), and random seed file (`.historify/seed.bin`). Logs a `seed` transaction to `changes/changelog-YYYY-MM.csv`.

**config** *key* *value* [*repo_path*]
: Set a configuration *key* to *value* in the repository. Keys use `section.option` format (e.g., `category.default.path`, `hash.algorithms`, `minisign.key`). Logs a `config` transaction.

**add-category** *category_name* *data_path* [*repo_path*]
: Add a data category with specified path for organizing content within the repository. The *data_path* can be a relative path within the repository or an absolute path to an external location. Updates configuration and database to track the new category.

**scan** [*repo_path*] [`--category` *category*]
: Scan the repository's data categories for file changes. Logs transactions (`new`, `move`, `deleted`) with cryptographic hashes to `changes/changelog-YYYY-MM.csv` and automatically signs the log using the configured `minisign_key`. If `--category` is specified, only scans that category.

**sign** [*repo_path*] [`--file` *log_file*] [`--all`]
: Sign change logs with the configured `minisign_key`. If `--file` is provided, signs only that specific file. With `--all`, signs all unsigned change logs in the repository. Prompts for the key's password if encrypted. Creates `.minisig` files.

**verify** [*repo_path*] [`--full-chain`]
: Verify the integrity of change logs. By default, verifies from the latest signature forward. With `--full-chain`, verifies the entire chain of logs. Checks signatures and hash chain integrity.

**status** [*repo_path*] [`--category` *category*]
: Display the current repository status, showing counts of tracked files, recent changes, and signature status. Clearly indicates whether categories are internal (within repository) or external (absolute paths). If `--category` is specified, limits output to the given category.

**log** [*repo_path*] [`--month` *YYYY-MM*] [`--category` *category*]
: Display change history from logs. By default, shows the current month's log. The `--month` option can specify a different month, and `--category` filters by category.

**comment** *message* [*repo_path*]
: Add an administrative comment to the change log. Useful for documenting important events or changes. Logs a `comment` transaction with the specified message.

**snapshot** *output_path* [*repo_path*]
: Create a compressed archive (tar.gz) of the current repository state for archiving purposes. Includes all data files, change logs, and configuration.

**rebuild-db** [*repo_path*]
: Regenerate the SQLite database from change logs. Useful if the database is corrupted or deleted. All information is reconstructed by replaying the change logs from seed to current state.

## OPTIONS

`--name` *name*
: Specify the repository name for `init` (required).

`--category` *category*
: Filter operations by category.

`--month` *YYYY-MM*
: Specify month for log operations.

`--full-chain`
: Verify the entire change log chain (with `verify` command).

`--file` *log_file*
: Specify a particular change log file for operations.

`--all`
: Apply operation to all eligible files (e.g., sign all unsigned logs).

## CONFIGURATION
Historify's configuration controls repository behavior:

- `category.<name>.path`: Path for a specific data category (can be relative or absolute)
- `category.<name>.description`: Optional description for the category
- `hash.algorithms`: Hash algorithms to use (default: `blake3,sha256`)
- `minisign.key`: Path to minisign private key
- `minisign.pub`: Path to minisign public key
- `changes.directory`: Directory for change logs (default: `changes`)

At least one category must be configured for each repository to define what data is tracked.

## CHANGE LOGS
Change logs (`changes/changelog-YYYY-MM.csv`) record file events with the following fields:

- `timestamp`: UTC timestamp with timezone (e.g., `2025-04-21 12:00:00 UTC`)
- `transaction_type`: Event type (`seed`, `new`, `move`, `deleted`, `config`, `comment`, `closing_log`, `verify`)
- `hash`: Primary hash of the file (BLAKE3 by default)
- `path`: Relative file path within the category
- `metadata`: Additional data as key-value pairs (e.g., `size=1024,blake3=...,sha256=...`)
- `size`, `ctime`, `mtime`, `sha256`, `blake3`: Optional file attributes

Logs are signed automatically after `scan` or manually with `sign`, producing `<log_file>.minisig` files.

## INTEGRITY VERIFICATION

Historify provides two levels of integrity verification:

1. **File Integrity**: Verifies that tracked files have not been modified since their last scan by comparing current hashes with stored hashes.

2. **Log Integrity**: Verifies that change logs themselves have not been tampered with through:
   - Cryptographic signatures using minisign
   - Hash chaining where each `closing_log` transaction contains a hash of the log before it was closed

This creates a verifiable chain of custody for all files in the repository.

## CATEGORIES

Categories provide logical grouping of data within a repository. Each category:
- Has its own designated data path (relative or absolute)
- Can be filtered in log and status displays
- Is independently tracked in the database

This allows for organizing different types of data (e.g., documents, source code, data sets) while maintaining a unified integrity verification system.

## EXAMPLES

Initialize a repository:
```bash
historify init /path/to/project --name project-docs
```

Configure a `minisign` keypair:
```bash
historify config minisign.key ~/.minisign/minisign.key /path/to/project
historify config minisign.pub ~/.minisign/minisign.pub /path/to/project
```

Add data categories:
```bash
# Internal category (relative path within repository)
historify add-category source-code src /path/to/project

# External category (absolute path outside repository) 
historify add-category external-data /mnt/external/data-files /path/to/project
```

Scan for file changes:
```bash
# Scan all categories
historify scan /path/to/project

# Scan a specific category
historify scan --category source-code /path/to/project
```

Set up automated scanning via cron:
```bash
# Add to crontab to run daily at 2am
0 2 * * * /usr/local/bin/historify scan /path/to/project
```

Add a comment about recent activity:
```bash
historify comment "Updated documentation" /path/to/project
```

Create an archive snapshot:
```bash
historify snapshot /backup/project-2025-04-21.tar.gz /path/to/project
```

View change history for a specific category:
```bash
historify log --category source-code /path/to/project
```

Sign all unsigned change logs:
```bash
historify sign --all /path/to/project
```

Verify the integrity of the entire change chain:
```bash
historify verify --full-chain /path/to/project
```

Rebuild the database from logs after corruption:
```bash
historify rebuild-db /path/to/project
```

## FILES

`<repo_path>/.historify/config`
: Repository configuration file

`<repo_path>/.historify/historify.db`
: SQLite database for file metadata (can be regenerated from logs)

`<repo_path>/.historify/seed.bin`
: Random seed file for integrity

`<repo_path>/changes/changelog-YYYY-MM.csv`
: Monthly change logs

`<repo_path>/changes/changelog-YYYY-MM.csv.minisig`
: Signature files for change logs

## ENVIRONMENT

Historify relies on these external tools:
- `b3sum`: For BLAKE3 hashing
- `minisign`: For signing and verification

## EXIT STATUS

- **0**: Success
- **1**: General error (e.g., invalid arguments, file not found)
- **2**: Configuration error (e.g., missing keypair)
- **3**: Integrity error (verification failed)
- **4**: Database error

## TROUBLESHOOTING

### Missing Signatures

If verification fails due to missing signatures, sign the logs:
```bash
historify sign --all /path/to/repository
```

### Database Inconsistencies

If the database shows inconsistencies with the file system:
```bash
# Rebuild the database from logs
historify rebuild-db /path/to/repository

# Then rescan to update with latest changes
historify scan /path/to/repository
```

### Hash Algorithm Changes

To update to a new hash algorithm while maintaining backward compatibility:
```bash
historify config hash.algorithms "blake3,sha256,newhash" /path/to/repository
```

## SEE ALSO

`b3sum(1)`, `minisign(1)`, `sha256sum(1)`, `tar(1)`

## AUTHOR

Written by Kevin Bortis <kevin@bortis.ch>
