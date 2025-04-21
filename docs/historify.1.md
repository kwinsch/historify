# HISTORIFY(1) Manual Page

## NAME
historify - track file history with cryptographic integrity

## SYNOPSIS
`historify` *command* [*options*] *repo_path*

## DESCRIPTION
**Historify** is a command-line tool for tracking file changes in a repository, logging transactions with BLAKE3 hashes, and securing logs with `minisign` signatures. It ensures data authenticity and auditability through automated signing and verification, supporting multiple repositories with shared or unique keypairs.

## COMMANDS
**init** *repo_path* `--name` *name*
: Initialize a new repository at *repo_path* with name *name*. Creates a configuration file (`.historify/config`), SQLite database (`.historify/historify.db`), and random seed file (`.historify/seed.bin`). Logs a `seed` transaction to `translog-YYYY-MM.csv`.

**config** *repo_path* [`--scope` `{global|local}`] *key* *value*
: Set a configuration *key* to *value* in the specified *scope* (`global` for `~/.historify/config`, `local` for `.historify/config`). Keys use `section.option` format (e.g., `repo.<name>.data_dir`, `repo.<name>.minisign_key`). Logs a `config` transaction.

**scan** *repo_path*
: Scan the repository’s data directory (default: `data`, configurable via `repo.<name>.data_dir`) for file changes. Logs transactions (`new`, `move`, `delete`) with BLAKE3 hashes to `translog-YYYY-MM.csv` and automatically signs the log using the configured `minisign_key`.

**sign** *repo_path* *log_file*
: Sign the specified *log_file* (e.g., `translog-2025-04.csv`) with the configured `minisign_key` (set via `config`). Prompts for the key’s password if encrypted. Creates `<log_file>.minisig`.

**verify** *repo_path* *log_file*
: Verify the signature of *log_file* using the configured `minisign_pub` key. Checks `<log_file>.minisig` for integrity.

**log** *repo_path*
: Display the transaction history from the current month’s log (`translog-YYYY-MM.csv`). Shows timestamp, transaction type, file path, and metadata (e.g., BLAKE3 hash, file size).

## OPTIONS
`--name` *name*
: Specify the repository name for `init` (required).

`--scope` `{global|local}`
: Set the configuration scope for `config` (default: `local`).

## CONFIGURATION
Historify uses configuration files to manage settings:
- **Global**: `~/.historify/config` (e.g., default tools: `tools.b3sum=/usr/bin/b3sum`, `tools.minisign=/usr/bin/minisign`).
- **Local**: `<repo_path>/.historify/config` (e.g., `repo.<name>.data_dir=data`, `repo.<name>.minisign_key=~/.minisign/minisign.key`, `repo.<name>.minisign_pub=~/.minisign/minisign.pub`).

Use the `config` command to set keypair paths for signing and verification. The same keypair can be shared across multiple repositories.

## TRANSACTION LOGS
Transaction logs (`translog-YYYY-MM.csv`) record file events with the following fields:
- `timestamp`: UTC timestamp (e.g., `2025-04-21 12:00:00 UTC`).
- `transaction_type`: Event type (`seed`, `new`, `move`, `delete`, `config`, `closing_log`).
- `hash`: BLAKE3 hash of the file.
- `path`: Relative file path.
- `metadata`: Additional data (e.g., `size=1024,blake3=...`).
- `size`, `ctime`, `mtime`, `sha256`, `blake3`: Optional file attributes.

Logs are signed automatically after `scan` or manually with `sign`, producing `<log_file>.minisig`.

## EXAMPLES
Initialize a repository:
```bash
historify init /tmp/my-repo --name my-repo
```

Configure a `minisign` keypair:
```bash
historify config /tmp/my-repo --scope local repo.my-repo.minisign_key ~/.minisign/minisign.key
historify config /tmp/my-repo --scope local repo.my-repo.minisign_pub ~/.minisign/minisign.pub
```

Scan for file changes:
```bash
historify scan /tmp/my-repo
```

Sign a transaction log:
```bash
historify sign /tmp/my-repo translog-2025-04.csv
```

Verify a transaction log:
```bash
historify verify /tmp/my-repo translog-2025-04.csv
```

View transaction history:
```bash
historify log /tmp/my-repo
```

## FILES
`~/.historify/config`
: Global configuration file.

`<repo_path>/.historify/config`
: Local repository configuration.

`<repo_path>/.historify/historify.db`
: SQLite database for file metadata.

`<repo_path>/.historify/seed.bin`
: Random seed file for integrity.

`<repo_path>/translog-YYYY-MM.csv`
: Monthly transaction log.

`<repo_path>/translog-YYYY-MM.csv.minisig`
: Signature file for transaction log.

## ENVIRONMENT
Historify relies on external tools:
- `/usr/bin/b3sum`: For BLAKE3 hashing.
- `/usr/bin/minisign`: For signing and verification.

## EXIT STATUS
- **0**: Success.
- **1**: General error (e.g., invalid arguments, file not found).
- **2**: Configuration error (e.g., missing keypair).

## BUGS
Report issues at https://github.com/kwinsch/historify/issues.

## AUTHOR
Written by [Your Name] <your.email@example.com>.

## SEE ALSO
`b3sum(1)`, `minisign(1)`, `historify-getting-started(7)`