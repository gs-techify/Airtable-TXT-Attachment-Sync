import os
import requests
from dotenv import load_dotenv

load_dotenv()

AIRTABLE_TOKEN = os.getenv("AIRTABLE_TOKEN")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID")

url = f"https://api.airtable.com/v0/meta/bases/{AIRTABLE_BASE_ID}/tables"

headers = {
    "Authorization": f"Bearer {AIRTABLE_TOKEN}"
}

response = requests.get(url, headers=headers, timeout=30)

if response.status_code != 200:
    print("Failed to read Airtable schema.")
    print("Status:", response.status_code)
    print("Response:", response.text)
    print()
    print("Most likely reason: your Airtable token does not have schema.bases:read scope.")
    exit()

data = response.json()

for table in data.get("tables", []):
    print("=" * 80)
    print("TABLE NAME:", table.get("name"))
    print("TABLE ID:", table.get("id"))
    print("=" * 80)

    for field in table.get("fields", []):
        print(f"Field name: {field.get('name')}")
        print(f"Field ID:   {field.get('id')}")
        print(f"Field type: {field.get('type')}")
        print("-" * 40)