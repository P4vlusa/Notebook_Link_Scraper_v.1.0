import csv
import re
import time
import os
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://laptop88.vn/may-tinh-xach-tay.html"
DOMAIN = "https://laptop88.vn"
PRODUCT_HREF_RE = re.compile(r"/new-100-[a-z0-9\-]+", re.IGNORECASE)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36"
}

def fetch(url, retries=3, timeout=20):
    for attempt in range(1, retries + 1):
        try:
            r = requests.get(url, headers=HEADERS, timeout=timeout)
            r.raise_for_status()
            r.encoding = r.apparent_encoding or "utf-8"
            return r.text
        except requests.RequestException:
            if attempt == retries:
                raise
            time.sleep(1.2 * attempt)

def parse_products(html):
    soup = BeautifulSoup(html, "html.parser")
    products = []
    seen = set()

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if PRODUCT_HREF_RE.search(href):
            url = urljoin(DOMAIN, href)
            name = a.get_text(strip=True)

            if not name or len(name) < 5:
                parent = a.parent
                if parent:
                    heading = parent.find(["h2", "h3", "h4"])
                    if heading:
                        name = heading.get_text(strip=True)

            if url not in seen and name:
                seen.add(url)
                products.append({"Product Name": name, "URL": url})
    return products

def crawl_all_pages():
    all_items = []
    seen_urls = set()

    page = 1
    while True:
        url = BASE_URL if page == 1 else f"{BASE_URL}?page={page}"
        html = fetch(url)
        items = parse_products(html)

        new_items = [it for it in items if it["URL"] not in seen_urls]
        for it in new_items:
            seen_urls.add(it["URL"])

        if not new_items:
            break

        all_items.extend(new_items)
        page += 1
        time.sleep(0.8)

    return all_items

def save_csv(rows):
    os.makedirs("output", exist_ok=True)
    path = "output/laptop88.csv"

    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["Product Name", "URL"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"✅ Saved {len(rows)} items to {path}")

if __name__ == "__main__":
    items = crawl_all_pages()
    save_csv(items)
