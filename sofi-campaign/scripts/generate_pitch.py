#!/usr/bin/env python3
"""
Generate a 20-second in-person bar pitch from an audit CSV row.
Outputs two branches: Logistics Pain and Revenue Hunger.

Usage:
  python scripts/generate_pitch.py --row "The Tap House"
  python scripts/generate_pitch.py --row "The Tap House" --branch revenue
  python scripts/generate_pitch.py --all   # print all leads, both branches
  python scripts/generate_pitch.py --csv sofi_leads_audited.csv
"""

import argparse
import csv
import sys
from pathlib import Path

LOGISTICS_PITCH = """\
╔══ LOGISTICS PAIN BRANCH (20 sec) ════════════════════════════════╗
"Hey — with the USA match [June 12] coming, are you guys ready for
the surge? We're seeing bars near SoFi get slammed with crowds who
can't find them on Google Maps. We built a 14-day fix for that — it's
${price} and we deliver before kickoff. [Hand one-pager.]
{hook}"
╚══════════════════════════════════════════════════════════════════╝"""

REVENUE_PITCH = """\
╔══ REVENUE HUNGER BRANCH (20 sec) ════════════════════════════════╗
"Hey — quick question. When someone searches 'world cup watch party
{neighborhood}' on Google right now, {competitor} is showing up, not
you. That's {traffic_loss} walk-ins per match going to them.
We fix that in 14 days for ${price}. [Hand one-pager.]
{hook}"
╚══════════════════════════════════════════════════════════════════╝"""

TIER_PRICE = {
    "high": "1,497",
    "medium": "997",
    "low": "997",
}

DEFAULT_COMPETITOR = "the bar down the street"


def build_pitches(row: dict) -> dict:
    name = row.get("Name", "your spot")
    neighborhood = row.get("Neighborhood", "this neighborhood")
    hook = row.get("Personalization_Hook", "").strip()
    traffic = (row.get("Estimated_Traffic_Loss") or row.get("traffic_loss_level") or "medium").lower()
    price = TIER_PRICE.get(traffic, "997")
    competitor = DEFAULT_COMPETITOR

    for gap_field in ("Ranking_Gap_1", "ranking_gap_1"):
        val = row.get(gap_field, "")
        if val:
            break

    if not hook:
        hook = f"Your {name} listing hasn't been updated in a while — quick wins available."

    logistics = LOGISTICS_PITCH.format(price=price, hook=hook)
    revenue = REVENUE_PITCH.format(
        neighborhood=neighborhood,
        competitor=competitor,
        traffic_loss="40–60" if traffic == "high" else "20–40",
        price=price,
        hook=hook,
    )
    return {"name": name, "logistics": logistics, "revenue": revenue, "price": price}


def print_pitch(row: dict, branch: str = "both"):
    pitches = build_pitches(row)
    print(f"\n{'═'*66}")
    print(f"  {pitches['name'].upper()} — {row.get('Neighborhood', '')} — ${pitches['price']}/tier")
    print(f"{'═'*66}")
    if branch in ("both", "logistics"):
        print(pitches["logistics"])
    if branch in ("both", "revenue"):
        print(pitches["revenue"])


def load_csv(path: str) -> list[dict]:
    p = Path(path)
    if not p.exists():
        print(f"ERROR: {path} not found", file=sys.stderr)
        sys.exit(1)
    with open(p, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", default="sofi_leads_audited.csv",
                        help="audit CSV to read from")
    parser.add_argument("--row", default="", help="business name to filter to")
    parser.add_argument("--branch", choices=["logistics", "revenue", "both"], default="both")
    parser.add_argument("--all", action="store_true", help="print pitches for all rows")
    args = parser.parse_args()

    # Try audited first, fall back to enriched/qualified
    csv_files = [args.csv, "sofi_leads_audited.csv", "sofi_leads_enriched.csv", "sofi_leads_qualified.csv"]
    rows = []
    for f in csv_files:
        if Path(f).exists():
            rows = load_csv(f)
            break

    if not rows:
        print("ERROR: no lead CSV found. Run filter_leads.py first.", file=sys.stderr)
        sys.exit(1)

    if args.all:
        for row in rows:
            print_pitch(row, args.branch)
        return

    if args.row:
        matches = [r for r in rows if args.row.lower() in r.get("Name", "").lower()]
        if not matches:
            print(f"No match for '{args.row}'. Available names:")
            for r in rows:
                print(f"  {r.get('Name', '')}")
            sys.exit(1)
        for m in matches:
            print_pitch(m, args.branch)
        return

    # Default: show top 5 by priority score
    sorted_rows = sorted(rows, key=lambda r: int(r.get("Audit_Priority_Score") or r.get("priority_score") or 0), reverse=True)
    print(f"\nTop 5 leads by priority score — {args.branch} branch:\n")
    for row in sorted_rows[:5]:
        print_pitch(row, args.branch)


if __name__ == "__main__":
    main()
