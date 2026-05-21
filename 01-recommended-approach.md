# Recommended Approach

## Summary

I recommend building the workflow as an n8n automation with Airtable, Google Drive, and HTTP request steps. This gives the team a visible workflow that can run manually, run on a schedule, and be maintained without requiring a full application deployment.

For a larger production environment, the same logic could also be implemented as a Python service running on Google Cloud Run or AWS Lambda. However, for this test task and for operational visibility, n8n is a good fit because the client can inspect every step of the workflow, rerun it manually, and connect failure notifications easily.

## What I Would Build

The workflow reads Airtable records from a `Sites` table, builds a list of expected `.txt` filenames, reads files from a configured Google Drive folder, matches files by exact filename, downloads the correct file, uploads it to the Airtable attachment field, and writes sync metadata back to Airtable.

The workflow supports both:

- Manual trigger
- Scheduled trigger

## Recommended Airtable Fields

The Airtable table should include these fields:

| Field | Type | Purpose |
|---|---|---|
| Domain | Single line text | Unique website/domain key |
| TXT Filename | Single line text | Expected Google Drive filename |
| TXT Attachment | Attachment | New target attachment field |
| Legacy TXT Text | Long text | Existing old field, kept during migration |
| Drive File ID | Single line text | Tracks the exact synced Drive file |
| Drive MD5 | Single line text | Detects changed file content |
| Drive Modified Time | Single line text | Detects updated Drive files |
| Drive File Size | Number | Helps debug unexpected file changes |
| Last Sync Status | Single select | Pending, Synced, Skipped, Failed |
| Last Sync Error | Long text | Stores failure reason |
| Last Sync At | Date/time | Last run timestamp |
| Last Sync Run ID | Single line text | Groups all records from the same run |

## Workflow Logic

1. Trigger workflow manually or by schedule.
2. Read all Airtable site records.
3. Read all `.txt` files from the configured Google Drive folder.
4. Build a Drive index by exact filename.
5. For each Airtable record:
   - Validate `Domain` and `TXT Filename`.
   - Find the exact filename in Drive.
   - If no file is found, mark the record as `Failed`.
   - If more than one matching file is found, mark the record as `Failed`.
   - If the file was already synced and metadata has not changed, mark it as `Skipped`.
   - Otherwise, download the file from Drive.
   - Upload it to the Airtable attachment field.
   - Store Drive metadata and mark the record as `Synced`.
6. Send or record a summary of uploaded, skipped, and failed records.

## Why Exact Filename Matching

The safest rule is to only upload a file when the `TXT Filename` field exactly matches one Google Drive file.

The workflow should not guess based on partial names or latest modified time. At this scale, guessing could attach the wrong file to the wrong domain. If there are duplicate filenames, the workflow fails that record and records the duplicate Drive IDs for debugging.

## Rerun Safety

The workflow stores the Drive file ID, MD5 checksum, modified time, and size in Airtable. On the next run, if those values match and the Airtable attachment already exists, the workflow skips the record.

This makes the workflow safe to rerun without babysitting.

## Failure Visibility

Every failure should write back to Airtable:

- `Last Sync Status = Failed`
- `Last Sync Error = specific reason`
- `Last Sync At = timestamp`
- `Last Sync Run ID = current run ID`

This prevents silent failure. At production scale, I would also connect Slack or email notifications for runs with failures.

## Scale Considerations

At approximately 5,000 records, the workflow should avoid one Drive search per Airtable row. Instead, it should list the Drive folder once, build an index, and then match records in memory.

The workflow should also be careful with Airtable API limits by avoiding unnecessary updates and by skipping unchanged records.

## Production Deployment

Recommended production setup:

- n8n workflow with Airtable and Google Drive credentials stored securely in n8n.
- Environment variables for base ID, table name, folder ID, and field IDs.
- Manual trigger for testing and emergency reruns.
- Schedule trigger for automated runs.
- Optional Slack/email notification for failure summaries.
- Audit fields in Airtable for debugging.
