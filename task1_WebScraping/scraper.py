"""
Scrapes the practice site https://books.toscrape.com (built for scraping)
and saves a custom dataset to books.csv.

Usage:
    python scraper.py                 # listing pages + detail pages
    python scraper.py --no-details    # listing pages only (fast, ~50 requests)
    python scraper.py --max-pages 5   # quick test run

Requires: requests, beautifulsoup4, pandas
"""
import argparse
import re
import time
from urllib.parse import urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup

BASE = "https://books.toscrape.com/"
HEADERS = {"User-Agent": "Mozilla/5.0 (student scraping project)"}
RATINGS = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}


def get_soup(session, url, retries=3, delay=1.0):
    """GET a URL and return BeautifulSoup, retrying on transient failures."""
    for attempt in range(1, retries + 1):
        try:
            r = session.get(url, headers=HEADERS, timeout=15)
            r.raise_for_status()
            r.encoding = "utf-8"  # site omits charset; avoids '£' mojibake
            return BeautifulSoup(r.text, "html.parser")
        except requests.RequestException as e:
            if attempt == retries:
                raise
            print(f"  retry {attempt} for {url}: {e}")
            time.sleep(delay * attempt)


def parse_listing(soup, page_url):
    """Extract basic book info from one listing page."""
    books = []
    for art in soup.select("article.product_pod"):
        a = art.h3.a
        rating_word = art.select_one("p.star-rating")["class"][1]
        price_text = art.select_one("p.price_color").text
        books.append({
            "title": a["title"],
            "price_gbp": float(re.sub(r"[^\d.]", "", price_text)),
            "rating": RATINGS.get(rating_word),
            "in_stock": "In stock" in art.select_one("p.availability").text,
            "url": urljoin(page_url, a["href"]),
        })
    return books


def parse_detail(soup):
    """Extract category, UPC and description from a book detail page."""
    crumbs = soup.select("ul.breadcrumb li a")
    category = crumbs[-1].text.strip() if len(crumbs) >= 3 else None
    table = {tr.th.text: tr.td.text for tr in soup.select("table.table-striped tr")}
    desc_tag = soup.select_one("#product_description + p")
    return {
        "category": category,
        "upc": table.get("UPC"),
        "description": desc_tag.text.strip() if desc_tag else None,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-details", action="store_true",
                        help="skip detail pages (faster)")
    parser.add_argument("--max-pages", type=int, default=50,
                        help="number of listing pages to scrape (max 50)")
    args = parser.parse_args()

    session = requests.Session()
    all_books = []

    for page in range(1, args.max_pages + 1):
        url = urljoin(BASE, f"catalogue/page-{page}.html")
        print(f"Listing page {page}/{args.max_pages}")
        try:
            soup = get_soup(session, url)
        except requests.RequestException as e:
            print(f"  stopping, could not load page {page}: {e}")
            break
        all_books.extend(parse_listing(soup, url))
        time.sleep(0.3)

    if not args.no_details:
        for i, book in enumerate(all_books, 1):
            print(f"Detail {i}/{len(all_books)}: {book['title'][:50]}")
            try:
                book.update(parse_detail(get_soup(session, book["url"])))
            except requests.RequestException as e:
                print(f"  skipped: {e}")
            time.sleep(0.2)

    df = pd.DataFrame(all_books)
    df.to_csv("books.csv", index=False, encoding="utf-8-sig")
    print(f"\nDone. Saved {len(df)} books to books.csv")


if __name__ == "__main__":
    main()
 