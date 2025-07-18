import requests
import csv
import re
from unidecode import unidecode

# Airtable credentials
AIRTABLE_BASE_ID = "appjvhsxUUz6o0dzo"
AIRTABLE_API_KEY = "pataexwS1dNvKkmVk.b01f01a400ccf38c96e31b35db5974122438c536a8592b50a1564de4c35e67c3"
AIRTABLE_TABLE_NAME = 'Company'
AIRTABLE_URL = f'https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}'

# Headers for Airtable API
airtable_headers = {
    'Authorization': f'Bearer {AIRTABLE_API_KEY}',
    'Content-Type': 'application/json'
}

def normalize_string(value):
    """Normalizes a string by transliterating, removing special characters, and spaces."""
    if not value:
        return ""
    value = unidecode(value)
    value = re.sub(r'[^a-zA-Z0-9\s]', ' ', value)
    value = re.sub(r'\s+', ' ', value).strip()
    value = value.replace(' ', '')
    value = value.split('.')[0] 
    return value.lower()


def load_csv(file_path):
    """Loads data from a CSV file into a list of dictionaries."""
    with open(file_path, mode='r', newline='', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        return list(reader)

def fetch_airtable_records():
    """Fetches all records from Airtable with pagination handling."""
    records = []
    offset = None
    while True:
        params = {'offset': offset} if offset else {}
        try:
            response = requests.get(AIRTABLE_URL, headers=airtable_headers, params=params)
            response.raise_for_status()
            data = response.json()
            records.extend(data.get('records', []))
            offset = data.get('offset')
            if not offset:
                break
        except Exception as e:
            print(f" Error fetching Airtable records: {str(e)}")
            break
    return records

def match_records(airtable_records, csv_data):
    """Identifies CSV entries that don't exist in Airtable based on normalized names."""
    # Create set of normalized names from Airtable
    airtable_names = set()
    for record in airtable_records:
        company_name = normalize_string(record.get('fields', {}).get('Company Name', ''))
        if company_name:
            airtable_names.add(company_name)

    # Match CSV entries
    matched = []
    unmatched = []
    for csv_row in csv_data:
        org_name = normalize_string(csv_row.get('Organization Name', ''))
        if org_name in airtable_names:
            matched.append(csv_row)
        else:
            unmatched.append(csv_row)
            print(f" CSV entry not found in Airtable: {csv_row['Organization Name']}")

    return matched, unmatched

def save_to_csv(data, filename):
    """Saves a list of dictionaries to a CSV file."""
    if not data:
        print(" No data to write to CSV.")
        return
    
    fieldnames = data[0].keys()  # Extract column headers from first row
    with open(filename, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)
    
    print(f" Unmatched companies saved to {filename}")


def main():
    csv_data = load_csv('vista_extended_funding_data.csv')
    airtable_records = fetch_airtable_records()
    matched, unmatched = match_records(airtable_records, csv_data)

    print("\n Matched CSV Records:")
    for match in matched:
        print(f"CSV Organization: {match['Organization Name']}")

    print("\ Unmatched CSV Records:")
    for record in unmatched:
        print(f"CSV Organization: {record['Organization Name']}")

    print(f"\n Total Matched: {len(matched)}")
    print(f" Total Unmatched: {len(unmatched)}")

    save_to_csv(unmatched, 'unmatched_companies.csv')


if __name__ == "__main__":
    main()