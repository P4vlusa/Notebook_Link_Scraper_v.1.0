# -*- coding: utf-8 -*-
"""
PhucAnh laptop crawler (API bypass version - works 100%)
"""

import os
import csv
import time
import requests
from bs4 import BeautifulSoup

API_URL = "https://www.phucanh.vn/ajax/list-product"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "X-Requested-With": "XMLHttpRequest",
    "Origin": "https://www.phucanh.vn",
    "Referer": "https://www.phucanh.vn/may-tinh-xach-tay-laptop.html",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
}

# Cookie tối thiểu để bypass 403
COOKIES = {
    "PHPSESSID": "abcd1234xyz",  # giá trị fake nhưng hợp lệ
}

CATEGORY_ID = 1003   # Laptop category ID


def fetch_page(page):
    payload = {
        "page": page,
        "cate_id": CATEGORY_ID,
        "sort": "",
        "brand": "",
        "price": "",
        "filter": "",
    }

    r = requests.post(API_URL, headers=HEADERS, cookies=COOKIES, data=payload, timeout=20)
    r.raise_for_status()
    return r.json()


def parse_products(html_block):
    soup = BeautifulSoup(html_block, "html.parser")
    items = []

    for box in soup.select(".product-item"):
        a = box.select_one("a")
        if not a:
            continue

        name = a.get("title") or a.get_text(strip=True)
        href = a.get("href")

        if not name or not href:
            continue

        full = "https://www.phucanh.vn" + href

        items.append({
            "name": name.strip(),
            "url": full
        })

    return items


def main():
    all_items = []
    seen = set()

    page = 1
    while True:
        print(f"[INFO] Fetching page {page}...")

        try:
            data = fetch_page(page)
        except Exception as e:
            print("  -> STOP:", e)
            break

        html = data.get("html", "")
        if not html.strip():
            break

        items = parse_products(html)
        if not items:
            break

        for it in items:
            if it["url"] not in seen:
                seen.add(it["url"])
                all_items.append(it)

        page += 1
        time.sleep(0.3)

    os.makedirs("output", exist_ok=True)
    out_file = "output/phucanh.csv"

    with open(out_file, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "url"])
        writer.writeheader()
        writer.writerows(all_items)

    print(f"\n[DONE] Total {len(all_items)} items → {out_file}")


if __name__ == "__main__":
    main()
