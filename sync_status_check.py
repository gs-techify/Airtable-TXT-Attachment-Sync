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


load_dotenv()

AIRTABLE_TOKEN = os.getenv("AIRTABLE_TOKEN")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID")
AIRTABLE_TABLE_NAME = os.getenv("AIRTABLE_TABLE_NAME")

DOMAIN_FIELD = os.getenv("AIRTABLE_DOMAIN_FIELD", "Domain")
FILENAME_FIELD = os.getenv("AIRTABLE_FILENAME_FIELD", "TXT Filename")

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


def get_airtable_records():
    print("Reading Airtable records...")

    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{quote(AIRTABLE_TABLE_NAME)}"
    records = []
    offset = None

    while True:
        params = {"pageSize": 100}

        if offset:
            params["offset"] = offset

        response = requests.get(
            url,
            headers=airtable_headers(),
            params=params,
            timeout=30,
        )

        if response.status_code != 200:
            raise Exception(f"Airtable read error: {response.status_code} - {response.text}")

        data = response.json()
        records.extend(data.get("records", []))

        offset = data.get("offset")
        if not offset:
            break

    print(f"Found {len(records)} Airtable records.")
    return records


def get_drive_files():
    print("Reading Google Drive files...")

    scopes = ["https://www.googleapis.com/auth/drive.readonly"]

    credentials = service_account.Credentials.from_service_account_file(
        GOOGLE_SERVICE_ACCOUNT_FILE,
        scopes=scopes,
    )

    service = build("drive", "v3", credentials=credentials)

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


def update_airtable_record(record_id, fields):
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{quote(AIRTABLE_TABLE_NAME)}/{record_id}"

    payload = {
        "fields": fields,
        "typecast": True,
    }

    response = requests.patch(
        url,
        headers=airtable_headers(),
        json=payload,
        timeout=30,
    )

    if response.status_code not in [200, 201]:
        raise Exception(f"Airtable update error: {response.status_code} - {response.text}")

    time.sleep(0.25)


def run_status_check():
    run_id = str(uuid.uuid4())
    checked_at = now_iso()

    records = get_airtable_records()
    drive_files = get_drive_files()
    drive_index = build_drive_index(drive_files)

    ready_count = 0
    failed_count = 0
    invalid_count = 0

    print("\nChecking records and updating Airtable statuses...\n")

    for record in records:
        record_id = record.get("id")
        fields = record.get("fields", {})

        domain = fields.get(DOMAIN_FIELD)
        filename = fields.get(FILENAME_FIELD)

        if not domain or not filename:
            invalid_count += 1

            update_airtable_record(record_id, {
                STATUS_FIELD: "Failed",
                ERROR_FIELD: "Missing Domain or TXT Filename",
                SYNCED_AT_FIELD: checked_at,
                RUN_ID_FIELD: run_id,
            })

            print(f"[FAILED] Missing Domain or TXT Filename | Record ID: {record_id}")
            continue

        matches = drive_index.get(filename, [])

        if len(matches) == 0:
            failed_count += 1

            update_airtable_record(record_id, {
                STATUS_FIELD: "Failed",
                ERROR_FIELD: f"Drive file not found: {filename}",
                SYNCED_AT_FIELD: checked_at,
                RUN_ID_FIELD: run_id,
            })

            print(f"[FAILED] {domain} -> {filename} | File not found")
            continue

        if len(matches) > 1:
            failed_count += 1
            drive_ids = ", ".join([file.get("id") for file in matches])

            update_airtable_record(record_id, {
                STATUS_FIELD: "Failed",
                ERROR_FIELD: f"Duplicate Drive files found for {filename}. Drive IDs: {drive_ids}",
                SYNCED_AT_FIELD: checked_at,
                RUN_ID_FIELD: run_id,
            })

            print(f"[FAILED] {domain} -> {filename} | Duplicate files found")
            continue

        ready_count += 1
        drive_file = matches[0]

        update_airtable_record(record_id, {
            STATUS_FIELD: "Ready",
            ERROR_FIELD: "",
            SYNCED_AT_FIELD: checked_at,
            RUN_ID_FIELD: run_id,
        })

        print(f"[READY] {domain} -> {filename} | Drive ID: {drive_file.get('id')}")

    print("\nStatus check finished.")
    print(f"Ready: {ready_count}")
    print(f"Failed: {failed_count}")
    print(f"Invalid: {invalid_count}")
    print(f"Run ID: {run_id}")


if __name__ == "__main__":
    run_status_check()