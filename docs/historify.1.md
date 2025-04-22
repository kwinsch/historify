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

- `db/config`: Repository configuration file
- `db/cache.db`: SQLite database for file metadata (can be regenerated from logs)
- `db/seed.bin`: Random seed file for integrity
- `db/seed.bin.minisig`: Mandatory signature for seed
- `changes/`: Directory containing change logs
- `changes/changelog-YYYY-MM.csv`: Monthly change logs
- `changes/changelog-YYYY-MM.csv.minisig`: Signature files for change logs. File created at closing event.

## COMMANDS

**init** *repo_path*
: Initialize a new repository at *repo_path* with name *name*. Creates a configuration file (`db/config`), SQLite database (`db/cache.db`), and random seed file (`db/seed.bin`).

**config** *key* *value* *repo_path*
: Set a configuration *key* to *value* in the repository. Keys use `section.option` format (e.g., `category.default.path`, `hash.algorithms`, `minisign.key`). Logs a `config` transaction.

**check-config** *repo_path*
: Verifies the configuration.

**add-category** *category_name* *data_path* *repo_path*
: Add a data category with specified path for organizing content within the repository. The *data_path* can be a relative path within the repository or an absolute path to an external location. Updates configuration and database to track the new category. At least one category must be present to start tracking files.

**start|closing** [*repo_path*]
: Signs the `db/seed.bin` in case of a new repo or the latest `db/changelog-YYYY-MM-DD.csv` file. On successfull signing, the first|next `db/changelog-YYYY-MM-DD.csv` file is created. The command issues an implicit prior `verify`. A new file can not be created without prior closing (sigining) the last open file. Logs a `closing` transaction to the new changelog with the hash of the last seed or changelog file, closing the chain. The signature is placed in the same folder as the original file with a `.minisig` extension.

**scan** [*repo_path*]
: Scan the repository's data categories for file changes. Logs changes (`new`, `move`, `deleted`, `duplicate`) with cryptographic hashes to the latest open changelog file, where a file can produce multiple changelog entries (e.g. `new` and `duplicate`).

**verify** [*repo_path*] [`--full-chain`]
: Verify the integrity of change logs. By default, verifies from the latest signed changelog forward. With `--full-chain`, verifies the entire chain of logs including available signatures. Checks signatures and hash chain integrity. Implies a prior implicit `check-config`. Rebuids the sqlite database automatically if a corruption is detected from the full-chain.

**status** [*repo_path*] [`--category` *category*]
: Display the current repository status, showing counts of tracked files, recent changes, and signature status. Clearly indicates whether categories are internal (within repository) or external (absolute paths). If `--category` is specified, limits output to the given category.

**log** [*repo_path*] [`--file` *YYYY-MM-DD*] [`--category` *category*]
: Display change history from logs. By default, shows the current log. The `--file` option can specify a different changelog, and `--category` filters by category.

**comment** *message* [*repo_path*]
: Add an administrative comment to the change log. Useful for documenting important events or changes. Logs a `comment`  with the specified message.

**snapshot** *output_path* [*repo_path*]
: Create a compressed archive (tar.gz) of the current repository state for archiving purposes. Includes all data files, change logs, seed, signatures, and configuration.

## OPTIONS

`--category` *category*
: Filter operations by category.

`--full-chain`
: Verify the entire change log chain (with `verify` command).

`--file` *log_file*
: Specify a particular change log file for operations.

## CONFIGURATION
Historify's configuration controls repository behavior:

- `category.<name>.path`: Path for a specific data category
- `category.<name>.description`: Optional description for the category
- `hash.algorithms`: Hash algorithms to use (default: `blake3,sha256`)
- `minisign.key`: Path to minisign private key 
- `minisign.pub`: Path to minisign public key
- `changes.directory`: Directory for change logs (default: `changes`)

All paths can be either relative or absolute.

At least one category must be configured for each repository to define what data is tracked.

## CHANGE LOGS
Change logs (`changes/changelog-YYYY-MM-DD.csv`) record file events with the following fields:

- `timestamp`: UTC timestamp with timezone (e.g., `2025-04-21 12:00:00 UTC`)
- `changelog_types`: Event type (`closing`, `move`, `deleted`, `duplicate`, `config`, `comment`, `verify`)
- `path`: Relative file path within the category
- `size`, `ctime`, `mtime`, `sha256`, `blake3`: Metadata attributes

## INTEGRITY VERIFICATION

Historify provides two levels of integrity verification:

1. **File Integrity**: Verifies that tracked files have not been modified since their last scan by comparing current hashes with stored hashes.

2. **Log Integrity**: Verifies that change logs themselves have not been tampered with through:
   - Cryptographic signatures using minisign
   - Hash chaining where each `closing` changelog entry contains a hash of the last changelog file.

This creates a verifiable chain of custody for all files in the repository.

## CATEGORIES

Categories provide logical grouping of data within a repository. Each category:
- Has its own designated data path (relative or absolute)
- Can be filtered in log and status displays
- Is independently tracked in the database

This allows for organizing different types of data (e.g., documents, source code, data sets, financial records) while maintaining a unified integrity verification system.

## EXAMPLES

Initialize a repository:
```bash
historify init /path/to/project
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

Start first changelog file:
```bash
historify start /path/to/project
# OR
historify closing /path/to/project
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

Closing current changelog file:
```bash
historify closing /path/to/project
# OR
historify start /path/to/project
```

Create an archive snapshot:
```bash
historify snapshot /backup/project-2025-04-21.tar.gz /path/to/project
```

View change history for a specific category:
```bash
historify log --category source-code /path/to/project
```

Verify the integrity of the entire change chain:
```bash
historify verify --full-chain /path/to/project
```

## FILES

`<repo_path>/db/config`
: Repository configuration file

`<repo_path>/db/cache.db`
: SQLite database for file metadata (can be regenerated from logs)

`<repo_path>/db/seed.bin`
: Random seed file for integrity

`<repo_path>/db/seed.bin.minisig`
: Signature files for seed

`<repo_path>/changes/changelog-YYYY-MM-DD.csv`
: Monthly change logs

`<repo_path>/changes/changelog-YYYY-MM-DD.csv.minisig`
: Signature files for change logs

## ENVIRONMENT

Historify relies on these external tools:
- `minisign`: For signing and verification
- `b3sum`: For BLAKE3 hashing (if native implementation is not available)

## EXIT STATUS

- **0**: Success
- **1**: General error (e.g., invalid arguments, file not found)
- **2**: Configuration error (e.g., missing keypair)
- **3**: Integrity error (verification failed)
- **4**: Database error

### Hash Algorithm Changes

To update to a new hash algorithm while maintaining backward compatibility:
```bash
historify config hash.algorithms "blake3,sha256,newhash" /path/to/repository
```

Such changes will introduce an additional field in the output CSV in the future, while maintaining the order of the existing ones.

## SEE ALSO

`b3sum(1)`, `minisign(1)`, `sha256sum(1)`, `tar(1)`

## AUTHOR

Written by Kevin Bortis <kevin@bortis.ch>
