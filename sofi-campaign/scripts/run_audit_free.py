#!/usr/bin/env python3
"""
Free alternative to run_audit.py — uses Groq (free tier) instead of Claude API,
and scrape_website_free.py instead of Firecrawl.

Free tiers available:
  - Groq: groq.com → free API key, fast Llama-3/Mixtral inference
  - Google Gemini: aistudio.google.com → free API key, 15 RPM free
  - Ollama: ollama.ai → fully local, no key needed, runs on your machine

Setup:
  Option A (Groq — recommended, fastest):
    export GROQ_API_KEY=gsk_...   # free at groq.com

  Option B (Gemini):
    export GEMINI_API_KEY=...     # free at aistudio.google.com

  Option C (Ollama — fully offline):
    ollama pull llama3             # one-time download
    (no env var needed)

Usage:
  python run_audit_free.py --input sofi_leads_enriched.csv --provider groq
  python run_audit_free.py --input sofi_leads_enriched.csv --provider gemini
  python run_audit_free.py --input sofi_leads_enriched.csv --provider ollama
  python run_audit_free.py --dry-run
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
    import requests
except ImportError:
    print("pip install requests", file=sys.stderr)
    sys.exit(1)

try:
    from scrape_website_free import scrape as firecrawl_free
except ImportError:
    def firecrawl_free(url):
        return "[scraper not available]"

TOP_COMPETITOR = "Springbok Bar & Grill"

AUDIT_PROMPT = """You are a local SEO strategist auditing an LA-area restaurant near SoFi Stadium 10 days before the FIFA World Cup 2026 kickoff (June 12, 2026). Produce concise, evidence-based audits for cold outreach. Be specific. Never fabricate.

BUSINESS: {business_name}
LOCATION: {address}, {neighborhood}
RATING: {rating} ({review_count} reviews)
WEBSITE CONTENT:
{content}
COMPETITOR: {top_competitor}
QUERY: "{neighborhood} world cup watch party"

Return ONLY valid JSON matching this exact schema:
{{"business_name":"{business_name}","neighborhood":"{neighborhood}","verdict":"not_ready|partial|tournament_ready","ranking_gaps":[{{"gap":"≤40 words","evidence":"competitor vs you","fixability_days":1}}],"highest_leverage_fix":"≤30 words","personalization_hook":"≤25 words specific detail","estimated_traffic_loss":{{"level":"low|medium|high","reasoning":"≤20 words"}},"nationality_angle":"string or null","priority_score":0,"audit_timestamp":"{timestamp}"}}"""


# ── Provider implementations ────────────────────────────────────────────────

def call_groq(prompt: str, api_key: str) -> str:
    r = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": "llama-3.3-70b-versatile",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 800,
            "temperature": 0.2,
        },
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def call_gemini(prompt: str, api_key: str) -> str:
    r = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}",
        json={"contents": [{"parts": [{"text": prompt}]}],
              "generationConfig": {"temperature": 0.2, "maxOutputTokens": 800}},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["candidates"][0]["content"]["parts"][0]["text"]


def call_ollama(prompt: str, model: str = "llama3") -> str:
    r = requests.post(
        "http://localhost:11434/api/generate",
        json={"model": model, "prompt": prompt, "stream": False},
        timeout=120,
    )
    r.raise_for_status()
    return r.json()["response"]


def call_llm(prompt: str, provider: str, **kwargs) -> str:
    if provider == "groq":
        return call_groq(prompt, kwargs["groq_key"])
    if provider == "gemini":
        return call_gemini(prompt, kwargs["gemini_key"])
    if provider == "ollama":
        return call_ollama(prompt, kwargs.get("ollama_model", "llama3"))
    raise ValueError(f"Unknown provider: {provider}")


def parse_json(raw: str) -> dict:
    raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start, end = raw.find("{"), raw.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(raw[start:end])
            except Exception:
                pass
    return {"error": "parse_failed", "raw": raw[:300]}


def flatten(result: dict) -> dict:
    tl = result.get("estimated_traffic_loss") or {}
    gaps = result.get("ranking_gaps") or []
    flat = {
        "verdict": result.get("verdict", ""),
        "highest_leverage_fix": result.get("highest_leverage_fix", ""),
        "personalization_hook": result.get("personalization_hook", ""),
        "priority_score": result.get("priority_score", ""),
        "nationality_angle": result.get("nationality_angle", ""),
        "audit_timestamp": result.get("audit_timestamp", ""),
        "audit_error": result.get("error", ""),
        "estimated_traffic_loss_level": tl.get("level", "") if isinstance(tl, dict) else "",
        "estimated_traffic_loss_reasoning": tl.get("reasoning", "") if isinstance(tl, dict) else "",
    }
    for i, g in enumerate(gaps[:3], 1):
        flat[f"ranking_gap_{i}"] = (g.get("gap", "") if isinstance(g, dict) else str(g))
    return flat


AUDIT_OUTPUT_FIELDS = [
    "verdict", "highest_leverage_fix", "personalization_hook", "priority_score",
    "estimated_traffic_loss_level", "estimated_traffic_loss_reasoning",
    "nationality_angle", "ranking_gap_1", "ranking_gap_2", "ranking_gap_3",
    "audit_timestamp", "audit_error",
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="sofi_leads_enriched.csv")
    parser.add_argument("--output", default="sofi_leads_audited.csv")
    parser.add_argument("--provider", choices=["groq", "gemini", "ollama"], default="groq")
    parser.add_argument("--ollama-model", default="llama3")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--delay", type=float, default=1.5)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    groq_key = os.environ.get("GROQ_API_KEY", "")
    gemini_key = os.environ.get("GEMINI_API_KEY", "")

    if not args.dry_run:
        if args.provider == "groq" and not groq_key:
            print("ERROR: set GROQ_API_KEY (free at groq.com)", file=sys.stderr)
            sys.exit(1)
        if args.provider == "gemini" and not gemini_key:
            print("ERROR: set GEMINI_API_KEY (free at aistudio.google.com)", file=sys.stderr)
            sys.exit(1)

    in_path = Path(args.input)
    if not in_path.exists():
        print(f"ERROR: {args.input} not found", file=sys.stderr)
        sys.exit(1)

    with open(in_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if args.limit:
        rows = rows[:args.limit]

    if args.dry_run:
        row = rows[0] if rows else {}
        prompt = AUDIT_PROMPT.format(
            business_name=row.get("Name", ""),
            address=row.get("Address", ""),
            neighborhood=row.get("Neighborhood", ""),
            rating=row.get("Rating", ""),
            review_count=row.get("ReviewCount", ""),
            content="[DRY RUN]",
            top_competitor=TOP_COMPETITOR,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        print(f"Provider: {args.provider}\n")
        print(prompt)
        return

    out_path = Path(args.output)
    all_fields = list(rows[0].keys()) + AUDIT_OUTPUT_FIELDS

    with open(out_path, "w", newline="", encoding="utf-8") as out_f:
        writer = csv.DictWriter(out_f, fieldnames=all_fields, extrasaction="ignore")
        writer.writeheader()

        for i, row in enumerate(rows, 1):
            website = row.get("Website", "").strip()
            print(f"[{i}/{len(rows)}] {row.get('Name', '')} — scraping ...")
            content = firecrawl_free(website) if website else ""

            prompt = AUDIT_PROMPT.format(
                business_name=row.get("Name", ""),
                address=row.get("Address", ""),
                neighborhood=row.get("Neighborhood", ""),
                rating=row.get("Rating", ""),
                review_count=row.get("ReviewCount", ""),
                content=content[:2500],
                top_competitor=TOP_COMPETITOR,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

            print(f"  → calling {args.provider} ...")
            raw = call_llm(prompt, args.provider,
                           groq_key=groq_key, gemini_key=gemini_key,
                           ollama_model=args.ollama_model)
            result = parse_json(raw)
            row.update(flatten(result))
            writer.writerow(row)
            out_f.flush()
            print(f"  ✓ verdict={row.get('verdict')} priority={row.get('priority_score')}")
            time.sleep(args.delay)

    print(f"\nDone → {out_path.resolve()}")


if __name__ == "__main__":
    main()
