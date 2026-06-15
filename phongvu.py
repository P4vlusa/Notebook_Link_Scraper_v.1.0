# -*- coding: utf-8 -*-
"""
Thu thập toàn bộ tên + link laptop từ Phong Vũ (API chính thức)
URL: https://phongvu.vn/c/laptop
API: https://api-phongvu.vn/v1/products
"""

import requests
import pandas as pd
import os

API = "https://api-phongvu.vn/v1/products"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Origin": "https://phongvu.vn",
    "Referer": "https://phongvu.vn/c/laptop",
}


def fetch_page(page):
    params = {
        "category": "laptop",
        "page": page,
        "size": 48,
    }

    r = requests.get(API, headers=HEADERS, params=params, timeout=20)
    r.raise_for_status()
    return r.json()


def main():
    all_items = []
    page = 1

    while True:
        print(f"[INFO] Fetching page {page}...")

        data = fetch_page(page)
        products = data.get("data", {}).get("products", [])

        if not products:
            break

        for p in products:
            name = p.get("name")
            slug = p.get("slug")

            if not name or not slug:
                continue

            link = f"https://phongvu.vn/{slug}"

            all_items.append({
                "Tên": name,
                "link": link
            })

        page += 1

    os.makedirs("output", exist_ok=True)
    df = pd.DataFrame(all_items)
    df.to_csv("output/phongvu.csv", index=False, encoding="utf-8-sig")

    print(f"[DONE] Thu thập {len(df)} sản phẩm → output/phongvu.csv")


if __name__ == "__main__":
    main()
