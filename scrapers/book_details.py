"""Visit every book's own page and add its details.

Reads data/raw/books.csv (from scrapers/books.py), opens each book's URL,
and saves data/raw/books_full.parquet.

Usage:
    uv run scrapers/book_details.py --limit 5    # test on 5 books first
    uv run scrapers/book_details.py              # all of them (~17 minutes)

Safe to stop with Ctrl+C and re-run: finished books are saved as it goes
and skipped next time.
"""

import argparse
import json
import time
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

USER_AGENT = "data-lab student project"
DELAY = 1.0
LIST_FILE = Path("data/raw/books.csv")
PROGRESS = Path("data/raw/book_details.jsonl")  # one line per finished book
OUTPUT = Path("data/raw/books_full.parquet")


def text_or_none(soup, selector):
    el = soup.select_one(selector)
    return el.get_text(" ", strip=True) if el else None


def parse_book(html: bytes, url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    row = {"url": url}

    # The "Product Information" table: each row is <tr><th>Name</th><td>Value</td></tr>.
    # Reading it as name → value works even if rows are reordered or added.
    for tr in soup.select("table tr"):
        th, td = tr.find("th"), tr.find("td")
        if th and td:
            key = th.get_text(strip=True).lower().replace(" ", "_")
            key = key.replace("(", "").replace(")", "").replace(".", "")
            row[key] = td.get_text(strip=True)

    # Breadcrumb: Home > Books > <Category> > <Title>; the category is the 3rd item
    row["category"] = text_or_none(soup, "ul.breadcrumb li:nth-of-type(3) a")
    # The description is the <p> right after the "Product Description" heading
    row["description"] = text_or_none(soup, "#product_description ~ p")
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, help="only do the first N books")
    args = ap.parse_args()

    books = pd.read_csv(LIST_FILE)
    urls = books["url"].tolist()[: args.limit]

    done = set()
    if PROGRESS.exists():
        done = {json.loads(line)["url"] for line in PROGRESS.read_text().splitlines()}
    todo = [u for u in urls if u not in done]
    print(f"{len(urls)} books, {len(done)} already done, {len(todo)} to fetch")

    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    with open(PROGRESS, "a", encoding="utf-8") as f:
        for i, url in enumerate(todo, 1):
            r = session.get(url, timeout=10)
            r.raise_for_status()
            f.write(json.dumps(parse_book(r.content, url), ensure_ascii=False) + "\n")
            f.flush()  # saved now, so Ctrl+C loses nothing
            if i % 25 == 0 or i == len(todo):
                print(f"  {i}/{len(todo)}")
            time.sleep(DELAY)

    # dtype=False keeps everything as text, so a UPC like "0012" isn't turned into 12.
    # Converting types properly is Stage 2's job.
    details = pd.read_json(PROGRESS, lines=True, dtype=False)
    full = books.merge(details, on="url", how="inner")  # join the two tables on url
    full.to_parquet(OUTPUT, index=False)

    print(f"\nSaved {len(full)} books with {len(full.columns)} columns to {OUTPUT}")
    print("\nMissing values per column:")
    print(full.isna().sum().to_string())
    print("\nOne book:")
    print(full.iloc[0].drop("description").to_string())


if __name__ == "__main__":
    main()
