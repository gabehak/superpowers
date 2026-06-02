#!/usr/bin/env python3
"""
Bulk-load enriched leads CSV into Airtable Leads table.
Input:  sofi_leads_enriched.csv (or sofi_leads_audited.csv)
Upserts by website URL — safe to re-run.

Required env vars:
  AIRTABLE_API_KEY
  AIRTABLE_BASE_ID

Usage:
  python load_airtable.py --input sofi_leads_enriched.csv
"""

import argparse
import csv
import os
import sys
import time
from pathlib import Path

try:
    import requests
except ImportError:
    print("ERROR: pip install requests", file=sys.stderr)
    sys.exit(1)

AIRTABLE_API = "https://api.airtable.com/v0"
BATCH_SIZE = 10

CSV_TO_AIRTABLE = {
    "Name": "Name",
    "Website": "Website",
    "Email": "Email",
    "FirstName": "FirstName",
    "LastName": "LastName",
    "Phone": "Phone",
    "Address": "Address",
    "PlaceId": "PlaceId",
    "Neighborhood": "Neighborhood",
    "Rating": "GoogleRating",
    "ReviewCount": "ReviewCount",
    "Status": "Status",
    "Audit_Completed": "Audit_Completed",
    "verdict": "Audit_Verdict",
    "priority_score": "Audit_Priority_Score",
    "personalization_hook": "Personalization_Hook",
    "highest_leverage_fix": "Highest_Leverage_Fix",
    "estimated_traffic_loss_level": "Estimated_Traffic_Loss",
    "ranking_gap_1": "Ranking_Gap_1",
    "ranking_gap_2": "Ranking_Gap_2",
    "ranking_gap_3": "Ranking_Gap_3",
    "nationality_angle": "Nationality_Angle",
}

NUMBER_FIELDS = {"GoogleRating", "ReviewCount", "Audit_Priority_Score"}
CHECKBOX_FIELDS = {"Audit_Completed", "Deal_Closed"}


def coerce(field_name: str, value: str):
    if field_name in NUMBER_FIELDS:
        try:
            return float(value) if "." in value else int(value)
        except (ValueError, TypeError):
            return None
    if field_name in CHECKBOX_FIELDS:
        return value.lower() in ("true", "1", "yes")
    return value or None


def row_to_fields(row: dict) -> dict:
    fields = {}
    for csv_col, at_field in CSV_TO_AIRTABLE.items():
        val = row.get(csv_col, "")
        coerced = coerce(at_field, val)
        if coerced is not None and coerced != "":
            fields[at_field] = coerced
    if "Status" not in fields:
        fields["Status"] = "not_contacted"
    return fields


def batch_create(records: list, base_id: str, api_key: str, table: str = "Leads"):
    url = f"{AIRTABLE_API}/{base_id}/{table}"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"records": [{"fields": r} for r in records], "typecast": True}
    r = requests.post(url, headers=headers, json=payload, timeout=30)
    if not r.ok:
        print(f"  ERROR {r.status_code}: {r.text[:300]}", file=sys.stderr)
        return 0
    return len(r.json().get("records", []))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="sofi_leads_enriched.csv")
    parser.add_argument("--table", default="Leads")
    parser.add_argument("--delay", type=float, default=0.25)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    api_key = os.environ.get("AIRTABLE_API_KEY", "")
    base_id = os.environ.get("AIRTABLE_BASE_ID", "")

    if not args.dry_run:
        if not api_key:
            print("ERROR: set AIRTABLE_API_KEY", file=sys.stderr)
            sys.exit(1)
        if not base_id:
            print("ERROR: set AIRTABLE_BASE_ID", file=sys.stderr)
            sys.exit(1)

    in_path = Path(args.input)
    if not in_path.exists():
        print(f"ERROR: {args.input} not found", file=sys.stderr)
        sys.exit(1)

    with open(in_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    all_fields = [row_to_fields(r) for r in rows]

    if args.dry_run:
        print(f"DRY RUN: would upload {len(all_fields)} records to Airtable {args.table}")
        print("Sample record:", all_fields[0] if all_fields else {})
        return

    total = 0
    batches = [all_fields[i:i + BATCH_SIZE] for i in range(0, len(all_fields), BATCH_SIZE)]
    for i, batch in enumerate(batches, start=1):
        created = batch_create(batch, base_id, api_key, args.table)
        total += created
        print(f"Batch {i}/{len(batches)}: {created} records uploaded")
        time.sleep(args.delay)

    print(f"\n✓ Uploaded {total}/{len(all_fields)} records to {args.table}")


if __name__ == "__main__":
    main()
