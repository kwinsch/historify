# historify(1) Manual Page

## NAME
historify - track file history with cryptographic integrity verification

## SYNOPSIS
`historify` *command* [*options*] [*arguments*]

## DESCRIPTION
**historify** is a command-line tool for tracking file changes in a repository, logging changes with cryptographic hashes (BLAKE3 and SHA256), and securing logs with `minisign` signatures. It ensures data authenticity and auditability through automated signing and verification, supporting multiple repositories and logical categorization of data.

historify is designed for secure tracking of files that require a high level of integrity protection, such as critical documents, scientific data, or any materials that should remain tamper-evident.

## REPOSITORY STRUCTURE
A historify repository contains:

- `db/config`: Repository configuration file
- `db/config.csv`: CSV version of the configuration file
- `db/integrity.csv`: CSV database containing integrity verification information
- `db/seed.bin`: Random seed file for integrity
- `db/seed.bin.minisig`: Mandatory signature for seed
- `db/keys/`: Directory containing archived public keys
- `changes/`: Directory containing change logs (location can be configured)
- `changes/changelog-YYYY-MM-DD.csv`: Daily change logs
- `changes/changelog-YYYY-MM-DD.csv.minisig`: Signature files for change logs created at closing events

## COMMANDS

**init** *repo_path* [`--name` *name*]
: Initialize a new repository at *repo_path*. Creates a configuration file (`db/config`), configuration CSV (`db/config.csv`), integrity CSV (`db/integrity.csv`), and random seed file (`db/seed.bin`). If `--name` is not specified, the directory name is used as the repository name.

**config** *key* *value* *repo_path*
: Set a configuration *key* to *value* in the repository. Keys use `section.option` format (e.g., `category.default.path`, `hash.algorithms`, `minisign.key`). Logs a `config` transaction.

**check-config** *repo_path*
: Verifies the configuration.

**add-category** *category_name* *data_path* *repo_path*
: Add a data category with specified path for organizing content within the repository. The *data_path* can be a relative path within the repository or an absolute path to an external location. Updates configuration and database to track the new category. At least one category must be present to start tracking files.

**start|closing** [*repo_path*]
: Signs the `db/seed.bin` in case of a new repo or the latest `changelog-YYYY-MM-DD.csv` file. On successful signing, the first/next `changelog-YYYY-MM-DD.csv` file is created. The signature is placed in the same folder as the original file with a `.minisig` extension. A new changelog file cannot be created without signing the previous one first. Logs a `closing` transaction to the new changelog with the hash of the previous file (seed or changelog), establishing the hash chain for integrity verification.

**scan** [*repo_path*] [`--category` *category*]
: Scan the repository's data categories for file changes. Automatically detects and logs changes (`new`, `changed`, `move`, `deleted`) with cryptographic hashes to the latest open changelog file. The scan operation intelligently identifies new files, modified content, files that have been moved or renamed, and files that have been deleted.

**duplicates** [*repo_path*] [`--category` *category*]
: Find and display duplicate files in the repository based on hash values. Groups identical files together and shows information about size and potential wasted space. Can be filtered by category.

**verify** [*repo_path*] [`--full-chain`]
: Verify the integrity of change logs. By default, verifies from the latest signed changelog forward. With `--full-chain`, verifies the entire chain of logs including available signatures. Checks signatures and hash chain integrity. Implies a prior implicit `check-config`. Rebuilds the integrity CSV automatically if a corruption is detected from the full-chain.

**status** [*repo_path*] [`--category` *category*]
: Display the current repository status, showing counts of tracked files, recent changes, and signature status. Clearly indicates whether categories are internal (within repository) or external (absolute paths). If `--category` is specified, limits output to the given category.

**log** [*repo_path*] [`--file` *YYYY-MM-DD*] [`--category` *category*]
: Display change history from logs. By default, shows the current log. The `--file` option can specify a different changelog, and `--category` filters by category.

**comment** *message* [*repo_path*]
: Add an administrative comment to the change log. Useful for documenting important events or changes. Logs a `comment`  with the specified message. In addition to explicit user comments, historify automatically logs key system activities (like verify and snapshot operations) as comments for better auditing and traceability.

**snapshot** *output_dir* [*repo_path*] [`--name` *name*] [`--full`] [`--media`]
: Create a compressed archive (tar.gz) of the current repository state for archiving purposes. Saves files to *output_dir* with automatically generated filenames that include the current date. The base name can be customized with `--name` (defaults to repository name). Filenames will be sanitized to use only alphanumeric characters and hyphens. Includes all data files, change logs, seed, signatures, and configuration directly residing under the repo path. If `--full` is specified, all external data files and folders referenced by the repository are backed up as separate tar.gz archives in the same output directory. If `--media` is specified, the tar.gz files are packed in ISO files with UDF 2.60 filesystem, ready to be burned to single layer BD-R disks (25GB). Other media types are currently not supported. If the content exceeds the expected media size, the archives are split into multiple ISO files.

## OPTIONS

`--category` *category*
: Filter operations by category. Used with `scan`, `status`, `log`, and `duplicates` commands.

`--full-chain`
: Verify the entire change log chain (with `verify` command).

`--file` *log_file*
: Specify a particular change log file for operations (with `log` command).

## CONFIGURATION
historify's configuration controls repository behavior:

- `category.<name>.path`: Path for a specific data category
- `category.<name>.description`: Optional description for the category
- `hash.algorithms`: Hash algorithms to use (default: `blake3,sha256`)
- `minisign.key`: Path to minisign private key 
- `minisign.pub`: Path to minisign public key
- `changes.directory`: Directory for change logs (default: `changes`)
- `iso.publisher`: Custom publisher name for ISO images (default: `historify archive`)

All paths can be either relative or absolute.

At least one category must be configured for each repository to define what data is tracked.

## CHANGE LOGS
Change logs (`changes/changelog-YYYY-MM-DD.csv`) record file events with the following fields:

- `timestamp`: UTC timestamp with timezone (e.g., `2025-04-21 12:00:00 UTC`)
- `changelog_types`: Event type (`closing`, `new`, `changed`, `move`, `deleted`, `config`, `comment`, `verify`)
- `path`: Relative file path within the category
- `size`, `ctime`, `mtime`, `sha256`, `blake3`: Metadata attributes

Duplicate files are not marked specifically in the changelog. Use the `duplicates` command to find files with identical content based on their hash values.

## TRANSACTION TYPES

historify uses the following transaction types to track changes:

- `new`: A file that appears for the first time in a category
- `changed`: A file that has been modified (content changes)
- `move`: A file that has been moved or renamed (path has changed, but content is identical)
- `deleted`: A file that no longer exists in the category
- `closing`: Administrative transaction that links changelogs in a chain
- `config`: Configuration change
- `comment`: User-added comment (includes both user comments and system-generated action logs)
- `verify`: Verification operation

## INTEGRITY VERIFICATION

historify provides two levels of integrity verification:

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

## ENVIRONMENT

`HISTORIFY_PASSWORD`
: Password for encrypted minisign key. If this environment variable is set, historify will use it for signing operations instead of prompting for a password at the command line. This is useful for automated scripts and batch operations. If the key is not encrypted, this variable is ignored.

historify relies on these external tools:
- `minisign`: For signing and verification
- `b3sum`: For BLAKE3 hashing (if native implementation is not available)

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

Set up secure automated scanning:
```bash
# 1. Create a credentials file with restricted permissions
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
0 2 * * * /usr/local/bin/historify-scan /path/to/project
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

View change history for a specific category:
```bash
historify log --category source-code /path/to/project
```

Find duplicate files in the repository:
```bash
historify duplicates /path/to/project
```

Find duplicate files in a specific category:
```bash
historify duplicates --category source-code /path/to/project
```

Verify the integrity of the entire change chain:
```bash
historify verify --full-chain /path/to/project
```

Create archive snapshots:
```bash
# Create basic snapshot (saves to /backup/project_YYYY-MM-DD.tar.gz)
historify snapshot /backup /path/to/project

# Specify a custom name (saves to /backup/archive_YYYY-MM-DD.tar.gz)
historify snapshot /backup /path/to/project --name archive

# Create a snapshot with external data
historify snapshot /backup /path/to/project --full

# Create a snapshot packaged for BD-R media
historify snapshot /backup /path/to/project --media

# All options combined
historify snapshot /backup /path/to/project --name archive --full --media
```

## FILES

`<repo_path>/db/config`
: Repository configuration file (INI format)

`<repo_path>/db/config.csv`
: Repository configuration in CSV format

`<repo_path>/db/integrity.csv`
: CSV file containing integrity verification information

`<repo_path>/db/seed.bin`
: Random seed file for integrity (1MB of random data)

`<repo_path>/db/seed.bin.minisig`
: Signature file for seed

`<repo_path>/db/keys/`
: Directory containing archived copies of public keys

`<repo_path>/changes/changelog-YYYY-MM-DD.csv`
: Daily change logs (location configurable via changes.directory)

`<repo_path>/changes/changelog-YYYY-MM-DD.csv.minisig`
: Signature files for change logs

## EXIT STATUS

- **0**: Success
- **1**: General error (e.g., invalid arguments, file not found)
- **2**: Configuration error (e.g., missing keypair)
- **3**: Integrity error (verification failed)
- **4**: Database error

## Hash Algorithm Changes

To update to a new hash algorithm while maintaining backward compatibility:
```bash
historify config hash.algorithms "blake3,sha256,newhash" /path/to/repository
```

Such changes will introduce an additional field in the output CSV in the future, while maintaining the order of the existing ones.

## ISO Metadata

When creating ISO images with the `--media` flag, historify adds meaningful metadata to help identify the disc contents:

- **Volume Identifier**: Contains the snapshot base name and date (e.g., `archive_2025-01-15`)
- **System Identifier**: Set to "historify"
- **Publisher**: Set to "historify archive" by default, but can be customized with the `iso.publisher` configuration option
- **Preparer**: Contains "historify" and the creation date
- **Application**: Points to the project's homepage "https://github.com/kwinsch/historify"

To customize the ISO publisher information:
```bash
historify config iso.publisher "Your Company Name" /path/to/repository
```

## SEE ALSO

`b3sum(1)`, `minisign(1)`, `sha256sum(1)`, `tar(1)`

## AUTHOR

Written by Kevin Bortis <kevin@bortis.ch>
