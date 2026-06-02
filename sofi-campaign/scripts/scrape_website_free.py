#!/usr/bin/env python3
"""
Free alternative to Firecrawl — scrapes website content with requests + BeautifulSoup.
Used by run_audit_free.py. Zero cost, no API key needed.

Usage (standalone test):
  python scrape_website_free.py https://example.com
"""

import sys
import time
import re

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("pip install requests beautifulsoup4", file=sys.stderr)
    sys.exit(1)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_CHARS = 3000


def scrape(url: str, timeout: int = 15) -> str:
    if not url:
        return ""
    if not url.startswith("http"):
        url = "https://" + url
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        # Remove noise
        for tag in soup(["script", "style", "nav", "footer", "head", "noscript"]):
            tag.decompose()

        # Extract meaningful text
        chunks = []

        # Title
        title = soup.find("title")
        if title:
            chunks.append(f"TITLE: {title.get_text(strip=True)}")

        # Meta description
        meta = soup.find("meta", attrs={"name": "description"})
        if meta and meta.get("content"):
            chunks.append(f"META: {meta['content']}")

        # h1/h2
        for tag in soup.find_all(["h1", "h2"])[:8]:
            text = tag.get_text(strip=True)
            if text:
                chunks.append(f"H: {text}")

        # Body paragraphs and list items
        for tag in soup.find_all(["p", "li"])[:40]:
            text = tag.get_text(strip=True)
            if len(text) > 20:
                chunks.append(text)

        content = "\n".join(chunks)
        # Collapse whitespace
        content = re.sub(r"\n{3,}", "\n\n", content)
        return content[:MAX_CHARS]

    except Exception as e:
        return f"[scrape error: {e}]"


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "https://example.com"
    print(scrape(url))
