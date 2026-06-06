# -*- coding: utf-8 -*-
"""
Collector for xgear.net laptop category
- Crawl laptop collection
- Up to 20 pages
- Output CSV: output/xgear.csv
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
from urllib.parse import urljoin
import time
import os

BASE = "https://xgear.net"
SEED = "https://xgear.net/collections/laptop"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; xgear-laptop-collector/1.1)"
}

MAX_PAGES = 20


def get_soup(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return None
        return BeautifulSoup(r.text, "html.parser")
    except:
        return None


def collect_links_from_category(cat_url):
    links = set()

    for page in range(1, MAX_PAGES + 1):
        url = f"{cat_url}?page={page}"
        print(f"[INFO] Loading page {page}: {url}")

        soup = get_soup(url)
        if not soup:
            break

        selectors = [
            ".product-card a",
            ".product-item a",
            ".product-item__info a",
            ".product-grid a",
            "a"
        ]

        found = set()

        for sel in selectors:
            for a in soup.select(sel):
                href = a.get("href")
                if not href:
                    continue
                u = urljoin(BASE, href).split("#")[0]
                if "/products/" in u:
                    found.add(u)

        if not found:
            break

        links.update(found)
        time.sleep(0.3)

    return links


def extract_name_from_product(url):
    soup = get_soup(url)
    if not soup:
        return ""

    h1 = soup.find("h1")
    if h1:
        return " ".join(h1.get_text(" ", strip=True).split())

    og = soup.find("meta", {"property": "og:title"}) or soup.find("meta", {"name": "title"})
    if og and og.get("content"):
        return og["content"].strip()

    title = soup.find("title")
    if title:
        return " ".join(title.get_text(" ", strip=True).split())

    return ""


def main():
    print("[INFO] Crawling XGEAR laptop category...")
    urls = collect_links_from_category(SEED)
    print(f"[INFO] Total unique product URLs: {len(urls)}")

    rows = []
    for i, u in enumerate(sorted(urls), 1):
        name = extract_name_from_product(u)
        rows.append({"name": name, "url": u})
        if i % 20 == 0:
            print(f"[INFO] Processed {i}/{len(urls)} products")

    df = pd.DataFrame(rows, columns=["name", "url"])

    os.makedirs("output", exist_ok=True)

    output_path = "output/xgear.csv"
    df.to_csv(output_path, index=False, encoding="utf-8-sig")

    print(f"[DONE] Saved to {output_path}")


if __name__ == "__main__":
    main()
