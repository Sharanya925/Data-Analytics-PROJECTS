import re, time, argparse
from urllib.parse import urljoin
import requests, pandas as pd
from bs4 import BeautifulSoup

BASE = "https://books.toscrape.com/catalogue/"
RATING = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}
S = requests.Session()
S.headers["User-Agent"] = "student-scraper/1.0 (educational project)"

def soup(url):
    for i in range(3):
        try:
            r = S.get(url, timeout=15)
            r.raise_for_status()
            r.encoding = "utf-8"
            return BeautifulSoup(r.text, "lxml")
        except requests.RequestException:
            time.sleep(1 + i)
    raise RuntimeError("failed: " + url)

def details(url):
    s = soup(url)
    crumbs = s.select("ul.breadcrumb li a")
    t = {r.th.text: r.td.text for r in s.select("table.table-striped tr")}
    m = re.search(r"\((\d+) available\)", t.get("Availability", ""))
    d = s.select_one("#product_description ~ p")
    return {"category": crumbs[2].text.strip() if len(crumbs) > 2 else None,
            "upc": t.get("UPC"),
            "num_reviews": int(t.get("Number of reviews", 0)),
            "stock_count": int(m.group(1)) if m else 0,
            "description_len": len(d.text.strip()) if d else 0}

ap = argparse.ArgumentParser()
ap.add_argument("--max-pages", type=int)
ap.add_argument("--no-details", action="store_true")
ap.add_argument("--out", default="books.csv")
a = ap.parse_args()
import os; os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)

rows, url, page = [], BASE + "page-1.html", 0
while url and (a.max_pages is None or page < a.max_pages):
    page += 1
    s = soup(url)
    for p in s.select("article.product_pod"):
        link = p.h3.a
        cls = [c for c in p.select_one("p.star-rating")["class"] if c != "star-rating"]
        price = p.select_one("p.price_color").text
        rows.append({"title": link["title"],
                     "price_gbp": float(re.sub(r"[^\d.]", "", price)),
                     "rating": RATING.get(cls[0]),
                     "in_stock_listing": "In stock" in p.select_one("p.instock").text,
                     "url": urljoin(url, link["href"])})
    print(f"page {page}: total {len(rows)} books")
    nxt = s.select_one("li.next a")
    url = urljoin(url, nxt["href"]) if nxt else None
    time.sleep(0.3)

if not a.no_details:
    for i, r in enumerate(rows, 1):
        r.update(details(r["url"]))
        if i % 50 == 0:
            print(f"details: {i}/{len(rows)}")
        time.sleep(0.3)

pd.DataFrame(rows).to_csv(a.out, index=False, encoding="utf-8")
print(f"Saved {len(rows)} rows to {a.out}")