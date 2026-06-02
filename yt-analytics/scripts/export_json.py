#!/usr/bin/env python3
"""
Export analyzed comments to data.json for the dashboard.
Run after analyze.py.

Usage:
  python scripts/export_json.py
  python scripts/export_json.py --input outputs/comments_raw.csv --output site/data.json
"""

import csv
import json
import os
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
OUTPUT_DIR = ROOT / "outputs"
SITE_DIR = ROOT / "site"


def load_csv(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=str(OUTPUT_DIR / "comments_raw.csv"))
    parser.add_argument("--output", default=str(SITE_DIR / "data.json"))
    args = parser.parse_args()

    comments_path = Path(args.input)
    if not comments_path.exists():
        print(f"ERROR: {comments_path} not found. Run pull_comments.py first.", file=sys.stderr)
        sys.exit(1)

    comments = load_csv(comments_path)
    print(f"Loaded {len(comments)} comments")

    # Sentiment
    sentiment = Counter()
    categories = Counter()
    for c in comments:
        cat = c.get("category", "general")
        categories[cat] += 1
        if cat == "positive_feedback":
            sentiment["positive"] += 1
        elif cat == "question":
            sentiment["question"] += 1
        elif cat == "issue_report":
            sentiment["negative"] += 1
        else:
            sentiment["neutral"] += 1

    # Tools
    tool_keywords = [
        "claude", "chatgpt", "gpt-4", "gemini", "cursor", "copilot",
        "airtable", "notion", "zapier", "make", "n8n", "vercel",
        "python", "javascript", "typescript", "api", "github", "codex",
        "anthropic", "openai", "ollama", "groq",
    ]
    tools = Counter()
    for c in comments:
        text = c.get("text", "").lower()
        for t in tool_keywords:
            if t in text:
                tools[t.title()] += 1

    # Videos
    videos = list({c.get("video_title", "") for c in comments if c.get("video_title")})

    # Top liked
    sorted_by_likes = sorted(comments, key=lambda x: int(x.get("likes", 0) or 0), reverse=True)
    priority = [c.get("text", "")[:200] for c in sorted_by_likes[:5]]

    # Questions
    questions = [c.get("text", "")[:180] for c in comments if c.get("category") == "question"][:10]
    requests = [c.get("text", "")[:180] for c in comments if c.get("category") == "content_request"][:10]

    # Key themes (simple)
    theme_map = {
        "Beginner questions": ["beginner", "getting started", "how do i", "new to"],
        "Tool comparisons": ["vs ", "versus", "better than", "difference between", "compare"],
        "Pricing / cost": ["free", "cost", "price", "pay", "subscription", "tier"],
        "Workflow / automation": ["workflow", "automat", "system", "process"],
        "Positive feedback": ["thank", "amazing", "great", "love", "helpful", "best"],
    }
    theme_counts = {}
    for theme, keywords in theme_map.items():
        count = sum(1 for c in comments if any(k in c.get("text", "").lower() for k in keywords))
        if count > 0:
            theme_counts[theme] = count

    # Prep comment objects for dashboard
    dash_comments = []
    for c in sorted_by_likes[:500]:
        dash_comments.append({
            "author": c.get("author", ""),
            "video": c.get("video_title", "")[:60],
            "text": c.get("text", ""),
            "likes": int(c.get("likes", 0) or 0),
            "category": c.get("category", "general"),
            "url": c.get("url", ""),
        })

    data = {
        "generated": datetime.utcnow().isoformat() + "Z",
        "total_comments": len(comments),
        "videos_analyzed": len(videos),
        "total_likes": sum(int(c.get("likes", 0) or 0) for c in comments),
        "sentiment": dict(sentiment),
        "categories": dict(categories),
        "key_themes": list(theme_counts.keys()),
        "theme_counts": list(theme_counts.values()),
        "top_tools": dict(tools.most_common(12)),
        "creator_insights": [
            "Reply to top-liked questions first — they drive the most engagement signal",
            f"Questions are {sentiment['question']/max(len(comments),1)*100:.0f}% of comments — your audience wants answers, not just tutorials",
            "High tool-mention rate suggests a technical audience ready to buy tools/courses",
        ],
        "top_questions": questions,
        "content_requests": requests,
        "priority_replies": priority,
        "comments": dash_comments,
    }

    SITE_DIR.mkdir(exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"✓ data.json written to {args.output}")
    print("Next: open site/index.html in a browser, or deploy with Netlify/Vercel")


if __name__ == "__main__":
    main()
