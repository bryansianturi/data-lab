"""Test a CSS selector against a page, the way requests sees it.

Usage:
    uv run try_selector.py <url> "<css selector>"
Example:
    uv run try_selector.py https://books.toscrape.com "article.product_pod h3 a"
"""

import sys

import requests
from bs4 import BeautifulSoup

USER_AGENT = "data-lab student project"

if len(sys.argv) != 3:
    sys.exit(__doc__)

url, selector = sys.argv[1], sys.argv[2]
r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=10)
print(f"HTTP {r.status_code}, {len(r.content):,} bytes")

soup = BeautifulSoup(r.content, "html.parser")
matches = soup.select(selector)
print(f"{len(matches)} match(es) for {selector!r}\n")

for el in matches[:5]:
    text = el.get_text(" ", strip=True)[:80]
    print(f"<{el.name}> text: {text!r}")
    print(f"      attrs: {dict(el.attrs)}\n")

if not matches:
    print("No matches. Either the selector is wrong, or the content is drawn")
    print("by JavaScript (check View Page Source, Step 2).")
