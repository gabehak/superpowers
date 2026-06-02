#!/usr/bin/env python3
"""
Enrich leads CSV with email addresses via Hunter.io domain search.
Input:  sofi_leads_qualified.csv
Output: sofi_leads_enriched.csv

Required env vars:
  HUNTER_API_KEY

Usage:
  python enrich_emails.py --input sofi_leads_qualified.csv
"""

import argparse
import csv
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

try:
    import requests
except ImportError:
    print("ERROR: pip install requests", file=sys.stderr)
    sys.exit(1)

HUNTER_ENDPOINT = "https://api.hunter.io/v2/domain-search"


def domain_from_url(url: str) -> str:
    if not url:
        return ""
    if not url.startswith("http"):
        url = "https://" + url
    parsed = urlparse(url)
    domain = parsed.netloc.lstrip("www.")
    return domain


def hunter_lookup(domain: str, api_key: str) -> list[dict]:
    """Return list of {email, first_name, last_name, position, confidence}."""
    params = {"domain": domain, "api_key": api_key, "limit": 5, "type": "personal"}
    try:
        r = requests.get(HUNTER_ENDPOINT, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
        emails = data.get("data", {}).get("emails", [])
        return [
            {
                "email": e.get("value", ""),
                "first_name": e.get("first_name", ""),
                "last_name": e.get("last_name", ""),
                "position": e.get("position", ""),
                "confidence": e.get("confidence", 0),
            }
            for e in emails
        ]
    except Exception as e:
        return [{"email": "", "error": str(e)}]


def best_email(emails: list[dict]) -> dict:
    if not emails:
        return {}
    owner_titles = {"owner", "founder", "ceo", "president", "gm", "general manager", "manager"}
    for e in emails:
        pos = (e.get("position") or "").lower()
        if any(t in pos for t in owner_titles):
            return e
    return max(emails, key=lambda x: x.get("confidence", 0))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="sofi_leads_qualified.csv")
    parser.add_argument("--output", default="sofi_leads_enriched.csv")
    parser.add_argument("--delay", type=float, default=1.5)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    api_key = os.environ.get("HUNTER_API_KEY", "")
    if not args.dry_run and not api_key:
        print("ERROR: set HUNTER_API_KEY", file=sys.stderr)
        sys.exit(1)

    in_path = Path(args.input)
    if not in_path.exists():
        print(f"ERROR: {args.input} not found", file=sys.stderr)
        sys.exit(1)

    with open(in_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    extra_fields = ["Email", "FirstName", "LastName", "ContactPosition", "EmailConfidence"]
    all_fields = list(rows[0].keys())
    for field in extra_fields:
        if field not in all_fields:
            all_fields.append(field)

    out_path = Path(args.output)
    found = 0

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=all_fields, extrasaction="ignore")
        writer.writeheader()

        for i, row in enumerate(rows, start=1):
            website = row.get("Website", "").strip()
            domain = domain_from_url(website)
            print(f"[{i}/{len(rows)}] {row.get('Name', '')} → {domain}", end=" ")

            if args.dry_run or not domain:
                row.update({"Email": "", "FirstName": "", "LastName": "", "ContactPosition": "", "EmailConfidence": ""})
                print("(skipped)")
            else:
                emails = hunter_lookup(domain, api_key)
                best = best_email(emails)
                row.update({
                    "Email": best.get("email", ""),
                    "FirstName": best.get("first_name", ""),
                    "LastName": best.get("last_name", ""),
                    "ContactPosition": best.get("position", ""),
                    "EmailConfidence": best.get("confidence", ""),
                })
                if best.get("email"):
                    found += 1
                    print(f"✓ {best['email']}")
                else:
                    print("✗ not found")
                time.sleep(args.delay)

            writer.writerow(row)

    print(f"\nEnriched {found}/{len(rows)} leads with email.")
    print(f"Output: {out_path.resolve()}")


if __name__ == "__main__":
    main()
