# Decisions, Risks, and Limitations

## Key Decisions

### 1. Airtable remains the source of truth

The workflow reads the domain and expected `.txt` filename from Airtable. Google Drive is treated as file storage, not as the authority for which file belongs to which domain.

### 2. Exact filename matching only

The workflow only uploads a file when the Airtable `TXT Filename` exactly matches one file in the Google Drive folder.

This avoids accidentally attaching the wrong file to the wrong domain.

### 3. Duplicate files fail safely

Google Drive can contain old or duplicate files. If more than one Drive file has the expected filename, the workflow does not guess. It marks the Airtable record as failed and records the matching Drive file IDs.

### 4. Metadata is stored back in Airtable

The workflow stores:

- Drive File ID
- Drive MD5
- Drive Modified Time
- Drive File Size
- Last Sync Status
- Last Sync Error
- Last Sync At
- Last Sync Run ID

This supports safe reruns and easier debugging.

### 5. Legacy text field is not changed

The old text cell is left alone. Downstream systems currently reading from that field need a separate migration plan.

## Risks

### Wrong file attached to wrong domain

This is the biggest risk. The mitigation is exact filename matching and safe failure on duplicates.

### Old files accumulating in Drive

Old and unused files can remain in the folder. The workflow ignores files that are not referenced by Airtable. A future cleanup report could identify unused Drive files.

### Duplicate file names

Duplicate filenames are dangerous. The workflow flags them as failures instead of choosing one.

### Manual edits by team members

Team members may edit Drive files or Airtable records while the sync is running. The workflow reduces risk by recording Drive metadata and run IDs, but production usage should include team rules around changing filenames and records.

### Downstream systems still using old text cells

Moving to attachments solves the Airtable text cell limit, but existing downstream systems that read from the old text cell must be updated separately.

### Airtable attachment URLs

Airtable attachment URLs should not be treated as permanent public file URLs. Downstream systems should read the current attachment object from Airtable or use a controlled file-serving layer.

### API limits and retries

At 5,000 records, the workflow should avoid unnecessary API calls, skip unchanged records, and retry temporary API failures.

## Limitations of This Test Implementation

The provided JSON implementation uses placeholder credentials and environment variables. It is designed to be imported and configured in the operator's n8n environment.

The client did not provide production Airtable access, Google Drive access, API tokens, or existing source code. Therefore, the implementation is designed against a sandbox structure that mirrors the requested production workflow.

Production credentials, base IDs, table names, Drive folder IDs, and attachment field IDs must be configured before running against real data.

## Recommended Follow-up Improvements

1. Add Slack or email alerts for failed runs.
2. Add a summary log table in Airtable.
3. Add an unused Drive file report.
4. Add a domain-level retry mode for emergency fixes.
5. Add a dry-run mode before production migration.
6. Add a downstream migration plan for systems still reading the old text cell.
