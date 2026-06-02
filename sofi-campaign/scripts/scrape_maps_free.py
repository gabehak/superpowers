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

QUERY_PROFILES = {
    "la": [
        "sports bar Inglewood CA",
        "restaurant Westchester CA",
        "bar Culver City CA",
        "sports bar West LA",
        "brewpub Culver City",
        "watch party venue Inglewood",
        "Iranian restaurant Westwood CA",
        "Turkish restaurant Los Angeles CA",
        "sports bar West Hollywood CA",
        "soccer bar Santa Monica CA",
        "watch party bar Marina del Rey CA",
        "sports bar El Segundo CA",
        "bar near SoFi Stadium Inglewood",
        "restaurant Hollywood Park Inglewood",
    ],
    "nyc": [
        "sports bar near MetLife Stadium NJ",
        "watch party bar East Rutherford NJ",
        "soccer bar Jersey City NJ",
        "sports bar Midtown Manhattan NY",
        "bar world cup watch party Brooklyn NY",
        "Mexican restaurant Jackson Heights Queens NY",
        "Brazilian restaurant Newark NJ",
        "bar world cup watch party Hoboken NJ",
    ],
    "dallas": [
        "sports bar near AT&T Stadium Arlington TX",
        "watch party bar Dallas TX world cup",
        "soccer bar Uptown Dallas TX",
        "Mexican restaurant Deep Ellum Dallas TX",
        "bar world cup watch party Fort Worth TX",
        "sports bar Irving TX near stadium",
    ],
    "bayarea": [
        "sports bar near Levi's Stadium Santa Clara CA",
        "watch party bar San Jose CA world cup",
        "soccer bar San Francisco CA",
        "bar world cup watch party Oakland CA",
        "Mexican restaurant San Jose CA",
        "Brazilian restaurant San Francisco CA",
    ],
    "seattle": [
        "sports bar near Lumen Field Seattle WA",
        "watch party bar Seattle WA world cup",
        "soccer bar Capitol Hill Seattle",
        "bar world cup Seattle WA",
    ],
    "boston": [
        "sports bar near Gillette Stadium Foxborough MA",
        "watch party bar Boston MA world cup",
        "soccer bar South Boston",
        "Irish pub world cup Boston MA",
    ],
    "miami": [
        "sports bar near Hard Rock Stadium Miami FL",
        "watch party bar Miami Gardens FL",
        "soccer bar Little Havana Miami",
        "Colombian restaurant Doral FL",
        "bar world cup Brickell Miami",
    ],
}

# Default: LA only. Override with --city flag.
QUERIES = QUERY_PROFILES["la"]

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
    parser.add_argument("--city", default="la",
                        choices=list(QUERY_PROFILES.keys()),
                        help=f"Host city profile. Options: {', '.join(QUERY_PROFILES)}")
    parser.add_argument("--no-details", action="store_true",
                        help="skip website/phone lookup (saves API calls)")
    args = parser.parse_args()

    global QUERIES
    QUERIES = QUERY_PROFILES[args.city]
    print(f"City profile: {args.city} ({len(QUERIES)} search queries)")

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
