The client did not provide production Airtable or Google Drive access, so I created a sandbox Airtable base and Google Drive folder that mirror the required workflow. The automation is built so the same code can run against the client’s real base and Drive folder by changing environment variables.

# Airtable TXT Attachment Sync

This project is a sandbox implementation for the Airtable TXT Upload Automation test task.

The goal is to automate the process of reading domain records from Airtable, finding the matching `.txt` file in a Google Drive folder, and uploading that file into an Airtable attachment field.

## Background

The client operates many websites, and each website has a corresponding `.txt` file. These files are currently stored in Airtable text fields, but some files are larger than Airtable's text cell limit.

To solve this, the `.txt` files should be moved into an Airtable attachment field.

## Sandbox Setup

Because production Airtable access, Google Drive access, API tokens, and source code were not provided, I created a sandbox environment for testing.

The sandbox contains:

- A test Airtable base
- A test Airtable table named `Sites`
- A test Google Drive folder
- Sample `.txt` files
- Test records for success and failure cases

## Project Name

Airtable TXT Attachment Sync

## Airtable Table

Table name:

`Sites`

Fields:

- `Domain`
- `TXT Filename`
- `TXT Attachment`
- `Legacy TXT Text`
- `Drive File ID`
- `Drive MD5`
- `Drive Modified Time`
- `Drive File Size`
- `Last Sync Status`
- `Last Sync Error`
- `Last Sync At`
- `Last Sync Run ID`

## Sample Airtable Records

| Domain | TXT Filename | Expected Result |
|---|---|---|
| 1bettor.com | 1bettor.com.txt | Successful upload |
| 1betvegas.com | 1betvegas.com.txt | Successful upload |
| 2bet888.com | 2bet888.com.txt | Successful upload |
| betnet.ag | betnet.ag.txt | Successful upload |
| betwar.com | betwar.com.txt | Successful upload |
| missing-test.com | missing-test.com.txt | Missing file error |
| duplicate-test.com | duplicate-test.txt | Duplicate file error |

## Google Drive Test Files

The Google Drive test folder contains normal `.txt` files such as:

- `1bettor.com.txt`
- `1betvegas.com.txt`
- `2bet888.com.txt`
- `betnet.ag.txt`
- `betwar.com.txt`

The file `missing-test.com.txt` is intentionally not uploaded. This is used to test the missing file error case.

The file `duplicate-test.txt` is intentionally uploaded more than once in Google Drive. This is used to test duplicate filename handling.

## Main Assumptions

- Airtable is the source of truth.
- The `Domain` field is the unique business key.
- The `TXT Filename` field tells the automation which Google Drive file belongs to each domain.
- The automation should only upload files that exactly match the filename in Airtable.
- If a file is missing in Google Drive, the script should mark the Airtable record as failed.
- If more than one Drive file has the same expected filename, the script should fail safely and not guess.
- The automation should be safe to rerun.
- Existing downstream systems that still read from the old text field are outside the scope of this task.

## Expected Workflow

1. Read records from the Airtable `Sites` table.
2. Read files from the configured Google Drive folder.
3. Match each Airtable record to a Drive file using `TXT Filename`.
4. Upload the matching `.txt` file to the Airtable `TXT Attachment` field.
5. Store Drive metadata in Airtable.
6. Mark successful records as `Synced`.
7. Mark failed records as `Failed` and write the error message to `Last Sync Error`.

## Error Handling

The automation should handle these cases:

### Missing File

If Airtable says the file should be `missing-test.com.txt`, but that file does not exist in Google Drive, the record should be marked as failed.

Expected error:

`Drive file not found: missing-test.com.txt`

### Duplicate File

If more than one file in Google Drive has the same filename, the automation should not guess which file is correct.

Expected error:

`Duplicate Drive files found for duplicate-test.txt`

### Safe Rerun

If the script is run again and the file has already been uploaded with the same Drive metadata, the script should skip the record instead of uploading again unnecessarily.

## Risk Notes

The biggest risk is uploading the wrong `.txt` file to the wrong domain.

To avoid this, the automation should use exact filename matching and should fail safely when there are duplicates or missing files.

Another risk is silent failure. To avoid this, each run should write sync status, error messages, timestamps, and run IDs back to Airtable.

## Future Production Notes

For production use, the script should be configured with real Airtable and Google Drive credentials through environment variables.

Recommended production setup:

- Python automation script
- Airtable API
- Google Drive API
- Scheduled run using GitHub Actions, Google Cloud Run, or another scheduler
- Slack or email notifications for failures
- Structured logs for debugging

## Current Status

This sandbox setup is prepared for implementing and testing the automation logic.