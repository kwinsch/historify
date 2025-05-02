# historify Use Cases

This document outlines common use cases for `historify` and provides guidance on implementation.

## Cloud Storage Audit and Compliance

### Problem Statement

Modern cloud storage solutions (such as Nextcloud, OneDrive, Dropbox, etc.) offer excellent collaboration features and access controls, but often lack robust cryptographic audit trails that can withstand legal scrutiny. Organizations handling sensitive documents such as:

- Financial records
- Legal documentation
- Medical records
- Intellectual property
- Regulatory compliance materials

need to maintain tamper-evident proof that files have not been modified outside of authorized processes.

### Solution: historify as a Compliance Layer

`historify` provides a cryptographic audit layer that complements cloud storage systems by:

1. **Tracking all file changes** with cryptographic hashes
2. **Maintaining a verifiable chain** of file operations
3. **Providing cryptographic signatures** that can be independently verified
4. **Creating secure snapshots** for compliance archives

Unlike traditional version control systems, `historify` is designed with compliance and auditing as primary goals, making it ideal for regulatory requirements.

### Implementation with Nextcloud

#### Architecture

In this common setup:

- **Nextcloud** handles day-to-day document storage, user access, and collaboration
- **historify** runs scheduled scans to create a tamper-evident audit record
- Periodic snapshots create archives for long-term compliance storage

```
┌─────────────────┐     ┌───────────────────┐     ┌─────────────────┐
│                 │     │                   │     │                 │
│   Nextcloud     │     │     historify     │     │   Compliance    │
│   Document      │────>│     Integrity     │────>│   Archives      │
│   Storage       │     │     Verification  │     │   (ISO/BD-R)    │
│                 │     │                   │     │                 │
└─────────────────┘     └───────────────────┘     └─────────────────┘
    User access          Cryptographic audit       Long-term storage
    Collaboration        Tamper detection          Legal evidence
```

#### Setup Steps

1. **Configure External Category**

   Create a category pointing to your Nextcloud data directory:

   ```bash
   historify add-category nextcloud-finance /path/to/nextcloud/data/finance /path/to/repository
   ```

2. **Scheduled Scanning**

   Set up a cron job to scan for changes on a regular schedule:

   ```bash
   # Run scan every hour
   0 * * * * /usr/local/bin/historify scan --category nextcloud-finance /path/to/repository
   
   # Close and sign the changelog daily at midnight
   0 0 * * * /usr/local/bin/historify closing /path/to/repository
   ```

3. **Periodic Verification**

   Regularly verify your historical chain to ensure integrity:

   ```bash
   # Verify integrity weekly
   0 0 * * 0 /usr/local/bin/historify verify --full-chain /path/to/repository
   ```

4. **Compliance Snapshots**

   Create timestamped archives for compliance requirements:

   ```bash
   # Monthly full snapshot with media archive
   0 0 1 * * /usr/local/bin/historify snapshot /archival/directory /path/to/repository --full --media
   ```

#### Security Considerations

- Store the `historify` repository on a separate system from the Nextcloud server
- Use separate administrator credentials for `historify` operations
- Keep minisign keys secured (consider hardware security modules for production use)
- Implement physical security for archival media

### Demonstrating Compliance

When an auditor or legal entity requests proof of document integrity:

1. **Status Report**: Run `historify status` to show tracking statistics
2. **Verification**: Demonstrate `historify verify --full-chain` to prove the integrity of the entire history
3. **Specific File History**: Use `historify log --category nextcloud-finance` to show the complete history of changes
4. **Archival Evidence**: Provide archived snapshots showing consistent state at compliance checkpoints

### Benefits

- **Legal Defensibility**: Cryptographic proof that documents have not been tampered with
- **Separation of Duties**: Storage system (Nextcloud) separate from audit system (historify)
- **Non-Repudiation**: Signed changelogs provide stronger evidence than internal logs
- **Archival Compliance**: Media archives satisfy long-term retention requirements
- **Minimal Disruption**: End users continue using familiar cloud storage interfaces

### Limitations and Boundaries

It's important to understand what historify can and cannot do:

- **Detection, Not Prevention**: historify can detect when files have been changed but cannot prevent changes from occurring. It is an audit tool, not an access control mechanism.

- **Complements, Not Replaces**: historify should be used alongside existing access control systems (like Nextcloud's user permissions), not as a replacement for them.

- **Verification, Not Recovery**: While historify can verify that a file has been altered, it does not store previous versions of files (unlike version control systems) and cannot restore altered files.

- **Independent Verification**: The integrity of historify's audit trail depends on the security of its own repository and private keys. Store these separately from the data being audited.

- **Time Delay**: Since historify operates on a scan schedule, there is a window between when a file change occurs and when it is detected and logged. Configure scan frequency based on your security requirements.

## Scientific Data Integrity

Another common use case is ensuring the integrity of scientific datasets throughout a research project...

[Note: Additional use cases could be expanded here]