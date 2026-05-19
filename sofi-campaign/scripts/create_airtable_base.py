#!/usr/bin/env python3
"""
Create the Airtable base + tables + fields via Airtable API.
Run once to bootstrap your CRM.

Required env vars:
  AIRTABLE_API_KEY  (Personal Access Token from airtable.com/create/tokens)
  AIRTABLE_ORG_ID   (Workspace ID — see airtable.com/api, looks like wspXXXXXX)

Usage:
  python create_airtable_base.py
  python create_airtable_base.py --dry-run
"""

import argparse
import json
import os
import sys

try:
    import requests
except ImportError:
    print("ERROR: pip install requests", file=sys.stderr)
    sys.exit(1)

API_BASE = "https://api.airtable.com/v0/meta"

LEADS_FIELDS = [
    {"name": "Name",                  "type": "singleLineText"},
    {"name": "Website",               "type": "url"},
    {"name": "Email",                 "type": "email"},
    {"name": "FirstName",             "type": "singleLineText"},
    {"name": "LastName",              "type": "singleLineText"},
    {"name": "Phone",                 "type": "phoneNumber"},
    {"name": "Address",               "type": "singleLineText"},
    {"name": "PlaceId",               "type": "singleLineText"},
    {
        "name": "Neighborhood",
        "type": "singleSelect",
        "options": {
            "choices": [
                {"name": "Inglewood"},
                {"name": "Westchester"},
                {"name": "Culver City"},
                {"name": "West LA"},
                {"name": "Westwood"},
                {"name": "Marina del Rey"},
                {"name": "El Segundo"},
                {"name": "Other"},
            ]
        },
    },
    {"name": "GoogleRating",          "type": "number",    "options": {"precision": 1}},
    {"name": "ReviewCount",           "type": "number",    "options": {"precision": 0}},
    {
        "name": "Status",
        "type": "singleSelect",
        "options": {
            "choices": [
                {"name": "not_contacted", "color": "grayLight2"},
                {"name": "awaiting_reply", "color": "yellowLight2"},
                {"name": "booked_call", "color": "blueLight2"},
                {"name": "closed", "color": "greenLight2"},
                {"name": "declined", "color": "redLight2"},
                {"name": "unsubscribed", "color": "grayLight2"},
            ]
        },
    },
    {"name": "Audit_Completed",       "type": "checkbox",  "options": {"icon": "check", "color": "greenBright"}},
    {
        "name": "Audit_Verdict",
        "type": "singleSelect",
        "options": {
            "choices": [
                {"name": "not_ready",       "color": "redBright"},
                {"name": "partial",         "color": "yellowBright"},
                {"name": "tournament_ready","color": "greenBright"},
            ]
        },
    },
    {"name": "Audit_Priority_Score",  "type": "number",    "options": {"precision": 0}},
    {"name": "Personalization_Hook",  "type": "multilineText"},
    {"name": "Highest_Leverage_Fix",  "type": "singleLineText"},
    {
        "name": "Estimated_Traffic_Loss",
        "type": "singleSelect",
        "options": {
            "choices": [
                {"name": "high",   "color": "redBright"},
                {"name": "medium", "color": "yellowBright"},
                {"name": "low",    "color": "grayLight2"},
            ]
        },
    },
    {"name": "Ranking_Gap_1",         "type": "singleLineText"},
    {"name": "Ranking_Gap_2",         "type": "singleLineText"},
    {"name": "Ranking_Gap_3",         "type": "singleLineText"},
    {"name": "Nationality_Angle",     "type": "singleLineText"},
    {"name": "Deal_Closed",           "type": "checkbox",  "options": {"icon": "check", "color": "greenBright"}},
    {"name": "Deal_Amount",           "type": "currency",  "options": {"precision": 2, "symbol": "$"}},
    {"name": "Delivery_Date",         "type": "date",      "options": {"dateFormat": {"name": "us"}}},
    {"name": "Notes",                 "type": "multilineText"},
]


def create_base(api_key: str, org_id: str, dry_run: bool = False) -> str:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "name": "SoFi Tournament Leads",
        "workspaceId": org_id,
        "tables": [
            {
                "name": "Leads",
                "description": "All scraped + enriched restaurant leads near SoFi Stadium",
                "fields": LEADS_FIELDS,
            },
            {
                "name": "Replies",
                "description": "Inbound replies",
                "fields": [
                    {"name": "Reply_Date",    "type": "date"},
                    {"name": "Reply_Text",    "type": "multilineText"},
                    {
                        "name": "Category",
                        "type": "singleSelect",
                        "options": {
                            "choices": [
                                {"name": "INTERESTED_BOOK_CALL"},
                                {"name": "OBJECTION_PRICE"},
                                {"name": "OBJECTION_TIMING"},
                                {"name": "ALREADY_DOING_IT"},
                                {"name": "REFERRAL"},
                                {"name": "UNSUBSCRIBE"},
                                {"name": "NOT_OWNER"},
                                {"name": "OTHER"},
                            ]
                        },
                    },
                    {"name": "Response_Sent", "type": "checkbox"},
                    {
                        "name": "Next_Action",
                        "type": "singleSelect",
                        "options": {
                            "choices": [
                                {"name": "send_loom"},
                                {"name": "book_call"},
                                {"name": "send_objection_handler"},
                                {"name": "follow_up"},
                                {"name": "archive"},
                            ]
                        },
                    },
                ],
            },
            {
                "name": "Closes",
                "description": "Confirmed deals",
                "fields": [
                    {"name": "Close_Date",       "type": "date"},
                    {"name": "Deal_Size",        "type": "currency", "options": {"precision": 2, "symbol": "$"}},
                    {
                        "name": "Service_Tier",
                        "type": "singleSelect",
                        "options": {
                            "choices": [
                                {"name": "Tournament_Audit"},
                                {"name": "Audit_Plus_Maintenance"},
                                {"name": "Full_Tournament_Run"},
                            ]
                        },
                    },
                    {"name": "Payment_Received", "type": "checkbox"},
                    {"name": "Delivery_Date",    "type": "date"},
                    {
                        "name": "Delivery_Status",
                        "type": "singleSelect",
                        "options": {
                            "choices": [
                                {"name": "pending"},
                                {"name": "in_progress"},
                                {"name": "completed"},
                            ]
                        },
                    },
                    {"name": "Upsell_Offered",   "type": "checkbox"},
                    {"name": "Notes",            "type": "multilineText"},
                ],
            },
        ],
    }

    if dry_run:
        print("=== DRY RUN: would POST to Airtable Bases API ===")
        print(json.dumps(payload, indent=2))
        return "(dry-run)"

    r = requests.post(f"{API_BASE}/bases", headers=headers, json=payload, timeout=30)
    if not r.ok:
        print(f"ERROR {r.status_code}: {r.text}", file=sys.stderr)
        sys.exit(1)

    data = r.json()
    base_id = data.get("id", "")
    print(f"✓ Base created: {data.get('name')} (ID: {base_id})")
    print(f"  URL: https://airtable.com/{base_id}")
    print(f"\nSet this env var for n8n and run_audit.py:")
    print(f"  export AIRTABLE_BASE_ID={base_id}")
    return base_id


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    api_key = os.environ.get("AIRTABLE_API_KEY", "")
    org_id = os.environ.get("AIRTABLE_ORG_ID", "")

    if not args.dry_run:
        if not api_key:
            print("ERROR: set AIRTABLE_API_KEY (Personal Access Token from airtable.com/create/tokens)", file=sys.stderr)
            sys.exit(1)
        if not org_id:
            print("ERROR: set AIRTABLE_ORG_ID (workspace ID from airtable.com/api)", file=sys.stderr)
            sys.exit(1)

    create_base(api_key, org_id, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
