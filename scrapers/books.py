"""Reusable scraper template.

Copy this file per site (e.g. scrapers/books.py), edit the SITE block,
then run from the project folder:  uv run scrapers/books.py
"""

import time
from pathlib import Path
from urllib.parse import urljoin
from urllib.robotparser import RobotFileParser

import pandas as pd
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ---------------------------------------------------------------
# EDIT THIS BLOCK FOR EACH NEW SITE
# ---------------------------------------------------------------
SITE = {
    # First page to fetch
    "start_url": "https://books.toscrape.com/catalogue/page-1.html",
    # Selector matching ONE repeated item (a card, a row, a post)
    "item": "article.product_pod",
    # Fields to pull from INSIDE each item:
    #   name: (selector, what)
    #   selector ""  = the item itself
    #   what "text"  = visible text
    #   what "attr:X" = the value of attribute X (href, src, title, class...)
    "fields": {
        "title": ("h3 a", "attr:title"),
        "price": (".price_color", "text"),
        "rating": ("p.star-rating", "attr:class"),
        "url": ("h3 a", "attr:href"),
    },
    # Selector for the "next page" link; None for a single page
    "next": "li.next a",
    "max_pages": 50,  # safety limit; raise once it works
    "delay": 1.0,  # seconds between requests (use Crawl-delay if given)
    "output": "data/raw/books.csv",
}

USER_AGENT = "data-lab student project"
# ---------------------------------------------------------------


def make_session() -> requests.Session:
    """A session that reuses connections and retries temporary errors."""
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    retry = Retry(
        total=3,
        backoff_factor=2,  # waits 2s, 4s, 8s between retries
        status_forcelist=[429, 500, 502, 503, 504],
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.mount("http://", HTTPAdapter(max_retries=retry))
    return session


def robots_allows(url: str) -> bool:
    """Check the site's robots.txt for this URL."""
    parser = RobotFileParser(urljoin(url, "/robots.txt"))
    try:
        parser.read()
    except Exception as e:
        print(f"Couldn't read robots.txt ({e}); check it by hand.")
        return False
    return parser.can_fetch(USER_AGENT, url)


def extract(item, selector: str, what: str, page_url: str):
    """Pull one field out of one item. Returns None if it isn't there."""
    el = item.select_one(selector) if selector else item
    if el is None:
        return None
    if what == "text":
        return el.get_text(" ", strip=True)
    if what.startswith("attr:"):
        name = what.removeprefix("attr:")
        value = el.get(name)
        if isinstance(value, list):  # "class" comes back as a list
            value = " ".join(value)
        if name in ("href", "src") and value:
            value = urljoin(page_url, value)  # relative → full URL
        return value
    raise ValueError(f"Unknown 'what': {what!r}")


def scrape(site: dict) -> list[dict]:
    session = make_session()
    url = site["start_url"]
    if not robots_allows(url):
        raise SystemExit(f"robots.txt disallows {url}. Stopping.")

    rows = []
    for page in range(1, site["max_pages"] + 1):
        print(f"Page {page}: {url}")
        response = session.get(url, timeout=10)
        response.raise_for_status()
        # .content (bytes) lets BeautifulSoup detect the encoding itself
        soup = BeautifulSoup(response.content, "html.parser")

        items = soup.select(site["item"])
        if not items:
            print("  0 items: wrong 'item' selector, or JavaScript-drawn page.")
            break
        for item in items:
            row = {
                name: extract(item, selector, what, url)
                for name, (selector, what) in site["fields"].items()
            }
            row["source_page"] = url
            rows.append(row)
        print(f"  {len(items)} items")

        next_link = soup.select_one(site["next"]) if site["next"] else None
        if next_link is None or not next_link.get("href"):
            break
        url = urljoin(url, next_link["href"])
        time.sleep(site["delay"])
    return rows


def main():
    rows = scrape(SITE)
    df = pd.DataFrame(rows)
    out = Path(SITE["output"])
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)

    print(f"\nSaved {len(df)} rows to {out}")
    if not df.empty:
        print("\nMissing values per column (high = check that selector):")
        print(df.isna().sum().to_string())
        print("\nFirst rows:")
        print(df.head().to_string())


if __name__ == "__main__":
    main()
