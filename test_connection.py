import os
import requests
from dotenv import load_dotenv
from urllib.parse import quote

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


def test_airtable_connection():
    print("\nTesting Airtable connection...")

    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{quote(AIRTABLE_TABLE_NAME)}"

    headers = {
        "Authorization": f"Bearer {AIRTABLE_TOKEN}"
    }

    params = {
        "pageSize": 5
    }

    response = requests.get(url, headers=headers, params=params, timeout=30)

    if response.status_code != 200:
        print("Airtable connection failed.")
        print("Status:", response.status_code)
        print("Response:", response.text)
        return False

    data = response.json()
    records = data.get("records", [])

    print("Airtable connection successful.")
    print(f"Found {len(records)} sample records.")

    for record in records:
        fields = record.get("fields", {})
        domain = fields.get(DOMAIN_FIELD)
        filename = fields.get(FILENAME_FIELD)

        print(f"- Domain: {domain} | TXT Filename: {filename}")

    return True


def test_google_drive_connection():
    print("\nTesting Google Drive connection...")

    scopes = ["https://www.googleapis.com/auth/drive.readonly"]

    credentials = service_account.Credentials.from_service_account_file(
        GOOGLE_SERVICE_ACCOUNT_FILE,
        scopes=scopes
    )

    service = build("drive", "v3", credentials=credentials)

    query = (
        f"'{GOOGLE_DRIVE_FOLDER_ID}' in parents "
        f"and trashed = false"
    )

    response = service.files().list(
        q=query,
        pageSize=20,
        fields="files(id, name, mimeType, modifiedTime, size, md5Checksum)",
        includeItemsFromAllDrives=True,
        supportsAllDrives=True
    ).execute()

    files = response.get("files", [])

    print("Google Drive connection successful.")
    print(f"Found {len(files)} files in the test folder.")

    for file in files:
        print(f"- {file.get('name')} | ID: {file.get('id')}")

    return True


if __name__ == "__main__":
    airtable_ok = test_airtable_connection()
    drive_ok = test_google_drive_connection()

    print("\nResult:")

    if airtable_ok and drive_ok:
        print("Both Airtable and Google Drive connections are working.")
        print("Next step: build the sync script.")
    else:
        print("One or more connections failed. Fix the error before continuing.")