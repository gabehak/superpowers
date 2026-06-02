#!/usr/bin/env python3
"""
Free alternative to Apify — scrapes Google Maps via Google Places API.
Google gives $200 free credit/month (~6,000 Nearby Search calls free).

Setup (one-time, free):
  1. console.cloud.google.com → New Project
  2. Enable "Places API"
  3. APIs & Services → Credentials → Create API Key
  4. export GOOGLE_PLACES_API_KEY=your_key

Usage:
  python scrape_maps_free.py --output apify_raw.csv
"""

import argparse
import csv
import os
import sys
import time

try:
    import requests
except ImportError:
    print("pip install requests", file=sys.stderr)
    sys.exit(1)

PLACES_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
DETAIL_URL = "https://maps.googleapis.com/maps/api/place/details/json"

QUERIES = [
    "sports bar Inglewood CA",
    "restaurant Westchester CA",
    "bar Culver City CA",
    "sports bar West LA",
    "brewpub Culver City",
    "watch party venue Inglewood",
    "Iranian restaurant Westwood CA",
    "Turkish restaurant Los Angeles CA",
]

OUTPUT_FIELDS = ["Name", "Address", "Website", "Phone", "Rating", "ReviewCount", "PlaceId"]


def search(query: str, api_key: str) -> list[dict]:
    results = []
    params = {"query": query, "key": api_key}
    while True:
        r = requests.get(PLACES_URL, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
        results.extend(data.get("results", []))
        token = data.get("next_page_token")
        if not token:
            break
        params["pagetoken"] = token
        time.sleep(2)  # Google requires delay before using next_page_token
    return results


def get_website(place_id: str, api_key: str) -> str:
    params = {"place_id": place_id, "fields": "website,formatted_phone_number", "key": api_key}
    r = requests.get(DETAIL_URL, params=params, timeout=10)
    r.raise_for_status()
    data = r.json().get("result", {})
    return data.get("website", ""), data.get("formatted_phone_number", "")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="apify_raw.csv")
    parser.add_argument("--no-details", action="store_true",
                        help="skip website/phone lookup (saves API calls)")
    args = parser.parse_args()

    api_key = os.environ.get("GOOGLE_PLACES_API_KEY", "")
    if not api_key:
        print("ERROR: set GOOGLE_PLACES_API_KEY\n"
              "Get one free at console.cloud.google.com → Places API → Credentials", file=sys.stderr)
        sys.exit(1)

    seen = set()
    rows = []

    for query in QUERIES:
        print(f"Searching: {query}")
        try:
            results = search(query, api_key)
        except Exception as e:
            print(f"  ERROR: {e}")
            continue

        for place in results:
            pid = place.get("place_id", "")
            if pid in seen:
                continue
            seen.add(pid)

            website, phone = "", ""
            if not args.no_details and pid:
                try:
                    website, phone = get_website(pid, api_key)
                    time.sleep(0.1)
                except Exception:
                    pass

            rows.append({
                "Name": place.get("name", ""),
                "Address": place.get("formatted_address", ""),
                "Website": website,
                "Phone": phone or place.get("formatted_phone_number", ""),
                "Rating": place.get("rating", ""),
                "ReviewCount": place.get("user_ratings_total", ""),
                "PlaceId": pid,
            })

        print(f"  → {len(results)} results (total unique: {len(rows)})")
        time.sleep(1)

    with open(args.output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n✓ {len(rows)} places saved to {args.output}")
    print("Next: python scripts/filter_leads.py apify_raw.csv sofi_leads_qualified.csv")


if __name__ == "__main__":
    main()
