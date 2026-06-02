#!/usr/bin/env python3
"""
Normalize any location CSV into the pipeline's standard schema before filtering.

Supports:
  - StoreLocatorWidgets bulk export
  - Apify Google Maps Scraper output
  - Google Places API export
  - Generic/manual CSV (column mapping printed if unrecognized)

Usage:
  python scripts/normalize_csv.py stores_export.csv apify_raw.csv
  python scripts/normalize_csv.py --detect stores_export.csv   # just show detected format
  python normalize_csv.py input.csv                            # output to stdout
"""

import argparse
import csv
import io
import sys
from pathlib import Path

# ── Standard pipeline schema ─────────────────────────────────────────────────
STANDARD_FIELDS = ["Name", "Address", "Website", "Phone", "Rating", "ReviewCount", "PlaceId"]

# ── Column mappings per source format ────────────────────────────────────────

# StoreLocatorWidgets bulk export columns (varies slightly by account config)
SLW_MAPS = {
    # their col name          → standard field
    "Store Name":             "Name",
    "store_name":             "Name",
    "name":                   "Name",
    "title":                  "Name",
    "Address Line 1":         "_addr1",
    "address":                "_addr1",
    "address1":               "_addr1",
    "Address Line 2":         "_addr2",
    "address2":               "_addr2",
    "City":                   "_city",
    "city":                   "_city",
    "State":                  "_state",
    "state":                  "_state",
    "Zip":                    "_zip",
    "zip":                    "_zip",
    "postal":                 "_zip",
    "postal_code":            "_zip",
    "Country":                "_country",
    "country":                "_country",
    "Phone":                  "Phone",
    "phone":                  "Phone",
    "phone_number":           "Phone",
    "URL":                    "Website",
    "url":                    "Website",
    "website":                "Website",
    "Website":                "Website",
    "web":                    "Website",
    "Rating":                 "Rating",
    "rating":                 "Rating",
    "Reviews":                "ReviewCount",
    "review_count":           "ReviewCount",
    "ReviewCount":            "ReviewCount",
    "Place ID":               "PlaceId",
    "place_id":               "PlaceId",
    "PlaceId":                "PlaceId",
    "id":                     "PlaceId",
    "store_id":               "PlaceId",
    "Latitude":               "_lat",
    "latitude":               "_lat",
    "lat":                    "_lat",
    "Longitude":              "_lng",
    "longitude":              "_lng",
    "lng":                    "_lng",
    "lon":                    "_lng",
}

# Apify output — already correct, just pass through
APIFY_SIGNATURE = {"Name", "Address", "Website", "Phone", "Rating", "ReviewCount", "PlaceId"}

# Google Places export
GPLACES_MAPS = {
    "name":               "Name",
    "formatted_address":  "Address",
    "website":            "Website",
    "formatted_phone_number": "Phone",
    "rating":             "Rating",
    "user_ratings_total": "ReviewCount",
    "place_id":           "PlaceId",
}


def detect_format(headers: list[str]) -> str:
    header_set = set(h.strip() for h in headers)

    if APIFY_SIGNATURE.issubset(header_set):
        return "apify"

    gplaces_hits = sum(1 for h in header_set if h in GPLACES_MAPS)
    if gplaces_hits >= 4:
        return "gplaces"

    slw_hits = sum(1 for h in header_set if h in SLW_MAPS)
    if slw_hits >= 2:
        return "slw"

    return "unknown"


def build_address(parts: dict) -> str:
    addr1 = parts.get("_addr1", "").strip()
    addr2 = parts.get("_addr2", "").strip()
    city  = parts.get("_city",  "").strip()
    state = parts.get("_state", "").strip()
    zip_  = parts.get("_zip",   "").strip()

    components = [addr1]
    if addr2:
        components.append(addr2)
    city_state = ", ".join(filter(None, [city, state]))
    if city_state:
        components.append(city_state)
    if zip_:
        components.append(zip_)
    return " ".join(components)


def normalize_row(raw: dict, col_map: dict) -> dict:
    """Apply column mapping, collect address parts, build Address string."""
    out = {f: "" for f in STANDARD_FIELDS}
    parts = {}

    for src_col, val in raw.items():
        target = col_map.get(src_col.strip())
        if not target:
            continue
        if target.startswith("_"):
            parts[target] = val.strip()
        elif target in STANDARD_FIELDS:
            if not out[target]:   # first match wins
                out[target] = val.strip()

    if parts and not out["Address"]:
        out["Address"] = build_address(parts)

    return out


def get_col_map(fmt: str) -> dict:
    if fmt == "apify":
        return {f: f for f in STANDARD_FIELDS}
    if fmt == "gplaces":
        return GPLACES_MAPS
    return SLW_MAPS  # slw + unknown both use the widest map


def normalize(input_path: str, output_path: str | None = None) -> tuple[str, int]:
    in_path = Path(input_path)
    if not in_path.exists():
        print(f"ERROR: {input_path} not found", file=sys.stderr)
        sys.exit(1)

    with open(in_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        raw_rows = list(reader)
        headers = reader.fieldnames or []

    fmt = detect_format(headers)
    col_map = get_col_map(fmt)

    normalized = [normalize_row(r, col_map) for r in raw_rows]

    out_buf = io.StringIO()
    writer = csv.DictWriter(out_buf, fieldnames=STANDARD_FIELDS)
    writer.writeheader()
    writer.writerows(normalized)
    csv_text = out_buf.getvalue()

    if output_path:
        Path(output_path).write_text(csv_text, encoding="utf-8")
    else:
        sys.stdout.write(csv_text)

    return fmt, len(normalized)


def main():
    parser = argparse.ArgumentParser(
        description="Normalize any location CSV into the SoFi pipeline schema."
    )
    parser.add_argument("input", help="Input CSV (StoreLocatorWidgets, Apify, Google Places, etc.)")
    parser.add_argument("output", nargs="?", default=None,
                        help="Output CSV (default: stdout). Use apify_raw.csv to plug into pipeline.")
    parser.add_argument("--detect", action="store_true",
                        help="Only detect and print the format, don't convert")
    args = parser.parse_args()

    if args.detect:
        with open(args.input, newline="", encoding="utf-8-sig") as f:
            headers = csv.DictReader(f).fieldnames or []
        fmt = detect_format(headers)
        print(f"Detected format: {fmt}")
        print(f"Headers: {headers}")
        if fmt == "unknown":
            print("\nUnrecognized columns. To add support, map them in SLW_MAPS in this script.")
            print("Paste your header row here and I'll write the mapping for you.")
        return

    fmt, count = normalize(args.input, args.output)
    dest = args.output or "stdout"
    print(f"✓ Format detected: {fmt}", file=sys.stderr)
    print(f"✓ {count} rows normalized → {dest}", file=sys.stderr)
    if args.output:
        print(f"\nNext: python scripts/filter_leads.py {args.output} sofi_leads_qualified.csv",
              file=sys.stderr)


if __name__ == "__main__":
    main()
