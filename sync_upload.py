import argparse
import base64
import io
import os
import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from urllib.parse import quote

import requests
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload


load_dotenv()

AIRTABLE_TOKEN = os.getenv("AIRTABLE_TOKEN")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID")
AIRTABLE_TABLE_NAME = os.getenv("AIRTABLE_TABLE_NAME")

DOMAIN_FIELD = os.getenv("AIRTABLE_DOMAIN_FIELD", "Domain")
FILENAME_FIELD = os.getenv("AIRTABLE_FILENAME_FIELD", "TXT Filename")
ATTACHMENT_FIELD = os.getenv("AIRTABLE_ATTACHMENT_FIELD", "TXT Attachment")

DRIVE_ID_FIELD = os.getenv("AIRTABLE_DRIVE_ID_FIELD", "Drive File ID")
MD5_FIELD = os.getenv("AIRTABLE_MD5_FIELD", "Drive MD5")
MODIFIED_FIELD = os.getenv("AIRTABLE_MODIFIED_FIELD", "Drive Modified Time")
SIZE_FIELD = os.getenv("AIRTABLE_SIZE_FIELD", "Drive File Size")
STATUS_FIELD = os.getenv("AIRTABLE_STATUS_FIELD", "Last Sync Status")
ERROR_FIELD = os.getenv("AIRTABLE_ERROR_FIELD", "Last Sync Error")
SYNCED_AT_FIELD = os.getenv("AIRTABLE_SYNCED_AT_FIELD", "Last Sync At")
RUN_ID_FIELD = os.getenv("AIRTABLE_RUN_ID_FIELD", "Last Sync Run ID")

GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
GOOGLE_DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID")


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def airtable_headers():
    return {
        "Authorization": f"Bearer {AIRTABLE_TOKEN}",
        "Content-Type": "application/json",
    }


def airtable_request(method, url, **kwargs):
    for attempt in range(1, 6):
        response = requests.request(
            method,
            url,
            headers=airtable_headers(),
            timeout=60,
            **kwargs,
        )

        if response.status_code in [429, 500, 502, 503, 504]:
            wait_seconds = min(30, 2 ** attempt)
            print(f"[RETRY] Airtable status {response.status_code}. Waiting {wait_seconds}s...")
            time.sleep(wait_seconds)
            continue

        if response.status_code >= 400:
            raise Exception(f"Airtable API error {response.status_code}: {response.text}")

        return response

    raise Exception("Airtable API failed after retries.")


def get_airtable_records():
    print("Reading Airtable records...")

    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{quote(AIRTABLE_TABLE_NAME)}"
    records = []
    offset = None

    while True:
        params = {"pageSize": 100}

        if offset:
            params["offset"] = offset

        response = airtable_request("GET", url, params=params)
        data = response.json()

        records.extend(data.get("records", []))

        offset = data.get("offset")
        if not offset:
            break

        time.sleep(0.25)

    print(f"Found {len(records)} Airtable records.")
    return records


def update_airtable_record(record_id, fields):
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{quote(AIRTABLE_TABLE_NAME)}/{record_id}"

    payload = {
        "fields": fields,
        "typecast": True,
    }

    airtable_request("PATCH", url, json=payload)
    time.sleep(0.25)


def build_drive_service():
    scopes = ["https://www.googleapis.com/auth/drive.readonly"]

    credentials = service_account.Credentials.from_service_account_file(
        GOOGLE_SERVICE_ACCOUNT_FILE,
        scopes=scopes,
    )

    return build("drive", "v3", credentials=credentials)


def get_drive_files(service):
    print("Reading Google Drive files...")

    query = (
        f"'{GOOGLE_DRIVE_FOLDER_ID}' in parents "
        f"and trashed = false "
        f"and mimeType != 'application/vnd.google-apps.folder'"
    )

    files = []
    page_token = None

    while True:
        response = service.files().list(
            q=query,
            pageSize=1000,
            pageToken=page_token,
            fields="nextPageToken, files(id, name, mimeType, modifiedTime, size, md5Checksum)",
            includeItemsFromAllDrives=True,
            supportsAllDrives=True,
        ).execute()

        files.extend(response.get("files", []))

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    print(f"Found {len(files)} Google Drive files.")
    return files


def build_drive_index(files):
    index = defaultdict(list)

    for file in files:
        filename = file.get("name")

        if filename and filename.lower().endswith(".txt"):
            index[filename].append(file)

    return index


def download_drive_file(service, file_id):
    request = service.files().get_media(
        fileId=file_id,
        supportsAllDrives=True,
    )

    file_buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(file_buffer, request)

    done = False
    while not done:
        status, done = downloader.next_chunk()

    return file_buffer.getvalue()


def upload_attachment(record_id, filename, file_bytes):
    attachment_field = quote(ATTACHMENT_FIELD, safe="")

    url = (
        f"https://content.airtable.com/v0/"
        f"{AIRTABLE_BASE_ID}/{record_id}/{attachment_field}/uploadAttachment"
    )

    payload = {
        "contentType": "text/plain",
        "filename": filename,
        "file": base64.b64encode(file_bytes).decode("utf-8"),
    }

    print("Uploading attachment...")
    print("Record ID:", record_id)
    print("Attachment field:", ATTACHMENT_FIELD)
    print("Filename:", filename)
    print("File size:", len(file_bytes))
    print("Upload URL:", url)

    response = airtable_request("POST", url, json=payload)
    return response.json()


def already_synced(fields, drive_file):
    current_attachment = fields.get(ATTACHMENT_FIELD)

    if not current_attachment:
        return False

    stored_drive_id = fields.get(DRIVE_ID_FIELD)
    stored_md5 = fields.get(MD5_FIELD)
    stored_modified = fields.get(MODIFIED_FIELD)

    current_drive_id = drive_file.get("id")
    current_md5 = drive_file.get("md5Checksum")
    current_modified = drive_file.get("modifiedTime")

    if stored_drive_id != current_drive_id:
        return False

    if current_md5 and stored_md5 != current_md5:
        return False

    if stored_modified != current_modified:
        return False

    return True


def process_record(record, drive_index, drive_service, run_id, dry_run=False):
    record_id = record.get("id")
    fields = record.get("fields", {})

    domain = fields.get(DOMAIN_FIELD)
    filename = fields.get(FILENAME_FIELD)

    if not domain or not filename:
        raise Exception("Missing Domain or TXT Filename")

    matches = drive_index.get(filename, [])

    if len(matches) == 0:
        raise Exception(f"Drive file not found: {filename}")

    if len(matches) > 1:
        drive_ids = ", ".join([file.get("id") for file in matches])
        raise Exception(f"Duplicate Drive files found for {filename}. Drive IDs: {drive_ids}")

    drive_file = matches[0]

    if already_synced(fields, drive_file):
        if not dry_run:
            update_airtable_record(record_id, {
                STATUS_FIELD: "Skipped",
                ERROR_FIELD: "",
                SYNCED_AT_FIELD: now_iso(),
                RUN_ID_FIELD: run_id,
            })

        return "skipped"

    if dry_run:
        return "would_upload"

    file_bytes = download_drive_file(drive_service, drive_file.get("id"))

    upload_result = upload_attachment(record_id, filename, file_bytes)

    attachment_value = upload_result.get("fields", {}).get(ATTACHMENT_FIELD)

    if not attachment_value:
        raise Exception("Upload finished, but attachment field is still empty.")

    update_airtable_record(record_id, {
        DRIVE_ID_FIELD: drive_file.get("id"),
        MD5_FIELD: drive_file.get("md5Checksum"),
        MODIFIED_FIELD: drive_file.get("modifiedTime"),
        SIZE_FIELD: int(drive_file.get("size", 0)) if drive_file.get("size") else 0,
        STATUS_FIELD: "Synced",
        ERROR_FIELD: "",
        SYNCED_AT_FIELD: now_iso(),
        RUN_ID_FIELD: run_id,
    })

    return "uploaded"


def run_sync(dry_run=False):
    run_id = str(uuid.uuid4())

    print("\nStarting TXT attachment sync...")
    print(f"Run ID: {run_id}")
    print(f"Dry run: {dry_run}\n")

    drive_service = build_drive_service()
    records = get_airtable_records()
    drive_files = get_drive_files(drive_service)
    drive_index = build_drive_index(drive_files)

    stats = {
        "uploaded": 0,
        "would_upload": 0,
        "skipped": 0,
        "failed": 0,
    }

    for record in records:
        record_id = record.get("id")
        fields = record.get("fields", {})

        domain = fields.get(DOMAIN_FIELD)
        filename = fields.get(FILENAME_FIELD)

        try:
            result = process_record(
                record=record,
                drive_index=drive_index,
                drive_service=drive_service,
                run_id=run_id,
                dry_run=dry_run,
            )

            stats[result] += 1
            print(f"[{result.upper()}] {domain} -> {filename}")

        except Exception as error:
            stats["failed"] += 1
            error_message = str(error)

            print(f"[FAILED] {domain} -> {filename} | {error_message}")

            if not dry_run:
                update_airtable_record(record_id, {
                    STATUS_FIELD: "Failed",
                    ERROR_FIELD: error_message[:1000],
                    SYNCED_AT_FIELD: now_iso(),
                    RUN_ID_FIELD: run_id,
                })

    print("\nSync finished.")
    print(f"Uploaded: {stats['uploaded']}")
    print(f"Would upload: {stats['would_upload']}")
    print(f"Skipped: {stats['skipped']}")
    print(f"Failed: {stats['failed']}")
    print(f"Run ID: {run_id}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")

    args = parser.parse_args()

    run_sync(dry_run=args.dry_run)