# Task Requirements Summary

## Client Background

The client operates a network of approximately 5,000 websites. Each site has a corresponding `.txt` file. These files are currently stored in Airtable text cells, but some files are hitting Airtable's text cell character limit, so the files need to move into an Airtable attachment field.

The `.txt` files are maintained in a Google Drive folder. Airtable remains the source of truth for which file belongs to which domain.

## Goal

Build an automated workflow that:

1. Reads from an Airtable table to get domains and their corresponding `.txt` filenames.
2. Finds the matching `.txt` file in a Google Drive folder.
3. Uploads the matching file to an Airtable attachment field on the correct record.
4. Can run manually or on a schedule.
5. Can run unattended with clear error visibility.
6. Is safe to rerun without creating wrong or duplicate attachments.
7. Makes debugging easier if a domain has the wrong file or a sync fails.

## Important Conditions

- The domain name is the unique key linking Airtable records to files.
- Old or unused `.txt` files may accumulate in the Drive folder.
- Multiple team members may access both Drive and Airtable.
- Downstream systems currently read from the old text cell; changing those systems is outside this task scope.
- The solution should handle missing files, duplicate files, failed uploads, rate limits, and manual data changes.

## Expected Deliverables

1. A recommended approach document.
2. A working implementation JSON file.
3. A short decisions, risks, and limitations document.
