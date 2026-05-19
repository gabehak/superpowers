#!/usr/bin/env python3
"""
Run Claude audit on qualified leads CSV.
Reads sofi_leads_qualified.csv (or --input), calls Firecrawl then Claude API,
writes audit results back to sofi_leads_audited.csv (or --output).

Required env vars:
  ANTHROPIC_API_KEY
  FIRECRAWL_API_KEY

Usage:
  python run_audit.py --input sofi_leads_qualified.csv --output sofi_leads_audited.csv
  python run_audit.py --dry-run  (prints first prompt, no API calls)
"""

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    import anthropic
except ImportError:
    print("ERROR: pip install anthropic", file=sys.stderr)
    sys.exit(1)

try:
    import requests
except ImportError:
    print("ERROR: pip install requests", file=sys.stderr)
    sys.exit(1)

FIRECRAWL_ENDPOINT = "https://api.firecrawl.dev/v1/scrape"
CLAUDE_MODEL = "claude-sonnet-4-6"
TOP_COMPETITOR = "Springbok Bar & Grill"  # override per-row if available

AUDIT_PROMPT_TEMPLATE = """<role>
You are a local SEO strategist auditing an LA-area hospitality business
exactly 25 days before the FIFA World Cup 2026 kickoff at SoFi Stadium
(June 12, 2026). You produce concise, evidence-based audits for
personalized cold outreach. Be brutally specific. Never fabricate data.
</role>

<context>
MATCH SCHEDULE & SEARCH PEAKS:
- June 12 (USA v Paraguay): BIGGEST SPIKE
- June 25 (USA v Turkey): HIGH TURKISH-AMERICAN SEARCH
- June 21 (Belgium v Iran): HIGH IRAN DIASPORA SEARCH

BUSINESS DATA:
Business Name: {business_name}
Location: {address}, {neighborhood}
Distance from SoFi: {distance_miles} miles (estimated)
Rating: {rating} ({review_count} reviews)
Last GBP Post: unknown
Website: {website}

FIRECRAWL WEBSITE CONTENT:
{firecrawl_content}

COMPETITIVE DATA:
Query: "{neighborhood} world cup watch party"
Your Position: unknown
Top Competitor: {top_competitor}
</context>

<task>
Produce exactly 6 sections:

1. VERDICT (1 line): "tournament_ready" | "partial" | "not_ready"
2. TOP 3 RANKING GAPS (with competitor evidence + fixability)
3. HIGHEST-LEVERAGE FIX (≤30 words, doable in 48 hours)
4. PERSONALIZATION HOOK (≤25 words, specific + verifiable)
5. ESTIMATED TRAFFIC LOSS (low/medium/high + reasoning)
6. NATIONALITY ANGLE (if applicable, else null)

Return ONLY valid JSON. No markdown, no preamble.
</task>

<output_format>
{{
  "business_name": "{business_name}",
  "neighborhood": "{neighborhood}",
  "verdict": "tournament_ready|partial|not_ready",
  "ranking_gaps": [
    {{
      "gap": "specific weakness ≤40 words",
      "evidence": "competitor X has Y, you have Z",
      "fixability_days": 1
    }}
  ],
  "highest_leverage_fix": "action ≤30 words",
  "personalization_hook": "specific detail ≤25 words",
  "estimated_traffic_loss": {{
    "level": "low|medium|high",
    "reasoning": "≤20 words"
  }},
  "nationality_angle": "string or null",
  "priority_score": 0,
  "audit_timestamp": "{timestamp}"
}}
</output_format>"""


def firecrawl_scrape(url: str, api_key: str, timeout: int = 30) -> str:
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"url": url, "formats": ["markdown"]}
    try:
        r = requests.post(FIRECRAWL_ENDPOINT, headers=headers, json=payload, timeout=timeout)
        r.raise_for_status()
        data = r.json()
        return data.get("data", {}).get("markdown", "") or ""
    except Exception as e:
        return f"[Firecrawl error: {e}]"


def claude_audit(prompt: str, client: anthropic.Anthropic) -> dict:
    message = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = message.content[0].text.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(raw[start:end])
        return {"error": "parse_failed", "raw": raw[:500]}


def build_prompt(row: dict, firecrawl_content: str) -> str:
    return AUDIT_PROMPT_TEMPLATE.format(
        business_name=row.get("Name", ""),
        address=row.get("Address", ""),
        neighborhood=row.get("Neighborhood", ""),
        distance_miles=row.get("DistanceMiles", "~3"),
        rating=row.get("Rating", ""),
        review_count=row.get("ReviewCount", ""),
        website=row.get("Website", ""),
        firecrawl_content=firecrawl_content[:3000] if firecrawl_content else "[not scraped]",
        top_competitor=TOP_COMPETITOR,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


AUDIT_OUTPUT_FIELDS = [
    "verdict", "highest_leverage_fix", "personalization_hook",
    "priority_score", "estimated_traffic_loss_level", "estimated_traffic_loss_reasoning",
    "nationality_angle", "ranking_gap_1", "ranking_gap_2", "ranking_gap_3",
    "audit_timestamp", "audit_error",
]


def flatten_audit(result: dict) -> dict:
    flat = {
        "verdict": result.get("verdict", ""),
        "highest_leverage_fix": result.get("highest_leverage_fix", ""),
        "personalization_hook": result.get("personalization_hook", ""),
        "priority_score": result.get("priority_score", ""),
        "nationality_angle": result.get("nationality_angle", ""),
        "audit_timestamp": result.get("audit_timestamp", ""),
        "audit_error": result.get("error", ""),
    }
    tl = result.get("estimated_traffic_loss", {})
    flat["estimated_traffic_loss_level"] = tl.get("level", "") if isinstance(tl, dict) else ""
    flat["estimated_traffic_loss_reasoning"] = tl.get("reasoning", "") if isinstance(tl, dict) else ""
    gaps = result.get("ranking_gaps", [])
    for i, g in enumerate(gaps[:3], start=1):
        flat[f"ranking_gap_{i}"] = g.get("gap", "") if isinstance(g, dict) else str(g)
    return flat


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="sofi_leads_qualified.csv")
    parser.add_argument("--output", default="sofi_leads_audited.csv")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=0, help="max rows to process (0=all)")
    parser.add_argument("--delay", type=float, default=2.0, help="seconds between API calls")
    args = parser.parse_args()

    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
    firecrawl_key = os.environ.get("FIRECRAWL_API_KEY", "")

    if not args.dry_run:
        if not anthropic_key:
            print("ERROR: set ANTHROPIC_API_KEY", file=sys.stderr)
            sys.exit(1)
        if not firecrawl_key:
            print("ERROR: set FIRECRAWL_API_KEY", file=sys.stderr)
            sys.exit(1)

    in_path = Path(args.input)
    if not in_path.exists():
        print(f"ERROR: {args.input} not found. Run filter_leads.py first.", file=sys.stderr)
        sys.exit(1)

    with open(in_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    if args.limit:
        rows = rows[: args.limit]

    if args.dry_run:
        sample = rows[0] if rows else {}
        prompt = build_prompt(sample, "[DRY RUN - no firecrawl call]")
        print("=== DRY RUN: first prompt ===\n")
        print(prompt)
        return

    client = anthropic.Anthropic(api_key=anthropic_key)
    out_path = Path(args.output)
    all_fields = list(rows[0].keys()) + AUDIT_OUTPUT_FIELDS

    with open(out_path, "w", newline="", encoding="utf-8") as out_f:
        writer = csv.DictWriter(out_f, fieldnames=all_fields, extrasaction="ignore")
        writer.writeheader()

        for i, row in enumerate(rows, start=1):
            website = row.get("Website", "").strip()
            print(f"[{i}/{len(rows)}] {row.get('Name', '')} — scraping {website} ...")

            content = firecrawl_scrape(website, firecrawl_key) if website else ""
            prompt = build_prompt(row, content)

            print(f"  → calling Claude ...")
            audit = claude_audit(prompt, client)
            flat = flatten_audit(audit)
            row.update(flat)
            writer.writerow(row)
            out_f.flush()

            print(f"  ✓ verdict={flat.get('verdict')} priority={flat.get('priority_score')}")
            time.sleep(args.delay)

    print(f"\nDone. Results: {out_path.resolve()}")


if __name__ == "__main__":
    main()
