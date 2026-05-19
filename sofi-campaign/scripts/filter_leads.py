#!/usr/bin/env python3
"""
Filter raw Apify Google Maps scrape output to qualified SoFi leads.
Input:  CSV with columns: Name, Address, Website, Phone, Rating, ReviewCount, PlaceId
Output: sofi_leads_qualified.csv (ready for Airtable import)
"""

import csv
import sys
import re
from pathlib import Path

CHAIN_BLACKLIST = {
    "applebee", "chili's", "chilis", "buffalo wild wings", "bdubs",
    "denny's", "dennys", "ihop", "mcdonald", "burger king", "wendy",
    "taco bell", "subway", "domino", "pizza hut", "kfc", "popeye",
    "jack in the box", "in-n-out", "in n out", "panda express",
    "chipotle", "starbucks", "dunkin", "olive garden", "red lobster",
    "cheesecake factory", "hooters", "twin peaks", "dave & buster",
    "dave and buster", "wingstop", "raising cane", "shake shack",
}

MIN_REVIEWS = 20
MIN_RATING = 3.5

SOFI_NEIGHBORHOODS = [
    "Inglewood", "Westchester", "Culver City", "West LA",
    "West Los Angeles", "Westwood", "Marina del Rey", "El Segundo",
]


def is_chain(name: str) -> bool:
    name_lower = name.lower()
    return any(chain in name_lower for chain in CHAIN_BLACKLIST)


def qualify(row: dict) -> bool:
    if not row.get("Website", "").strip():
        return False
    try:
        rating = float(row.get("Rating", 0) or 0)
        reviews = int(row.get("ReviewCount", 0) or 0)
    except (ValueError, TypeError):
        return False
    if rating < MIN_RATING:
        return False
    if reviews < MIN_REVIEWS:
        return False
    if is_chain(row.get("Name", "")):
        return False
    return True


def detect_neighborhood(address: str) -> str:
    for n in SOFI_NEIGHBORHOODS:
        if n.lower() in address.lower():
            return n
    return "Other"


def main(input_file: str, output_file: str = "sofi_leads_qualified.csv"):
    path = Path(input_file)
    if not path.exists():
        print(f"ERROR: {input_file} not found", file=sys.stderr)
        sys.exit(1)

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    qualified = [r for r in rows if qualify(r)]

    for row in qualified:
        row["Neighborhood"] = detect_neighborhood(row.get("Address", ""))
        row["Status"] = "not_contacted"
        row["Audit_Completed"] = "false"
        row["Deal_Closed"] = "false"

    output_fields = [
        "Name", "Address", "Neighborhood", "Website", "Phone",
        "Rating", "ReviewCount", "PlaceId",
        "Status", "Audit_Completed", "Deal_Closed",
    ]

    out_path = Path(output_file)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=output_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(qualified)

    total = len(rows)
    kept = len(qualified)
    print(f"Input:     {total} rows")
    print(f"Qualified: {kept} rows ({kept/total*100:.1f}%)")
    print(f"Output:    {out_path.resolve()}")

    breakdown = {}
    for r in qualified:
        n = r["Neighborhood"]
        breakdown[n] = breakdown.get(n, 0) + 1
    print("\nBy neighborhood:")
    for n, c in sorted(breakdown.items(), key=lambda x: -x[1]):
        print(f"  {n}: {c}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python filter_leads.py <apify_output.csv> [output.csv]")
        sys.exit(1)
    main(*sys.argv[1:])
