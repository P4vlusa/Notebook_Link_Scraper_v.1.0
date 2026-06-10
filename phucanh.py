# -*- coding: utf-8 -*-
"""
PhucAnh laptop crawler (stable version)
- Crawl all laptop brands
- Extract product name + URL
- Save to output/phucanh.csv
"""

import os
import time
import csv
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

BASE = "https://www.phucanh.vn"

BRANDS = [
    "/may-tinh-xach-tay-laptop-dell.html",
    "/may-tinh-xach-tay-laptop-asus.html",
    "/laptop-lg.html",
    "/may-tinh-xach-tay-laptop-hp.html",
    "/may-tinh-xach-tay-laptop-acer.html",
    "/may-tinh-xach-tay-laptop-lenovo.html",
    "/may-tinh-xach-tay-laptop-msi.html",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}


def fetch(url):
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    r.encoding = "utf-8"
    return BeautifulSoup(r.text, "html.parser")


def extract_products(listing_url):
    results = []
    page = 1

    while True:
        url = listing_url if page == 1 else f"{listing_url}?page={page}"
        print(f"[INFO] Fetching: {url}")

        try:
            soup = fetch(url)
        except:
            break

        # Sản phẩm nằm trong div.product-item
        items = soup.select(".product-item")
        if not items:
            break

        count = 0
        for item in items:
            a = item.select_one(".p-name a, h3 a, .product-name a")
            if not a:
                continue

            name = a.get_text(strip=True)
            href = a.get("href")

            if not href or not name:
                continue

            full = urljoin(BASE, href)

            # Chỉ lấy laptop thật
            if "laptop" not in name.lower() and "xách tay" not in name.lower():
                continue

            results.append({"name": name, "url": full})
            count += 1

        print(f"  -> Found {count} items on page {page}")

        if count == 0:
            break

        page += 1
        time.sleep(0.5)

    return results


def main():
    all_items = []
    seen = set()

    for brand in BRANDS:
        listing_url = BASE + brand
        print(f"\n=== Crawling brand: {listing_url} ===")
        items = extract_products(listing_url)

        for it in items:
            if it["url"] not in seen:
                seen.add(it["url"])
                all_items.append(it)

    os.makedirs("output", exist_ok=True)
    out_file = "output/phucanh.csv"

    with open(out_file, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "url"])
        writer.writeheader()
        writer.writerows(all_items)

    print(f"\n[DONE] Collected {len(all_items)} products → {out_file}")


if __name__ == "__main__":
    main()
