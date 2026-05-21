import os
import json
from collections import defaultdict
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

GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
GOOGLE_DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID")


def get_airtable_records():
    print("Reading records from Airtable...")

    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{quote(AIRTABLE_TABLE_NAME)}"

    headers = {
        "Authorization": f"Bearer {AIRTABLE_TOKEN}"
    }

    records = []
    offset = None

    while True:
        params = {
            "pageSize": 100
        }

        if offset:
            params["offset"] = offset

        response = requests.get(url, headers=headers, params=params, timeout=30)

        if response.status_code != 200:
            raise Exception(f"Airtable error: {response.status_code} - {response.text}")

        data = response.json()
        records.extend(data.get("records", []))

        offset = data.get("offset")
        if not offset:
            break

    print(f"Found {len(records)} Airtable records.")
    return records


def get_drive_files():
    print("Reading files from Google Drive...")

    scopes = ["https://www.googleapis.com/auth/drive.readonly"]

    credentials = service_account.Credentials.from_service_account_file(
        GOOGLE_SERVICE_ACCOUNT_FILE,
        scopes=scopes
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
            supportsAllDrives=True
        ).execute()

        files.extend(response.get("files", []))

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    print(f"Found {len(files)} files in Google Drive folder.")
    return files


def build_drive_index(files):
    drive_index = defaultdict(list)

    for file in files:
        filename = file.get("name")
        if filename and filename.lower().endswith(".txt"):
            drive_index[filename].append(file)

    return drive_index


def run_dry_check():
    records = get_airtable_records()
    drive_files = get_drive_files()
    drive_index = build_drive_index(drive_files)

    report = {
        "total_records": len(records),
        "success_ready": [],
        "missing_files": [],
        "duplicate_files": [],
        "invalid_records": []
    }

    print("\nChecking Airtable records against Google Drive files...\n")

    for record in records:
        record_id = record.get("id")
        fields = record.get("fields", {})

        domain = fields.get(DOMAIN_FIELD)
        filename = fields.get(FILENAME_FIELD)

        if not domain or not filename:
            report["invalid_records"].append({
                "record_id": record_id,
                "domain": domain,
                "filename": filename,
                "error": "Missing Domain or TXT Filename"
            })
            print(f"[INVALID] Domain: {domain} | Filename: {filename}")
            continue

        matches = drive_index.get(filename, [])

        if len(matches) == 0:
            report["missing_files"].append({
                "record_id": record_id,
                "domain": domain,
                "filename": filename,
                "error": "Drive file not found"
            })
            print(f"[MISSING] {domain} -> {filename}")
            continue

        if len(matches) > 1:
            report["duplicate_files"].append({
                "record_id": record_id,
                "domain": domain,
                "filename": filename,
                "drive_file_ids": [file.get("id") for file in matches],
                "error": "Duplicate Drive files found"
            })
            print(f"[DUPLICATE] {domain} -> {filename}")
            continue

        file = matches[0]

        report["success_ready"].append({
            "record_id": record_id,
            "domain": domain,
            "filename": filename,
            "drive_file_id": file.get("id"),
            "drive_modified_time": file.get("modifiedTime"),
            "drive_file_size": file.get("size"),
            "drive_md5": file.get("md5Checksum")
        })

        print(f"[READY] {domain} -> {filename}")

    with open("dry_run_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print("\nDry run finished.")
    print(f"Total records: {report['total_records']}")
    print(f"Ready to upload: {len(report['success_ready'])}")
    print(f"Missing files: {len(report['missing_files'])}")
    print(f"Duplicate files: {len(report['duplicate_files'])}")
    print(f"Invalid records: {len(report['invalid_records'])}")

    print("\nReport saved to: dry_run_report.json")


if __name__ == "__main__":
    run_dry_check()